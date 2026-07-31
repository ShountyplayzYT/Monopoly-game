from flask import Flask, session, jsonify, request, render_template
import uuid, copy, random, string, time
from game_logic import Game, GameError
import json, os, atexit
app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

ROOMS = {}   # room_code -> {"game": Game, "seats": {player_id: seat_token}, "created": ts, "last_seen": ts}
SAVES = {}

STATE_FILE = "game_state.json"

def _game_to_dict(g):
    return g.__dict__

def _dict_to_game(d):
    g = Game()
    g.__dict__.update(d)
    return g

def save_state_to_disk():
    try:
        serializable = {
            "rooms": {
                code: {
                    "game": _game_to_dict(room["game"]),
                    "seats": room["seats"],
                    "created": room["created"],
                    "seat_last_seen": room.get("seat_last_seen", {}),
                }
                for code, room in ROOMS.items()
            },
            "saves": SAVES,
        }
        with open(STATE_FILE, "w") as f:
            json.dump(serializable, f)
    except Exception as e:
        print(f"Warning: failed to save state: {e}")

def load_state_from_disk():
    global ROOMS, SAVES
    if not os.path.exists(STATE_FILE):
        return
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
        for code, room in data.get("rooms", {}).items():
            g = _dict_to_game(room["game"])
            ROOMS[code] = {
                "game": g,
                "seats": {int(k): v for k, v in room["seats"].items()},
                "created": room["created"],
                "seat_last_seen": {int(k): v for k, v in room.get("seat_last_seen", {}).items()},
            }
        SAVES.update(data.get("saves", {}))
        print(f"Restored {len(ROOMS)} room(s) from disk.")
    except Exception as e:
        print(f"Warning: failed to load state: {e}")

load_state_from_disk()
atexit.register(save_state_to_disk)


def make_room_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if code not in ROOMS:
            return code

def get_room():
    code = session.get("room_code")
    if not code or code not in ROOMS:
        return None
    return ROOMS[code]

def get_my_seat(room):
    """Which player_id does THIS browser session control in this room, if any."""
    token = session.get("seat_token")
    if token is None:
        return None
    for pid, tok in room["seats"].items():
        if tok == token:
            return pid
    return None

def require_room():
    room = get_room()
    if not room:
        raise GameError("Not in a room. Create or join one first.")
    return room

def require_my_turn_seat(room):
    """Raise if it isn't this browser's seat's turn to act (covers normal turns AND auction bidding)."""
    g = room["game"]
    my_seat = get_my_seat(room)
    if my_seat is None:
        raise GameError("You don't have a seat in this game.")
    if g.turn_phase == "awaiting_auction" and g.auction:
        acting_id = g.auction["bidders"][g.auction["turn_index"]]
    else:
        acting_id = g.current_index
    if acting_id != my_seat:
        raise GameError("It's not your turn.")
    return my_seat

def maybe_advance_ai(g):
    guard = 0
    while guard < 200:
        guard += 1
        if g.turn_phase == "game_over":
            return
        if g.turn_phase == "awaiting_auction" and g.auction:
            bidder_id = g.auction["bidders"][g.auction["turn_index"]]
            bidder = g.players[bidder_id]
            if not bidder["is_ai"]:
                return
            g._ai_auction_step(bidder)
            continue
        cur = g.cur()
        if not cur["is_ai"] or cur["bankrupt"]:
            return
        g.ai_play_full_turn()

def ok(room):
    save_state_to_disk()
    data = room["game"].serialize()
    data["room_code"] = session.get("room_code")
    data["my_seat"] = get_my_seat(room)
    return jsonify(data)

@app.route("/")
def index():
    return render_template("index.html")

# ---------- room lifecycle ----------

@app.route("/api/create_room", methods=["POST"])
def create_room():
    data = request.json or {}
    code = make_room_code()
    seat_token = str(uuid.uuid4())
    g = Game()
    ROOMS[code] = {"game": g, "seats": {0: seat_token}, "created": time.time(), "last_seen": time.time()}
    session["room_code"] = code
    session["seat_token"] = seat_token
    return jsonify({"room_code": code, "seat": 0})

@app.route("/api/join_room", methods=["POST"])
def join_room():
    data = request.json or {}
    code = (data.get("room_code") or "").strip().upper()
    room = ROOMS.get(code)
    if not room:
        return jsonify({"error": "Room not found."}), 404
    g = room["game"]
    if g.started:
        return jsonify({"error": "Game already started."}), 400
    # if this browser already has a seat here (e.g. reconnect), reuse it
    existing = get_my_seat(room) if session.get("room_code") == code else None
    if existing is not None:
        return jsonify({"room_code": code, "seat": existing})
    next_seat = max(room["seats"].keys(), default=-1) + 1
    if next_seat >= 4:
        return jsonify({"error": "Room is full."}), 400
    seat_token = str(uuid.uuid4())
    room["seats"][next_seat] = seat_token
    session["room_code"] = code
    session["seat_token"] = seat_token
    room["last_seen"] = time.time()
    return jsonify({"room_code": code, "seat": next_seat})

