from flask import Flask, session, jsonify, request, render_template
import uuid, copy
from game_logic import Game, GameError
# all the imports required

app = Flask(__name__)
app.secret_key = "dev-secret-change-me" #secret key for sessions

GAMES = {} #Dictionaries to store saved games
SAVES = {}

def get_game(): #gets a saved game
    gid = session.get("game_id")
    if not gid or gid not in GAMES:
        gid = str(uuid.uuid4())
        session["game_id"] = gid
        GAMES[gid] = Game()
    return GAMES[gid]

# this function lets computer players take their turns automatically
def maybe_advance_ai(g):
    guard = 0
    # keep looping until a human needs to move or 200 steps pass
    while guard < 200:
        guard += 1
        # stop if the game is finished
        if g.turn_phase == "game_over":
            return
        # check if we are waiting for an auction bid
        if g.turn_phase == "awaiting_auction" and g.auction:
            bidder_id = g.auction["bidders"][g.auction["turn_index"]]
            # stop if it is a human player's turn to bid
            if not g.players[bidder_id]["is_ai"]:
                return
            # let the computer make its auction move
            g.ai_play_full_turn()
            continue
        # get the current player
        cur = g.cur()
        # stop if the current player is human or bankrupt
        if not cur["is_ai"] or cur["bankrupt"]:
            return
        # let the computer play its turn
        g.ai_play_full_turn()

# turn the game state into a response for the website
def ok(g):
    return jsonify(g.serialize())

# show the main home page
@app.route("/")
def index():
    return render_template("index.html")

# get the current game state
@app.route("/api/state")
def state():
    return ok(get_game())

# start a new game with players and money
@app.route("/api/start", methods=["POST"])
def start():
    g = get_game()
    data = request.json or {}
    g.start(data.get("names", []), data.get("ai_flags", []), data.get("start_money", 1500))
    maybe_advance_ai(g)
    return ok(g)

# roll the dice for the current player
@app.route("/api/roll", methods=["POST"])
def roll():
    g = get_game()
    try:
        g.roll_dice()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# pay money to get out of jail
@app.route("/api/pay_jail_fee", methods=["POST"])
def pay_jail_fee():
    g = get_game()
    try:
        g.pay_jail_fee()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# use a get out of jail free card
@app.route("/api/use_goojf", methods=["POST"])
def use_goojf():
    g = get_game()
    try:
        g.use_goojf()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# buy the property landed on
@app.route("/api/buy", methods=["POST"])
def buy():
    g = get_game()
    try:
        g.buy_property()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# skip buying a property and start an auction
@app.route("/api/decline", methods=["POST"])
def decline():
    g = get_game()
    try:
        g.decline_property()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# make a bid in an auction
@app.route("/api/auction_bid", methods=["POST"])
def auction_bid():
    g = get_game()
    data = request.json or {}
    try:
        g.auction_bid(int(data.get("amount", 0)))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# drop out of an auction
@app.route("/api/auction_fold", methods=["POST"])
def auction_fold():
    g = get_game()
    try:
        g.auction_fold()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# build a house on a property
@app.route("/api/build_house", methods=["POST"])
def build_house():
    g = get_game()
    data = request.json or {}
    try:
        g.build_house(int(data["space_id"]))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(g)

# sell a house back for money
@app.route("/api/sell_house", methods=["POST"])
def sell_house():
    g = get_game()
    data = request.json or {}
    try:
        g.sell_house(int(data["space_id"]))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(g)

# mortgage a property to get money
@app.route("/api/mortgage", methods=["POST"])
def mortgage():
    g = get_game()
    data = request.json or {}
    try:
        g.mortgage(int(data["space_id"]))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(g)

# pay money to unmortgage a property
@app.route("/api/unmortgage", methods=["POST"])
def unmortgage():
    g = get_game()
    data = request.json or {}
    try:
        g.unmortgage(int(data["space_id"]))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    return ok(g)

# finish the current player's turn
@app.route("/api/end_turn", methods=["POST"])
def end_turn():
    g = get_game()
    try:
        g.end_turn()
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# offer a trade to another player
@app.route("/api/propose_trade", methods=["POST"])
def propose_trade():
    g = get_game()
    d = request.json or {}
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
    return jsonify({"result": result.get("result"), "state": g.serialize()})

# accept or reject a trade offer
@app.route("/api/respond_trade", methods=["POST"])
def respond_trade():
    g = get_game()
    d = request.json or {}
    try:
        g.respond_trade(bool(d.get("accept", False)))
    except GameError as e:
        return jsonify({"error": str(e)}), 400
    maybe_advance_ai(g)
    return ok(g)

# save the current game state
@app.route("/api/save", methods=["POST"])
def save():
    gid = session.get("game_id")
    if not gid or gid not in GAMES:
        return jsonify({"error": "No game to save."}), 400
    SAVES[gid] = copy.deepcopy(GAMES[gid].__dict__)
    return jsonify({"ok": True})

# load a previously saved game
@app.route("/api/load", methods=["POST"])
def load():
    gid = session.get("game_id")
    if not gid or gid not in SAVES:
        return jsonify({"error": "No saved game found."}), 400
    g = GAMES.setdefault(gid, Game())
    g.__dict__.update(copy.deepcopy(SAVES[gid]))
    maybe_advance_ai(g)
    return ok(g)

# start the web app server
if __name__ == "__main__":
    app.run(debug=True)