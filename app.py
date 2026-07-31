from flask import Flask, session, jsonify, request, render_template
import uuid, copy, random, string, time
from game_logic import Game, GameError
import json, os, atexit

# make our web app
app = Flask(__name__)
app.secret_key = "dev-secret-change-me"

# keep track of rooms and saved games
ROOMS = {}   
SAVES = {}

STATE_FILE = "game_state.json"

# turn game into a dictionary
def _game_to_dict(g):
    return g.__dict__

# turn dictionary back into a game
def _dict_to_game(d):
    g = Game()
    g.__dict__.update(d)
    return g

# save the game to the hard drive
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
        print(f"warning: failed to save state: {e}")

# load the game from the hard drive
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
        print(f"restored {len(ROOMS)} room(s) from disk.")
    except Exception as e:
        print(f"warning: failed to load state: {e}")

load_state_from_disk()
atexit.register(save_state_to_disk)

# make a fun random room code
def make_room_code():
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=5))
        if code not in ROOMS:
            return code

# get the room you are in
def get_room():
    code = session.get("room_code")
    if not code or code not in ROOMS:
        return None
    return ROOMS[code]

# find out which seat is yours
def get_my_seat(room):
    token = session.get("seat_token")
    if token is None:
        return None
    if room.get("local"):
        g = room["game"]
        if g.turn_phase == "awaiting_auction" and g.auction:
            return g.auction["bidders"][g.auction["turn_index"]]
        return g.current_index
    for pid, tok in room["seats"].items():
        if tok == token:
            return pid
    return None

# make sure you are in a room
def require_room():
    room = get_room()
    if not room:
        raise GameError("not in a room. create or join one first.")
    return room

# check if it is your turn
def require_my_turn_seat(room):
    g = room["game"]
    my_seat = get_my_seat(room)
    if my_seat is None:
        raise GameError("you don't have a seat in this game.")
    if room.get("local"):
        return my_seat  
    if g.turn_phase == "awaiting_auction" and g.auction:
        acting_id = g.auction["bidders"][g.auction["turn_index"]]
    else:
        acting_id = g.current_index
    if acting_id != my_seat:
        raise GameError("it's not your turn.")
    return my_seat

# let the computer play its turn if it is an ai
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

# send back the game state
def ok(room):
    save_state_to_disk()
    data = room["game"].serialize()
    data["room_code"] = session.get("room_code")
    data["my_seat"] = get_my_seat(room)
    return jsonify(data)

# show the main web page
@app.route("/")
def index():
    return render_template("index.html")

# make a new room
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

# join an existing room
@app.route("/api/join_room", methods=["POST"])
def join_room():
    data = request.json or {}
    code = (data.get("room_code") or "").strip().upper()
    room = ROOMS.get(code)
    if not room:
        return jsonify({"error": "room not found."}), 404
    g = room["game"]
    if g.started:
        return jsonify({"error": "game already started."}), 400
    existing = get_my_seat(room) if session.get("room_code") == code else None
    if existing is not None:
        return jsonify({"room_code": code, "seat": existing})
    next_seat = max(room["seats"].keys(), default=-1) + 1
    if next_seat >= 4:
        return jsonify({"error": "room is full."}), 400
    seat_token = str(uuid.uuid4())
    room["seats"][next_seat] = seat_token
    session["room_code"] = code
    session["seat_token"] = seat_token
    room["last_seen"] = time.time()
    return jsonify({"room_code": code, "seat": next_seat})

# get info about the room
@app.route("/api/room_info")
def room_info():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    return jsonify({
        "room_code": session.get("room_code"),
        "my_seat": get_my_seat(room),
        "seat_count": len(room["seats"]),
        "started": room["game"].started,
    })

# get the current game state
@app.route("/api/state")
def state():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    room["last_seen"] = time.time()
    return ok(room)

# start the game
@app.route("/api/start", methods=["POST"])
def start():
    room = require_room_or_400()
    if room is None:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    names = data.get("names", [])
    ai_flags = list(data.get("ai_flags", []))
    for pid in room["seats"]:
        if pid < len(ai_flags):
            ai_flags[pid] = False
    g.start(names, ai_flags, data.get("start_money", 1500))
    maybe_advance_ai(g)
    return ok(room)

