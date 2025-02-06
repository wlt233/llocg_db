import os
import re

import requests

endpoint = "https://llofficial-cardgame.com/wordpress/wp-content/images/texticon/"

with open("cards.json", "r", encoding="utf-8") as f:
    text = f.read()
pattern = r'\{\{(.*?)\|(.*?)\}\}'
matches = list(set(re.findall(pattern, text)))
matches.sort()

for match in matches:
    p = f"./img/icon/{match[0]}"
    url = endpoint + match[0]
    if not os.path.exists(os.path.dirname(p)): os.makedirs(os.path.dirname(p))
    resp = requests.get(url, headers={ "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" })
    with open(p, mode="wb") as f:
        f.write(resp.content)
    print(match, p)

# shabi
for i in range(1, 7):
    url = (f"https://llofficial-cardgame.com/wordpress/wp-content"
           f"/themes/llofficial-cardgame_v1/assets/images/common/common/b_heart0{i}.png")
    p = f"./img/icon/b_heart0{i}.png"
    if not os.path.exists(os.path.dirname(p)): os.makedirs(os.path.dirname(p))
    resp = requests.get(url, headers={ "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" })
    with open(p, mode="wb") as f:
        f.write(resp.content)
    print(p)
    