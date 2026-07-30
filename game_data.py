GROUP_COLORS = {
    "brown": "#955436", "lightblue": "#AAE0FA", "pink": "#D93A96", "orange": "#F7941D",
    "red": "#ED1B24", "yellow": "#FEF200", "green": "#1FB25A", "blue": "#0072BB"
}

RAW_SPACES = [
    {"name": "GO", "type": "go"},
    {"name": "Mediterranean Avenue", "type": "property", "group": "brown", "price": 60, "rent": [2,10,30,90,160,250], "houseCost": 50},
    {"name": "Community Chest", "type": "community"},
    {"name": "Baltic Avenue", "type": "property", "group": "brown", "price": 60, "rent": [4,20,60,180,320,450], "houseCost": 50},
    {"name": "Income Tax", "type": "tax", "amount": 200},
    {"name": "Reading Railroad", "type": "railroad", "price": 200},
    {"name": "Oriental Avenue", "type": "property", "group": "lightblue", "price": 100, "rent": [6,30,90,270,400,550], "houseCost": 50},
    {"name": "Chance", "type": "chance"},
    {"name": "Vermont Avenue", "type": "property", "group": "lightblue", "price": 100, "rent": [6,30,90,270,400,550], "houseCost": 50},
    {"name": "Connecticut Avenue", "type": "property", "group": "lightblue", "price": 120, "rent": [8,40,100,300,450,600], "houseCost": 50},
    {"name": "Jail / Just Visiting", "type": "jail"},
    {"name": "St. Charles Place", "type": "property", "group": "pink", "price": 140, "rent": [10,50,150,450,625,750], "houseCost": 100},
    {"name": "Electric Company", "type": "utility", "price": 150},
    {"name": "States Avenue", "type": "property", "group": "pink", "price": 140, "rent": [10,50,150,450,625,750], "houseCost": 100},
    {"name": "Virginia Avenue", "type": "property", "group": "pink", "price": 160, "rent": [12,60,180,500,700,900], "houseCost": 100},
    {"name": "Pennsylvania Railroad", "type": "railroad", "price": 200},
    {"name": "St. James Place", "type": "property", "group": "orange", "price": 180, "rent": [14,70,200,550,750,950], "houseCost": 100},
    {"name": "Community Chest", "type": "community"},
    {"name": "Tennessee Avenue", "type": "property", "group": "orange", "price": 180, "rent": [14,70,200,550,750,950], "houseCost": 100},
    {"name": "New York Avenue", "type": "property", "group": "orange", "price": 200, "rent": [16,80,220,600,800,1000], "houseCost": 100},
    {"name": "Free Parking", "type": "free"},
    {"name": "Kentucky Avenue", "type": "property", "group": "red", "price": 220, "rent": [18,90,250,700,875,1050], "houseCost": 150},
    {"name": "Chance", "type": "chance"},
    {"name": "Indiana Avenue", "type": "property", "group": "red", "price": 220, "rent": [18,90,250,700,875,1050], "houseCost": 150},
    {"name": "Illinois Avenue", "type": "property", "group": "red", "price": 240, "rent": [20,100,300,750,925,1100], "houseCost": 150},
    {"name": "B&O Railroad", "type": "railroad", "price": 200},
    {"name": "Atlantic Avenue", "type": "property", "group": "yellow", "price": 260, "rent": [22,110,330,800,975,1150], "houseCost": 150},
    {"name": "Ventnor Avenue", "type": "property", "group": "yellow", "price": 260, "rent": [22,110,330,800,975,1150], "houseCost": 150},
    {"name": "Water Works", "type": "utility", "price": 150},
    {"name": "Marvin Gardens", "type": "property", "group": "yellow", "price": 280, "rent": [24,120,360,850,1025,1200], "houseCost": 150},
    {"name": "Go To Jail", "type": "gotojail"},
    {"name": "Pacific Avenue", "type": "property", "group": "green", "price": 300, "rent": [26,130,390,900,1100,1275], "houseCost": 200},
    {"name": "North Carolina Avenue", "type": "property", "group": "green", "price": 300, "rent": [26,130,390,900,1100,1275], "houseCost": 200},
    {"name": "Community Chest", "type": "community"},
    {"name": "Pennsylvania Avenue", "type": "property", "group": "green", "price": 320, "rent": [28,150,450,1000,1200,1400], "houseCost": 200},
    {"name": "Short Line", "type": "railroad", "price": 200},
    {"name": "Chance", "type": "chance"},
    {"name": "Park Place", "type": "property", "group": "blue", "price": 350, "rent": [35,175,500,1100,1300,1500], "houseCost": 200},
    {"name": "Luxury Tax", "type": "tax", "amount": 100},
    {"name": "Boardwalk", "type": "property", "group": "blue", "price": 400, "rent": [50,200,600,1400,1700,2000], "houseCost": 200}
]