@app.route("/api/room_info")
def room_info():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    return jsonify({
        "room_code": session.get("room_code"),
        "my_seat": get_my_seat(room),
        "seat_count": len(room["seats"]),
        "started": room["game"].started,
    })

# ---------- game state ----------

@app.route("/api/state")
def state():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    room["last_seen"] = time.time()
    return ok(room)

# host starts the game; unfilled seats (up to len(names)) become AI automatically
@app.route("/api/start", methods=["POST"])
def start():
    room = require_room_or_400()
    if room is None:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    names = data.get("names", [])
    ai_flags = list(data.get("ai_flags", []))
    # force real human seats to NOT be AI, regardless of what the form sends
    for pid in room["seats"]:
        if pid < len(ai_flags):
            ai_flags[pid] = False
    g.start(names, ai_flags, data.get("start_money", 1500))
    maybe_advance_ai(g)
    return ok(room)

def require_room_or_400():
    return get_room()

def game_action(fn):
    """Decorator: resolves room, enforces seat-turn ownership, runs fn(g), advances AI, returns state."""
    def wrapper(*args, **kwargs):
        room = get_room()
        if not room:
            return jsonify({"error": "Not in a room."}), 400
        g = room["game"]
        try:
            require_my_turn_seat(room)
            fn(g)
        except GameError as e:
            return jsonify({"error": str(e)}), 400
        maybe_advance_ai(g)
        return ok(room)
    wrapper.__name__ = fn.__name__
    return wrapper

@app.route("/api/roll", methods=["POST"])
@game_action
def roll(g):
    g.roll_dice()

@app.route("/api/pay_jail_fee", methods=["POST"])
@game_action
def pay_jail_fee(g):
    g.pay_jail_fee()

@app.route("/api/use_goojf", methods=["POST"])
@game_action
def use_goojf(g):
    g.use_goojf()

@app.route("/api/buy", methods=["POST"])
@game_action
def buy(g):
    g.buy_property()

@app.route("/api/decline", methods=["POST"])
@game_action
def decline(g):
    g.decline_property()

@app.route("/api/auction_bid", methods=["POST"])
@game_action
def auction_bid(g):
    data = request.json or {}
    g.auction_bid(int(data.get("amount", 0)))

@app.route("/api/auction_fold", methods=["POST"])
@game_action
def auction_fold(g):
    g.auction_fold()

@app.route("/api/end_turn", methods=["POST"])
@game_action
def end_turn(g):
    g.end_turn()

# building/mortgage actions aren't turn-gated in the original game (any owner can act any time),
# but they SHOULD be gated to "you own this space" so opponents can't touch your properties
@app.route("/api/build_house", methods=["POST"])
def build_house():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "You don't own this property."}), 403
    try:
        g.build_house(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

# (sell_house, mortgage, unmortgage follow the exact same owner-check pattern as build_house)

@app.route("/api/propose_trade", methods=["POST"])
def propose_trade():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    my_seat = get_my_seat(room)
    d = request.json or {}
    if int(d["from_id"]) != my_seat:
        return jsonify({"error": "You can only propose trades from your own seat."}), 403
    try:
        result = g.propose_trade(
            int(d["from_id"]), int(d["to_id"]),
            d.get("give_props", []), int(d.get("give_cash", 0)), bool(d.get("give_goojf", False)),
            d.get("get_props", []), int(d.get("get_cash", 0)), bool(d.get("get_goojf", False)),
            d.get("message", "")
        )
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    save_state_to_disk()
    return jsonify({"result": result.get("result"), "state": g.serialize(), "my_seat": my_seat})

@app.route("/api/respond_trade", methods=["POST"])
def respond_trade():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    my_seat = get_my_seat(room)
    if not g.trade or g.trade["to_id"] != my_seat:
        return jsonify({"error": "No trade offer is waiting on your seat."}), 400
    d = request.json or {}
    try:
        g.respond_trade(bool(d.get("accept", False)))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(room)

@app.route("/api/sell_house", methods=["POST"])
def sell_house():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "You don't own this property."}), 403
    try:
        g.sell_house(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

@app.route("/api/mortgage", methods=["POST"])
def mortgage():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "You don't own this property."}), 403
    try:
        g.mortgage(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

@app.route("/api/unmortgage", methods=["POST"])
def unmortgage():
    room = get_room()
    if not room:
        return jsonify({"error": "Not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "You don't own this property."}), 403
    try:
        g.unmortgage(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

if __name__ == "__main__":
    app.run(debug=False)