def require_room_or_400():
    return get_room()

# helper decorator for game actions
def game_action(fn):
    def wrapper(*args, **kwargs):
        room = get_room()
        if not room:
            return jsonify({"error": "not in a room."}), 400
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

# roll the dice
@app.route("/api/roll", methods=["POST"])
@game_action
def roll(g):
    g.roll_dice()

# pay to get out of jail
@app.route("/api/pay_jail_fee", methods=["POST"])
@game_action
def pay_jail_fee(g):
    g.pay_jail_fee()

# use a get out of jail free card
@app.route("/api/use_goojf", methods=["POST"])
@game_action
def use_goojf(g):
    g.use_goojf()

# buy a property
@app.route("/api/buy", methods=["POST"])
@game_action
def buy(g):
    g.buy_property()

# decline to buy a property
@app.route("/api/decline", methods=["POST"])
@game_action
def decline(g):
    g.decline_property()

# make a bid in an auction
@app.route("/api/auction_bid", methods=["POST"])
@game_action
def auction_bid(g):
    data = request.json or {}
    g.auction_bid(int(data.get("amount", 0)))

# fold in an auction
@app.route("/api/auction_fold", methods=["POST"])
@game_action
def auction_fold(g):
    g.auction_fold()

# end your turn
@app.route("/api/end_turn", methods=["POST"])
@game_action
def end_turn(g):
    g.end_turn()

# build a house on your property
@app.route("/api/build_house", methods=["POST"])
def build_house():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "you don't own this property."}), 403
    try:
        g.build_house(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

# offer a trade to another player
@app.route("/api/propose_trade", methods=["POST"])
def propose_trade():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    my_seat = get_my_seat(room)
    d = request.json or {}
    if not room.get("local") and int(d["from_id"]) != my_seat:
        return jsonify({"error": "you can only propose trades from your own seat."}), 403
    
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

# respond to a trade offer
@app.route("/api/respond_trade", methods=["POST"])
def respond_trade():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    my_seat = get_my_seat(room)
    if not g.trade or (not room.get("local") and g.trade["to_id"] != my_seat):
        return jsonify({"error": "no trade offer is waiting on your seat."}), 400
    d = request.json or {}
    try:
        g.respond_trade(bool(d.get("accept", False)))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(room)

# sell a house back
@app.route("/api/sell_house", methods=["POST"])
def sell_house():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "you don't own this property."}), 403
    try:
        g.sell_house(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

# mortgage a property
@app.route("/api/mortgage", methods=["POST"])
def mortgage():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "you don't own this property."}), 403
    try:
        g.mortgage(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

# unmortgage a property
@app.route("/api/unmortgage", methods=["POST"])
def unmortgage():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    g = room["game"]
    data = request.json or {}
    sid = int(data["space_id"])
    my_seat = get_my_seat(room)
    if g.spaces[sid]["owner"] != my_seat:
        return jsonify({"error": "you don't own this property."}), 403
    try:
        g.unmortgage(sid)
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(room)

# start a game locally on one screen
@app.route("/api/start_local", methods=["POST"])
def start_local():
    code = make_room_code()
    seat_token = str(uuid.uuid4())
    g = Game()
    ROOMS[code] = {
        "game": g,
        "seats": {0: seat_token, 1: seat_token, 2: seat_token, 3: seat_token},
        "created": time.time(),
        "last_seen": time.time(),
        "local": True,
    }
    session["room_code"] = code
    session["seat_token"] = seat_token
    return jsonify({"room_code": code, "local": True})

# save the game
@app.route("/api/save", methods=["POST"])
def save():
    room = get_room()
    if not room:
        return jsonify({"error": "not in a room."}), 400
    code = session.get("room_code")
    SAVES[code] = copy.deepcopy(room["game"].__dict__)
    save_state_to_disk()
    return jsonify({"ok": True})

# load the saved game
@app.route("/api/load", methods=["POST"])
def load():
    room = get_room()
    code = session.get("room_code")
    if not room or code not in SAVES:
        return jsonify({"error": "no saved game found for this room."}), 400
    room["game"].__dict__.update(copy.deepcopy(SAVES[code]))
    maybe_advance_ai(room["game"])
    return ok(room)

if __name__ == "__main__":
    app.run(debug=False)