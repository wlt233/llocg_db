
import json
import random
from collections import defaultdict

with open(f"./json/products.json", "r", encoding="utf8") as f:
    PRODUCTS = json.load(f)

with open(f"./json/cards.json", "r", encoding="utf8") as f:
    CARDS = json.load(f)

def pops(l, n):
    r = l[:n]
    del l[:n]
    return r

def gen_parcel(colle):
    card_list = PRODUCTS[colle]["card_list"]
    card_rare = defaultdict(list)
    for card_no in card_list:
        card_rare[CARDS[card_no]["rare"]].append(card_no)
    
    sece_num = (1 if random.random() < 0.005 else 0)
    sece_list = random.sample(card_rare["SECE"], k=sece_num)
    sec_num = 1 + (1 if random.random() < 0.05 else 0)
    sec_list = random.sample(card_rare["SEC"], k=sec_num)
    pe2_num = 3 + (1 if random.random() < 0.1 else 0)
    pe2_list = random.sample(card_rare["PE+"], k=pe2_num)
    p2_num = 4 + (1 if random.random() < 0.1 else 0)
    p2_list = random.sample(card_rare["P+"], k=p2_num)
    rare_list = sece_list + sec_list + pe2_list + p2_list
    random.shuffle(rare_list)

    shiny_list = (card_rare["R"] + card_rare["R+"] + card_rare["P"] + card_rare["L"]) * 8
    random.shuffle(shiny_list)
    normal_list = card_rare["N"] * 15
    random.shuffle(normal_list)
    def gen_pack_fill():
        fill = pops(shiny_list, 3) + pops(normal_list, 2)
        random.shuffle(fill)
        return fill
    
    _parcel_list = rare_list + [""] * (1000 - len(rare_list))
    random.shuffle(_parcel_list)
    parcel = []
    while _parcel_list:
        _box_list = pops(_parcel_list, 50)
        _box_list.remove("")
        _box_list.append(random.choice(card_rare["PE"]))
        random.shuffle(_box_list)
        
        box = []
        while _box_list:
            _pack_list = pops(_box_list, 5)
            _pack_fill = gen_pack_fill()
            while "" in _pack_list:
                _pack_list[_pack_list.index("")] = _pack_fill.pop()
            if random.random() < 0.0001:
                _pack_list = card_rare["LLE"].copy()
            box.append(_pack_list)
        parcel.append(box)
        
    return parcel

if __name__ == "__main__":
    import pprint
    pprint.pprint(gen_parcel("BP01"), sort_dicts=False, width=200)