def fresh_spaces():
    spaces = []
    for i, s in enumerate(RAW_SPACES):
        sp = dict(s)
        sp["id"] = i
        sp["owner"] = None
        sp["houses"] = 0
        sp["mortgaged"] = False
        if sp.get("price"):
            sp["mortgageValue"] = sp["price"] // 2
        spaces.append(sp)
    return spaces


# Card effects are descriptors: {"action": <name>, ...params}
CHANCE_CARDS = [
    {"text": "Advance to Go. Collect $200.", "action": "advance_to", "dest": 0, "pass_go": True},
    {"text": "Advance to Illinois Avenue. If you pass Go, collect $200.", "action": "advance_to", "dest": 24, "pass_go": True},
    {"text": "Advance to St. Charles Place. If you pass Go, collect $200.", "action": "advance_to", "dest": 11, "pass_go": True},
    {"text": "Advance token to nearest Utility. If unowned, you may buy it. If owned, pay owner 10x your dice roll.", "action": "advance_nearest", "space_type": "utility", "mult": 10},
    {"text": "Advance token to nearest Railroad. If unowned, you may buy it. If owned, pay owner twice the rental due.", "action": "advance_nearest", "space_type": "railroad", "mult": 2},
    {"text": "Advance token to nearest Railroad. If unowned, you may buy it. If owned, pay owner twice the rental due.", "action": "advance_nearest", "space_type": "railroad", "mult": 2},
    {"text": "Bank pays you dividend of $50.", "action": "pay_from_bank", "amount": 50},
    {"text": "Get Out of Jail Free. This card may be kept until needed.", "action": "goojf", "deck": "chance", "keep": True},
    {"text": "Go Back 3 Spaces.", "action": "go_back", "spaces": 3},
    {"text": "Go to Jail. Go directly to Jail, do not pass Go, do not collect $200.", "action": "go_to_jail"},
    {"text": "Make general repairs on all your property: for each house pay $25, for each hotel pay $100.", "action": "repairs", "per_house": 25, "per_hotel": 100},
    {"text": "Speeding fine, pay $15.", "action": "pay_to_bank", "amount": 15},
    {"text": "Take a trip to Reading Railroad. If you pass Go, collect $200.", "action": "advance_to", "dest": 5, "pass_go": True},
    {"text": "Take a walk on the Boardwalk. Advance to Boardwalk.", "action": "advance_to", "dest": 39, "pass_go": False},
    {"text": "You have been elected Chairman of the Board. Pay each player $50.", "action": "pay_each", "amount": 50},
    {"text": "Your building loan matures. Collect $150.", "action": "pay_from_bank", "amount": 150},
]

COMMUNITY_CARDS = [
    {"text": "Advance to Go. Collect $200.", "action": "advance_to", "dest": 0, "pass_go": True},
    {"text": "Bank error in your favor. Collect $200.", "action": "pay_from_bank", "amount": 200},
    {"text": "Doctor's fees. Pay $50.", "action": "pay_to_bank", "amount": 50},
    {"text": "From sale of stock you get $50.", "action": "pay_from_bank", "amount": 50},
    {"text": "Get Out of Jail Free. This card may be kept until needed.", "action": "goojf", "deck": "community", "keep": True},
    {"text": "Go to Jail. Go directly to Jail, do not pass Go, do not collect $200.", "action": "go_to_jail"},
    {"text": "Holiday fund matures. Receive $100.", "action": "pay_from_bank", "amount": 100},
    {"text": "Income tax refund. Collect $20.", "action": "pay_from_bank", "amount": 20},
    {"text": "It is your birthday. Collect $10 from every player.", "action": "collect_each", "amount": 10},
    {"text": "Life insurance matures. Collect $100.", "action": "pay_from_bank", "amount": 100},
    {"text": "Pay hospital fees of $100.", "action": "pay_to_bank", "amount": 100},
    {"text": "Pay school fees of $50.", "action": "pay_to_bank", "amount": 50},
    {"text": "Receive $25 consultancy fee.", "action": "pay_from_bank", "amount": 25},
    {"text": "You are assessed for street repairs: $40 per house, $115 per hotel.", "action": "repairs", "per_house": 40, "per_hotel": 115},
    {"text": "You have won second prize in a beauty contest. Collect $10.", "action": "pay_from_bank", "amount": 10},
    {"text": "You inherit $100.", "action": "pay_from_bank", "amount": 100},
]

GROUP_WEIGHT = {
    "orange": 1.35, "red": 1.3, "blue": 1.2, "lightblue": 1.05, "pink": 0.95,
    "yellow": 0.85, "green": 0.8, "brown": 0.55
}
RAILROAD_WEIGHT = 0.9
UTILITY_WEIGHT = 0.4
