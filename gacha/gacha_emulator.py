
import json
import random
from collections import defaultdict

with open(f"./json/products.json", "r", encoding="utf8") as f:
    PRODUCTS = json.load(f)

with open(f"./json/cards.json", "r", encoding="utf8") as f:
    CARDS = json.load(f)

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

    _parcel_list = [[rare] for rare in rare_list] + [[] for _ in range(20 - len(rare_list))]
    parcel = []
    for _box_high_list in _parcel_list:
        _box_high_list.append(random.choice(card_rare["PE"])) # 1 PE
        _box_high_list += random.sample(card_rare["L"], k=5)  # 5 L
        # 3 R+ when rare or 4 R+ when not rare
        _box_high_list += random.sample(card_rare["R+"], k=10 - len(_box_high_list))
        
        box = []
        p_list = card_rare["P"].copy()
        random.shuffle(p_list)
        r_list = card_rare["R"].copy()
        random.shuffle(r_list)
        n_list = card_rare["N"].copy()
        random.shuffle(n_list)
        for high in _box_high_list:
            _pack_card_list = [high]
            _pack_card_list += random.sample(p_list, k=1) # 1 P
            _pack_card_list += random.sample(r_list, k=1) # 1 R
            _pack_card_list += random.sample(n_list, k=2) # 2 N
            # random.shuffle(_pack_card_list)
            box.append(_pack_card_list)
        
        if random.random() < 0.0001:
            box[-1] = card_rare["LLE"].copy() # the last pack in box (LLE replace R+)
        random.shuffle(box)
        parcel.append(box)
    random.shuffle(parcel)
    return parcel

if __name__ == "__main__":
    import pprint
    pprint.pprint(gen_parcel("BP01"), sort_dicts=False, width=200)

