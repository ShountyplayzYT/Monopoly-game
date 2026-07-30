# bring in the random module to roll dice and shuffle cards
import random
# bring in game details and card lists from another file
from game_data import (
    fresh_spaces, CHANCE_CARDS, COMMUNITY_CARDS, GROUP_WEIGHT,
    RAILROAD_WEIGHT, UTILITY_WEIGHT, GROUP_COLORS
)


# roll a six sided die and get a number between 1 and 6
def roll_d6():
    return random.randint(1, 6)


# special error message for game rule problems
class GameError(Exception):
    pass


# main class that runs the monopoly game logic
class Game:
    # set up the game object
    def __init__(self):
        # reset everything to start fresh
        self.reset()

    # ---------- setup ----------
    # put all game variables back to start values
    def reset(self):
        # load fresh spaces on the board
        self.spaces = fresh_spaces()
        # list of players in the game
        self.players = []
        # turn index for current player
        self.current_index = 0
        # starting bank cash total
        self.bank_money = 20580
        # jackpot money collected for landing on free parking
        self.free_parking_pot = 0
        # toggle for free parking money rule
        self.free_parking_enabled = False
        # card deck order lists
        self.chance_deck = []
        self.community_deck = []
        # card discard pile lists
        self.chance_discard = []
        self.community_discard = []
        # count how many double rolls happened
        self.doubles_count = 0
        # current step phase of player turn
        self.turn_phase = "not_started"  # not_started, start, must_roll_again, must_end_turn, awaiting_buy, awaiting_auction, awaiting_trade, game_over
        # pending action storage
        self.pending = None
        # game message history log
        self.log = []
        # flag showing if game is playing
        self.started = False
        # trade and auction state info
        self.auction = None
        self.trade = None
        # record game statistics like turns and money made
        self.stats = {"turns": 0, "trades": 0, "earned": {}, "rentPaid": {}, "landings": {}}

    # start game with list of player names and cash amount
    def start(self, names, ai_flags, start_money=1500):
        # reset the game first
        self.reset()
        # shuffle the chance card deck
        self.chance_deck = list(range(len(CHANCE_CARDS)))
        random.shuffle(self.chance_deck)
        # shuffle the community chest card deck
        self.community_deck = list(range(len(COMMUNITY_CARDS)))
        random.shuffle(self.community_deck)
        # piece color list for players
        colors = ["#E0393A", "#3E7CD6", "#F2B705", "#2FA95C"]
        self.players = []
        # loop to create each player object
        for i, name in enumerate(names):
            # calculate starting money from bank
            amt = min(start_money, self.bank_money)
            self.bank_money -= amt
            # add player data dictionary to list
            self.players.append({
                "id": i, "name": name or f"Player {i+1}", "color": colors[i % 4],
                "money": amt, "pos": 0, "in_jail": False, "jail_turns": 0,
                "goojf": [], "bankrupt": False, "is_ai": bool(ai_flags[i]),
                "traded_this_turn": False,
            })
            # initialize player statistics
            self.stats["earned"][i] = 0
            self.stats["rentPaid"][i] = 0
        # start with the first player
        self.current_index = 0
        # set turn phase to start turn
        self.turn_phase = "start"
        # mark game as active
        self.started = True
        # add start message to log
        self._log(f"Game started. {self.players[0]['name']} goes first.")

    # ---------- helpers ----------
    # write a new message line to game log
    def _log(self, msg):
        # put new message at top of list
        self.log.insert(0, msg)
        # keep log size under 200 items
        self.log = self.log[:200]

    # get list of players who are still in the game
    def alive_players(self):
        return [p for p in self.players if not p["bankrupt"]]

    # get current active player
    def cur(self):
        return self.players[self.current_index]

    # check if player owns all spaces in a color group
    def owns_full_group(self, player, group):
        return all(s["owner"] == player["id"] for s in self.spaces if s.get("group") == group)

    # count total train stations owned by player
    def railroads_owned(self, player):
        return sum(1 for s in self.spaces if s["type"] == "railroad" and s["owner"] == player["id"])

    # count total utilities owned by player
    def utilities_owned(self, player):
        return sum(1 for s in self.spaces if s["type"] == "utility" and s["owner"] == player["id"])

    # calculate rent money owed for landing on a property
    def calc_rent(self, space, dice_total):
        owner = self.players[space["owner"]]
        # rent rule for train stations
        if space["type"] == "railroad":
            n = self.railroads_owned(owner)
            return [25, 50, 100, 200][n - 1]
        # rent rule for utility spaces based on dice roll
        if space["type"] == "utility":
            n = self.utilities_owned(owner)
            return dice_total * (4 if n == 1 else 10)
        # rent rule if houses are built on property
        if space["houses"] > 0:
            return space["rent"][space["houses"]]
        # rent rule for owning whole color group
        if self.owns_full_group(owner, space["group"]):
            return space["rent"][0] * 2
        # basic rent value
        return space["rent"][0]

    # get weight importance value of property for computer player decisions
    def group_weight(self, s):
        if s["type"] == "railroad":
            return RAILROAD_WEIGHT
        if s["type"] == "utility":
            return UTILITY_WEIGHT
        return GROUP_WEIGHT.get(s.get("group"), 1)

    # count all houses currently built on the board
    def used_houses(self):
        return sum(s["houses"] for s in self.spaces if 0 < s["houses"] < 5)

    # count all hotels currently built on the board
    def used_hotels(self):
        return sum(1 for s in self.spaces if s["houses"] == 5)

    # calculate full money value of a property including houses
    def property_value(self, s):
        v = s.get("price", 0) or 0
        # add value for houses
        if s["houses"] > 0:
            v += s["houses"] * s["houseCost"]
        # subtract mortgage debt
        if s["mortgaged"]:
            v -= s["mortgageValue"]
        return v

    # ---------- money ----------
    # give cash from bank to player
    def pay_from_bank(self, player, amount):
        actual = min(amount, self.bank_money)
        player["money"] += actual
        self.bank_money -= actual
        self.stats["earned"][player["id"]] = self.stats["earned"].get(player["id"], 0) + actual

    # take cash from player and give to bank
    def pay_to_bank(self, player, amount):
        # sell houses or mortgage if short on cash
        if player["money"] < amount:
            self.raise_funds(player, amount)
        # player loses game if still cannot pay
        if player["money"] < amount:
            self.bankrupt_player(player, None)
            return
        player["money"] -= amount
        self.bank_money += amount
        # add to free parking pot if rule is active
        if self.free_parking_enabled:
            self.free_parking_pot += amount

    # pay cash from one player to another player
    def pay_player(self, payer, other, amount, is_rent=False):
        # try to get money by selling houses or mortgaging
        if payer["money"] < amount:
            self.raise_funds(payer, amount)
        # if player cannot afford full amount give all remaining cash and go bankrupt
        if payer["money"] < amount:
            other["money"] += payer["money"]
            payer["money"] = 0
            self.bankrupt_player(payer, other)
            return
        payer["money"] -= amount
        other["money"] += amount
        self.stats["earned"][other["id"]] = self.stats["earned"].get(other["id"], 0) + amount
        if is_rent:
            self.stats["rentPaid"][payer["id"]] = self.stats["rentPaid"].get(payer["id"], 0) + amount

    # sell houses or mortgage spaces to raise cash automatically
    def raise_funds(self, player, amount):
        props = [s for s in self.spaces if s["owner"] == player["id"]]
        guard = 0
        # sell houses for half cost
        while player["money"] < amount and any(s["houses"] > 0 for s in props) and guard < 200:
            guard += 1
            target = sorted([s for s in props if s["houses"] > 0], key=lambda s: -s["houses"])[0]
            refund = (target["houseCost"] // 2) * (5 if target["houses"] == 5 else 1)
            target["houses"] = 0 if target["houses"] == 5 else target["houses"] - 1
            actual = min(refund, self.bank_money)
            player["money"] += actual
            self.bank_money -= actual
        guard = 0
        # mortgage properties with no houses
        while player["money"] < amount and any(not s["mortgaged"] and s["houses"] == 0 for s in props) and guard < 200:
            guard += 1
            candidates = [s for s in props if not s["mortgaged"] and s["houses"] == 0]
            target = sorted(candidates, key=lambda s: s["mortgageValue"])[0]
            target["mortgaged"] = True
            payout = min(target["mortgageValue"], self.bank_money)
            player["money"] += payout
            self.bank_money -= payout

    # eliminate a player who ran out of money
    def bankrupt_player(self, player, creditor):
        player["bankrupt"] = True
        self._log(f"{player['name']} is BANKRUPT and is out of the game!")
        # transfer properties to creditor player or reset them to bank
        for s in self.spaces:
            if s["owner"] == player["id"]:
                if creditor:
                    s["owner"] = creditor["id"]
                else:
                    s["owner"] = None
                    s["houses"] = 0
                    s["mortgaged"] = False
        # check if only one winner remains
        alive = self.alive_players()
        if len(alive) <= 1:
            self.turn_phase = "game_over"
            winner = alive[0]["name"] if alive else "No one"
            self._log(f"{winner} wins the game!")

    # ---------- movement / resolution ----------
    # move player directly to a space on board
    def advance_to(self, player, dest, pass_go):
        passed = dest < player["pos"]
        player["pos"] = dest
        # give $200 if passing go space
        if (passed or dest == 0) and pass_go:
            self.pay_from_bank(player, 200)
            self._log(f"{player['name']} passed Go, collected $200.")
        self.resolve_space(player)

    # move player forward to nearest special space type
    def advance_to_nearest(self, player, space_type, mult):
        idx = player["pos"]
        for k in range(1, 41):
            t = (player["pos"] + k) % 40
            if self.spaces[t]["type"] == space_type:
                idx = t
                break
        passed = idx < player["pos"]
        player["pos"] = idx
        if passed:
            self.pay_from_bank(player, 200)
            self._log(f"{player['name']} passed Go, collected $200.")
        space = self.spaces[idx]
        self.stats["landings"][idx] = self.stats["landings"].get(idx, 0) + 1
        # handle unowned space buy offer or pay extra rent rule
        if space["owner"] is None:
            self.pending = {"type": "buy", "space_id": idx, "card_mult": mult}
            self.turn_phase = "awaiting_buy"
        elif space["owner"] != player["id"]:
            if space_type == "utility":
                d = roll_d6() + roll_d6()
                rent = d * mult
                self._log(f"(Card rule: pay {mult}x dice roll = {d} x {mult})")
            else:
                rent = self.calc_rent(space, 0) * mult
            owner = self.players[space["owner"]]
            self._log(f"{player['name']} owes ${rent} rent to {owner['name']}.")
            self.pay_player(player, owner, rent, True)
            self.after_resolve()
        else:
            self.after_resolve()

    # move player token to jail space
    def send_to_jail(self, player):
        player["pos"] = 10
        player["in_jail"] = True
        player["jail_turns"] = 0
        self._log(f"{player['name']} is sent to Jail!")
        self.doubles_count = 0
        self.after_resolve()

    # do landing action based on space type player landed on
    def resolve_space(self, player):
        s = self.spaces[player["pos"]]
        self.stats["landings"][s["id"]] = self.stats["landings"].get(s["id"], 0) + 1
        t = s["type"]
        # landing on go or jail does nothing extra
        if t in ("go", "jail"):
            self.after_resolve()
        # landing on free parking gives jackpot money if enabled
        elif t == "free":
            if self.free_parking_enabled and self.free_parking_pot > 0:
                self._log(f"{player['name']} landed on Free Parking and collects the jackpot of ${self.free_parking_pot}!")
                player["money"] += self.free_parking_pot
                self.stats["earned"][player["id"]] = self.stats["earned"].get(player["id"], 0) + self.free_parking_pot
                self.free_parking_pot = 0
            self.after_resolve()
        # landing on go to jail space sends player to jail
        elif t == "gotojail":
            self.send_to_jail(player)
        # landing on tax space charges player tax cash
        elif t == "tax":
            self._log(f"{player['name']} pays ${s['amount']} tax.")
            self.pay_to_bank(player, s["amount"])
            self.after_resolve()
        # draw card if landing on chance or community chest
        elif t in ("chance", "community"):
            self.draw_card(t, player)
        # handle property railroad or utility space landing
        elif t in ("railroad", "utility", "property"):
            if s["owner"] is None:
                self.pending = {"type": "buy", "space_id": s["id"], "card_mult": None}
                self.turn_phase = "awaiting_buy"
            elif s["owner"] == player["id"]:
                self.after_resolve()
            elif s["mortgaged"]:
                self._log(f"{s['name']} is mortgaged — no rent due.")
                self.after_resolve()
            else:
                owner = self.players[s["owner"]]
                rent = self.calc_rent(s, self.last_dice_total)
                self._log(f"{player['name']} owes ${rent} rent to {owner['name']} for {s['name']}.")
                self.pay_player(player, owner, rent, True)
                self.after_resolve()

    # pick top card from chance or community chest deck
    def draw_card(self, deck_name, player):
        cards = CHANCE_CARDS if deck_name == "chance" else COMMUNITY_CARDS
        deck = self.chance_deck if deck_name == "chance" else self.community_deck
        discard = self.chance_discard if deck_name == "chance" else self.community_discard
        # reshuffle discards into deck if empty
        if not deck:
            deck.extend(discard)
            random.shuffle(deck)
            discard.clear()
        idx = deck.pop(0)
        card = cards[idx]
        if not card.get("keep"):
            discard.append(idx)
        label = "CHANCE" if deck_name == "chance" else "COMMUNITY CHEST"
        self._log(f"{player['name']} drew {label}: {card['text']}")
        self.apply_card(card, player, deck_name)

    # do instructions written on drawn card
    def apply_card(self, card, player, deck_name):
        action = card["action"]
        if action == "advance_to":
            self.advance_to(player, card["dest"], card["pass_go"])
            return
        if action == "advance_nearest":
            self.advance_to_nearest(player, card["space_type"], card["mult"])
            return
        if action == "go_to_jail":
            self.send_to_jail(player)
            return
        if action == "go_back":
            player["pos"] = (player["pos"] - card["spaces"]) % 40
            self._log(f"{player['name']} goes back {card['spaces']} spaces.")
            self.resolve_space(player)
            return
        # do cash or card reward actions
        if action == "pay_from_bank":
            self.pay_from_bank(player, card["amount"])
        elif action == "pay_to_bank":
            self.pay_to_bank(player, card["amount"])
        elif action == "pay_each":
            for o in self.alive_players():
                if o["id"] != player["id"]:
                    self.pay_player(player, o, card["amount"])
        elif action == "collect_each":
            for o in self.alive_players():
                if o["id"] != player["id"]:
                    self.pay_player(o, player, card["amount"])
        elif action == "repairs":
            total = 0
            for s in self.spaces:
                if s["owner"] == player["id"]:
                    total += card["per_hotel"] if s["houses"] == 5 else s["houses"] * card["per_house"]
            if total > 0:
                self.pay_to_bank(player, total)
            self._log(f"{player['name']} paid ${total} for repairs.")
        elif action == "goojf":
            player["goojf"].append(card["deck"])
            self._log(f"{player['name']} got a Get Out of Jail Free card.")
        self.after_resolve()

    # ---------- turn flow ----------
    # clean up state after finishing space resolution
    def after_resolve(self):
        self.pending = None
        if self.turn_phase != "game_over":
            if self.cur()["bankrupt"]:
                self.end_turn()
                return
            # allow rolling again if doubles were rolled
            self.turn_phase = "must_roll_again" if self.doubles_count > 0 else "must_end_turn"

    # roll two six sided dice and move current player
    def roll_dice(self):
        p = self.cur()
        if p["bankrupt"] or self.turn_phase == "game_over":
            raise GameError("Game is over or player is out.")
        if self.turn_phase not in ("start", "must_roll_again"):
            raise GameError("Cannot roll right now.")
        if p["in_jail"]:
            return self._handle_jail_roll(p)
        d1, d2 = roll_d6(), roll_d6()
        self.last_dice_total = d1 + d2
        is_double = d1 == d2
        self.doubles_count = self.doubles_count + 1 if is_double else 0
        # send to jail if player rolls doubles 3 times in a row
        if self.doubles_count == 3:
            self._log(f"{p['name']} rolled doubles 3 times in a row — go to Jail!")
            self.doubles_count = 0
            self.send_to_jail(p)
            return {"d1": d1, "d2": d2}
        old_pos = p["pos"]
        new_pos = (p["pos"] + d1 + d2) % 40
        passed_go = new_pos < old_pos
        p["pos"] = new_pos
        if passed_go:
            self.pay_from_bank(p, 200)
            self._log(f"{p['name']} passed Go, collected $200.")
        self._log(f"{p['name']} rolled {d1} + {d2} = {d1+d2}" + (" (doubles!)" if is_double else "") + f" and moved to {self.spaces[new_pos]['name']}.")
        self.resolve_space(p)
        return {"d1": d1, "d2": d2}

    # handle dice rolling rules when player is stuck in jail
    def _handle_jail_roll(self, p):
        d1, d2 = roll_d6(), roll_d6()
        self.last_dice_total = d1 + d2
        p["jail_turns"] += 1
        # exit jail for free if doubles are rolled
        if d1 == d2:
            p["in_jail"] = False
            p["jail_turns"] = 0
            self._log(f"{p['name']} rolled doubles ({d1},{d2}) and gets out of Jail!")
            new_pos = (p["pos"] + d1 + d2) % 40
            passed_go = new_pos < p["pos"]
            p["pos"] = new_pos
            if passed_go:
                self.pay_from_bank(p, 200)
                self._log(f"{p['name']} passed Go, collected $200.")
            self.resolve_space(p)
        # pay $50 fee and leave after failing 3 double rolls
        elif p["jail_turns"] >= 3:
            self._log(f"{p['name']} failed to roll doubles 3 times — pays $50 and leaves Jail.")
            self.pay_to_bank(p, 50)
            p["in_jail"] = False
            p["jail_turns"] = 0
            if not p["bankrupt"]:
                new_pos = (p["pos"] + d1 + d2) % 40
                passed_go = new_pos < p["pos"]
                p["pos"] = new_pos
                if passed_go:
                    self.pay_from_bank(p, 200)
                    self._log(f"{p['name']} passed Go, collected $200.")
                self.resolve_space(p)
            else:
                self.after_resolve()
        else:
            self._log(f"{p['name']} rolled ({d1},{d2}) — still in Jail. ({p['jail_turns']}/3 attempts)")
            self.doubles_count = 0
            self.turn_phase = "must_end_turn"
        return {"d1": d1, "d2": d2}

    # pay $50 to exit jail immediately without rolling
    def pay_jail_fee(self):
        p = self.cur()
        if not p["in_jail"]:
            raise GameError("Not in jail.")
        if p["money"] < 50:
            raise GameError("Not enough cash.")
        self.pay_to_bank(p, 50)
        p["in_jail"] = False
        p["jail_turns"] = 0
        self._log(f"{p['name']} paid $50 to get out of Jail.")
        self.turn_phase = "start"

    # use special card to get out of jail for free
    def use_goojf(self):
        p = self.cur()
        if not p["in_jail"] or not p["goojf"]:
            raise GameError("No card available.")
        card_type = p["goojf"].pop()
        discard = self.chance_discard if card_type == "chance" else self.community_discard
        cards = CHANCE_CARDS if card_type == "chance" else COMMUNITY_CARDS
        idx = next(i for i, c in enumerate(cards) if c.get("keep"))
        discard.append(idx)
        p["in_jail"] = False
        p["jail_turns"] = 0
        self._log(f"{p['name']} used a Get Out of Jail Free card.")
        self.turn_phase = "start"

    # finish current player turn and move to next player
    def end_turn(self):
        if self.turn_phase == "game_over":
            raise GameError("Game over.")
        self.doubles_count = 0
        self.turn_phase = "start"
        self.stats["turns"] += 1
        nxt = self.current_index
        # find next player who is not bankrupt
        for _ in range(len(self.players)):
            nxt = (nxt + 1) % len(self.players)
            if not self.players[nxt]["bankrupt"]:
                break
        self.current_index = nxt
        self.cur()["traded_this_turn"] = False
        self._log(f"— {self.cur()['name']}'s turn —")

    # ---------- buying / auction ----------
    # current player buys land space currently pending
    def buy_property(self):
        if self.turn_phase != "awaiting_buy" or not self.pending:
            raise GameError("No property to buy right now.")
        p = self.cur()
        s = self.spaces[self.pending["space_id"]]
        if p["money"] < s["price"]:
            raise GameError("Not enough cash.")
        p["money"] -= s["price"]
        self.bank_money += s["price"]
        s["owner"] = p["id"]
        self._log(f"{p['name']} bought {s['name']} for ${s['price']}.")
        self.after_resolve()

    # current player refuses property so it goes to auction
    def decline_property(self):
        if self.turn_phase != "awaiting_buy" or not self.pending:
            raise GameError("No property to decline right now.")
        p = self.cur()
        s = self.spaces[self.pending["space_id"]]
        self._log(f"{p['name']} declined {s['name']}. Going to auction!")
        self.pending = None
        self.start_auction(s["id"])

    # set up property auction for all active players
    def start_auction(self, space_id):
        bidders = [p["id"] for p in self.alive_players()]
        if not bidders:
            self.after_resolve()
            return
        self.auction = {"space_id": space_id, "bidders": bidders, "current_bid": 1, "highest_bidder": None, "turn_index": 0}
        self.turn_phase = "awaiting_auction"

    # submit a higher cash bid during auction
    def auction_bid(self, amount):
        a = self.auction
        if not a:
            raise GameError("No active auction.")
        bidder_id = a["bidders"][a["turn_index"]]
        player = self.players[bidder_id]
        if amount <= a["current_bid"]:
            raise GameError("Bid must be higher than current bid.")
        if amount > player["money"]:
            raise GameError("Not enough cash.")
        a["current_bid"] = amount
        a["highest_bidder"] = bidder_id
        a["turn_index"] = (a["turn_index"] + 1) % len(a["bidders"])
        self._settle_auction_if_done()

    # drop out of property auction
    def auction_fold(self):
        a = self.auction
        if not a:
            raise GameError("No active auction.")
        bidder_id = a["bidders"][a["turn_index"]]
        a["bidders"].remove(bidder_id)
        if a["turn_index"] >= len(a["bidders"]):
            a["turn_index"] = 0
        self._settle_auction_if_done()

    # check if auction completed and grant space to winning bidder
    def _settle_auction_if_done(self):
        a = self.auction
        if not a:
            return
        # winner is single bidder remaining
        if len(a["bidders"]) == 1 and a["highest_bidder"] is not None:
            winner = self.players[a["bidders"][0]]
            winner["money"] -= a["current_bid"]
            self.bank_money += a["current_bid"]
            self.spaces[a["space_id"]]["owner"] = winner["id"]
            self._log(f"{winner['name']} won the auction for {self.spaces[a['space_id']]['name']} for ${a['current_bid']}!")
            self.auction = None
            self.after_resolve()
        # no bids placed
        elif len(a["bidders"]) == 0:
            self._log(f"No one bid on {self.spaces[a['space_id']]['name']}.")
            self.auction = None
            self.after_resolve()

    # ---------- building / mortgage ----------
    # build house or hotel on property space
    def build_house(self, space_id):
        s = self.spaces[space_id]
        if s["owner"] is None:
            raise GameError("Unowned property.")
        p = self.players[s["owner"]]
        if not self.owns_full_group(p, s["group"]) or s["mortgaged"] or s["houses"] >= 5:
            raise GameError("Cannot build here.")
        group_spaces = [x for x in self.spaces if x.get("group") == s["group"]]
        # houses must be built evenly across group
        if s["houses"] != min(x["houses"] for x in group_spaces):
            raise GameError("Must build evenly across the group.")
        if p["money"] < s["houseCost"]:
            raise GameError("Not enough cash.")
        if s["houses"] < 4 and self.used_houses() >= 32:
            raise GameError("No houses left in the bank.")
        if s["houses"] == 4 and self.used_hotels() >= 12:
            raise GameError("No hotels left in the bank.")
        p["money"] -= s["houseCost"]
        self.bank_money += s["houseCost"]
        s["houses"] += 1
        self._log(f"{p['name']} built a {'hotel' if s['houses']==5 else 'house'} on {s['name']}.")

    # sell house back to bank for half building cost refund
    def sell_house(self, space_id):
        s = self.spaces[space_id]
        if s["owner"] is None or s["houses"] == 0:
            raise GameError("Nothing to sell.")
        p = self.players[s["owner"]]
        group_spaces = [x for x in self.spaces if x.get("group") == s["group"]]
        # houses must be sold evenly across group
        if s["houses"] != max(x["houses"] for x in group_spaces):
            raise GameError("Must sell evenly across the group.")
        refund = s["houseCost"] // 2
        actual = min(refund, self.bank_money)
        s["houses"] -= 1
        p["money"] += actual
        self.bank_money -= actual
        self._log(f"{p['name']} sold a house on {s['name']}.")

    # mortgage property space to get quick cash from bank
    def mortgage(self, space_id):
        s = self.spaces[space_id]
        if s["owner"] is None or s["mortgaged"] or s["houses"] > 0:
            raise GameError("Cannot mortgage this.")
        p = self.players[s["owner"]]
        s["mortgaged"] = True
        payout = min(s["mortgageValue"], self.bank_money)
        p["money"] += payout
        self.bank_money -= payout
        self._log(f"{p['name']} mortgaged {s['name']} for ${payout}.")

    # pay back mortgage plus 10 percent fee to unlock property
    def unmortgage(self, space_id):
        s = self.spaces[space_id]
        if s["owner"] is None or not s["mortgaged"]:
            raise GameError("Cannot unmortgage this.")
        p = self.players[s["owner"]]
        cost = int(-(-s["mortgageValue"] * 1.1 // 1))  # ceil
        if p["money"] < cost:
            raise GameError("Not enough cash.")
        s["mortgaged"] = False
        p["money"] -= cost
        self.bank_money += cost
        self._log(f"{p['name']} paid ${cost} to unmortgage {s['name']}.")

    # ---------- trading ----------
    # create trade offer to swap items with another player
    def propose_trade(self, from_id, to_id, give_props, give_cash, give_goojf, get_props, get_cash, get_goojf, message=""):
        giver = self.players[from_id]
        receiver = self.players[to_id]
        if giver["money"] < give_cash:
            raise GameError("Not enough cash to give.")
        if receiver["money"] < get_cash:
            raise GameError("Partner doesn't have that much cash.")
        offer = dict(from_id=from_id, to_id=to_id, give_props=give_props, give_cash=give_cash,
                     give_goojf=give_goojf, get_props=get_props, get_cash=get_cash, get_goojf=get_goojf,
                     message=message)
        self._log(f"{giver['name']} proposes a trade to {receiver['name']}.")
        # computer player auto evaluates trade offer
        if receiver["is_ai"]:
            decision = self._ai_evaluate_trade(receiver, giver, get_props, get_cash, get_goojf, give_props, give_cash, give_goojf)
            if decision == "accept":
                self._log(f"{receiver['name']} (AI) accepted the trade!")
                self.execute_trade(offer)
            else:
                self._log(f"{receiver['name']} (AI) rejected the trade offer.")
            return {"result": decision}
        # human player must accept or reject
        else:
            self.trade = offer
            self.turn_phase_before_trade = self.turn_phase
            return {"result": "pending"}

        # answer accept or reject to active trade
    def respond_trade(self, accept):
        if not self.trade:
            raise GameError("No pending trade.")
        offer = self.trade
        self.trade = None
        if accept:
            self.execute_trade(offer)
        else:
            to_p = self.players[offer["to_id"]]
            self._log(f"{to_p['name']} rejected the trade offer.")

    # swap cash properties and jail cards between trade players
    def execute_trade(self, offer):
        p1 = self.players[offer["from_id"]]
        p2 = self.players[offer["to_id"]]
        if p1["money"] < offer["give_cash"] or p2["money"] < offer["get_cash"]:
            raise GameError("Trade failed: insufficient cash.")
        # transfer cash
        if offer["give_cash"] > 0:
            p1["money"] -= offer["give_cash"]
            p2["money"] += offer["give_cash"]
        if offer["get_cash"] > 0:
            p2["money"] -= offer["get_cash"]
            p1["money"] += offer["get_cash"]
        # transfer get out of jail cards
        if offer["give_goojf"] and p1["goojf"]:
            p2["goojf"].append(p1["goojf"].pop())
        if offer["get_goojf"] and p2["goojf"]:
            p1["goojf"].append(p2["goojf"].pop())
        # transfer property space ownership
        for sid in offer["give_props"]:
            self.spaces[sid]["owner"] = p2["id"]
        for sid in offer["get_props"]:
            self.spaces[sid]["owner"] = p1["id"]
        self.stats["trades"] += 1
        self._log(f"Trade completed successfully between {p1['name']} and {p2['name']}!")

    # ---------- AI ----------
    # calculate extra safe money buffer for computer player choices
    def ai_cash_buffer(self, p):
        owned = sum(1 for s in self.spaces if s["owner"] is not None)
        ownable = sum(1 for s in self.spaces if s.get("price"))
        pct = owned / max(ownable, 1)
        phase_mult = 0.4 if pct < 0.5 else (0.7 if pct < 0.85 else 1.0)
        buffer = max(50, p["money"] * 0.06) * phase_mult
        if p["in_jail"]:
            buffer *= 0.6
        return min(buffer, 400)

    # calculate value of stopping opponent monopoly set
    def ai_defensive_value(self, p, space):
        if space["type"] != "property":
            return 0
        val = 0
        for o in self.players:
            if o["id"] == p["id"] or o["bankrupt"]:
                continue
            spaces_in_group = [s for s in self.spaces if s.get("group") == space["group"]]
            owned = sum(1 for s in spaces_in_group if s["owner"] == o["id"])
            total = len(spaces_in_group)
            if owned == total - 1:
                val += 140 * self.group_weight(space)
            elif owned > 0:
                val += 35 * self.group_weight(space)
        return val

    # evaluate if computer player should buy landed space
    def ai_should_buy(self, p, space):
        if p["money"] < space["price"]:
            return False
        buffer = self.ai_cash_buffer(p)
        after_buy = p["money"] - space["price"]
        weight = self.group_weight(space)
        if space["type"] == "property":
            spaces_in_group = [s for s in self.spaces if s.get("group") == space["group"]]
            owned = sum(1 for s in spaces_in_group if s["owner"] == p["id"])
            total = len(spaces_in_group)
            if owned == total - 1:
                weight *= 3.0
            elif owned > 0:
                weight *= 1.8
        if space["type"] == "railroad" and self.railroads_owned(p) >= 1:
            weight *= 1.6
        if space.get("group") == "brown":
            weight *= 0.75
        if space["type"] == "utility":
            weight *= 0.6
        weight += self.ai_defensive_value(p, space) / max(space["price"], 1)
        if after_buy < buffer:
            weight *= 0.85
        return weight >= 0.35 and after_buy >= -50

    # check if computer player accepts or rejects trade offer
    def _ai_evaluate_trade(self, me, other, i_give_props, i_give_cash, i_give_goojf, i_get_props, i_get_cash, i_get_goojf):
        if me["money"] < i_give_cash:
            return "reject"
        completes_opp_monopoly = False
        for sid in i_give_props:
            s = self.spaces[sid]
            if s["type"] != "property":
                continue
            spaces_in_group = [x for x in self.spaces if x.get("group") == s["group"]]
            owned_after = sum(1 for x in spaces_in_group if x["owner"] == other["id"] or x["id"] in i_give_props)
            if owned_after >= len(spaces_in_group):
                completes_opp_monopoly = True
        breaks_own_monopoly = any(
            self.spaces[sid]["type"] == "property" and self.owns_full_group(me, self.spaces[sid]["group"])
            for sid in i_give_props
        )
        give_val = i_give_cash + sum(self.property_value(self.spaces[sid]) * self.group_weight(self.spaces[sid]) for sid in i_give_props) + (60 if i_give_goojf else 0)
        get_val = i_get_cash + sum(self.property_value(self.spaces[sid]) * self.group_weight(self.spaces[sid]) for sid in i_get_props) + (60 if i_get_goojf else 0)
        if me["money"] - i_give_cash < -100:
            return "reject"
        if completes_opp_monopoly or breaks_own_monopoly:
            return "accept" if get_val >= give_val * 1.3 else "reject"
        return "accept" if get_val >= give_val * 0.95 else "reject"

    # calculate top maximum bid computer player will offer in auction
    def ai_auction_max_bid(self, p, space):
        weight = self.group_weight(space)
        if space["type"] == "property":
            spaces_in_group = [s for s in self.spaces if s.get("group") == space["group"]]
            owned = sum(1 for s in spaces_in_group if s["owner"] == p["id"])
            total = len(spaces_in_group)
            if owned == total - 1:
                weight *= 3.2
            elif owned > 0:
                weight *= 2.0
        max_val = space["price"] * weight * 2.2
        buffer = self.ai_cash_buffer(p) * 0.3
        return max(min(max_val, p["money"] - buffer), 0)

    # computer player automatically builds houses on full set spaces
    def ai_manage_buildings(self, p):
        buffer = self.ai_cash_buffer(p) * 0.15
        cash_limit = max(0, p["money"] - buffer)
        my_groups = set(s["group"] for s in self.spaces if s["type"] == "property" and s["owner"] == p["id"])
        my_groups = [g for g in my_groups if self.owns_full_group(p, g) and not any(s["mortgaged"] for s in self.spaces if s.get("group") == g)]
        guard = 0
        while cash_limit > 0 and guard < 60:
            guard += 1
            built = False
            for g in my_groups:
                gs = [s for s in self.spaces if s.get("group") == g]
                min_h = min(s["houses"] for s in gs)
                if min_h >= 5:
                    continue
                target = next(s for s in gs if s["houses"] == min_h)
                if target["houseCost"] > cash_limit:
                    continue
                if target["houses"] < 4 and self.used_houses() >= 32:
                    continue
                if target["houses"] == 4 and self.used_hotels() >= 12:
                    continue
                p["money"] -= target["houseCost"]
                self.bank_money += target["houseCost"]
                target["houses"] += 1
                cash_limit -= target["houseCost"]
                self._log(f"{p['name']} (AI) built a {'hotel' if target['houses']==5 else 'house'} on {target['name']}.")
                built = True
            if not built:
                break

    # computer player pays off mortgaged spaces if extra money is ready
    def ai_manage_mortgages(self, p):
        buffer = self.ai_cash_buffer(p)
        mortgaged = sorted([s for s in self.spaces if s["owner"] == p["id"] and s["mortgaged"]],
                            key=lambda s: s["mortgageValue"])
        for s in mortgaged:
            cost = int(-(-s["mortgageValue"] * 1.1 // 1))
            if p["money"] - cost < buffer:
                break
            p["money"] -= cost
            self.bank_money += cost
            s["mortgaged"] = False
            self._log(f"{p['name']} (AI) paid ${cost} to unmortgage {s['name']}.")

    # computer player checks if sending a trade request helps get full sets
    def ai_maybe_propose_trade(self, p):
        my_groups = set(s["group"] for s in self.spaces if s["owner"] == p["id"] and s["type"] == "property")
        best = None
        best_score = -1
        for g in my_groups:
            gs = [s for s in self.spaces if s.get("group") == g]
            owned = sum(1 for s in gs if s["owner"] == p["id"])
            total = len(gs)
            others_owned = [s for s in gs if s["owner"] is not None and s["owner"] != p["id"]]
            if 0 < owned < total and others_owned:
                for s in others_owned:
                    score = self.group_weight(s) * (owned / total) * (2 if owned == total - 1 else 1)
                    if score > best_score:
                        best_score = score
                        best = s
        if not best:
            return
        owner = self.players[best["owner"]]
        if owner["bankrupt"]:
            return
        basic_price = best.get("price", self.property_value(best))
        offer_cash = min(max(0, int(basic_price * 1.1)), max(0, p["money"] - self.ai_cash_buffer(p)))
        if offer_cash <= 0:
            return
        self.propose_trade(p["id"], owner["id"], [], offer_cash, False, [best["id"]], 0, False,
                            "Let's make a deal.")

    # run complete turn loop steps for computer controlled player
    def ai_play_full_turn(self):
        p = self.cur()
        if not p["is_ai"] or p["bankrupt"] or self.turn_phase == "game_over":
            return
        guard = 0
        if not p.get("traded_this_turn"):
            p["traded_this_turn"] = True
            if random.random() < 0.7:
                self.ai_maybe_propose_trade(p)
        while guard < 40:
            guard += 1
            if self.turn_phase == "game_over":
                return
            if self.turn_phase == "awaiting_auction":
                a = self.auction
                bidder_id = a["bidders"][a["turn_index"]]
                bidder = self.players[bidder_id]
                if bidder["is_ai"]:
                    self._ai_auction_step(bidder)
                    continue
                else:
                    return
            if self.turn_phase == "awaiting_buy":
                space = self.spaces[self.pending["space_id"]]
                if self.ai_should_buy(p, space):
                    self.buy_property()
                else:
                    self.decline_property()
                continue
            if self.turn_phase == "must_end_turn":
                self.ai_manage_mortgages(p)
                self.ai_manage_buildings(p)
                self.end_turn()
                return
            if p["in_jail"]:
                if p["goojf"]:
                    self.use_goojf()
                elif p["money"] >= 50:
                    self.pay_jail_fee()
                else:
                    self.roll_dice()
                    if self.turn_phase == "must_end_turn":
                        continue
                continue
            if self.turn_phase in ("start", "must_roll_again"):
                self.roll_dice()
                continue
            break

    # execute computer player bid or fold action inside property auction
    def _ai_auction_step(self, p):
        a = self.auction
        space = self.spaces[a["space_id"]]
        max_bid = self.ai_auction_max_bid(p, space)
        step = max(1, round(space["price"] * 0.05))
        next_bid = a["current_bid"] + step
        if next_bid <= max_bid and next_bid <= p["money"]:
            self.auction_bid(next_bid)
        else:
            self._log(f"{p['name']} (AI) folds from the auction.")
            self.auction_fold()

    # ---------- serialization ----------
    # package game variables into simple dictionary list format
    def serialize(self):
        return {
            "started": self.started,
            "spaces": self.spaces,
            "players": self.players,
            "current_index": self.current_index,
            "bank_money": self.bank_money,
            "free_parking_pot": self.free_parking_pot,
            "turn_phase": self.turn_phase,
            "pending": self.pending,
            "auction": self.auction,
            "trade": self.trade,
            "log": self.log[:50],
            "stats": self.stats,
            "group_colors": GROUP_COLORS,
        }