
import asyncio
import json
import pprint
import re

import httpx


headers = { "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" }


async def fetch_product(client):
    url = f"https://llofficial-cardgame.com/cardlist/"
    resp = await client.get(url, headers=headers)
    text = resp.text
    products_text = re.findall(r'<a class="productsList-Item.*?">.*?</a>', text, re.DOTALL)
    products = []
    for product_text in products_text:
        product = {}
        if img := re.search(r'<img src="(.*?)"', product_text, re.DOTALL):
            if img[1].startswith("http"):
                product["img"] = img[1]
            else:
                product["img"] = "https://llofficial-cardgame.com" + img[1]
        if href := re.search(r'href="(.*?)"', product_text, re.DOTALL):
            product["href"] = "https://llofficial-cardgame.com" + href[1]
        if product_id := re.search(r'expansion=(.*?)"', product_text, re.DOTALL):
            product["product_id"] = product_id[1]
        if title := re.search(r'<p class="item-Title">(.*?)</p>', product_text, re.DOTALL):
            product["title"] = title[1]
        if category := re.search(r'<span class="category">(.*?)</span>', product_text, re.DOTALL):
            product["category"] = category[1]
        if release_date := re.search(r'<p class="info-Text">(.*?)</p>', product_text, re.DOTALL):
            product["release_date"] = release_date[1]
        else:
            product["release_date"] = ""
        products.append(product)
    products.sort(key=lambda x: x["release_date"])
    print(f"{len(products)} products fetched")
    return products


async def fetch_card_no_list(client, product_id: str):
    page = 0
    card_list = []
    while 1:
        page += 1
        url = (f"https://llofficial-cardgame.com/cardlist/cardsearch_ex"
               f"?expansion={product_id}&view=text&page={page}&limit=100") # limit max: 100
        resp = await client.get(url, headers=headers)
        text = resp.text
        if 'http-equiv="Refresh"' in text:
            break
        card_list += re.findall(r'card="(.*?)"', text, re.DOTALL)
    print(f"{product_id} {len(card_list)} cards fetched")
    return (product_id, card_list)




def parse_html(html_text):
    html_text = re.sub(r'<img[^>]*src="[^"]*/([^"/]+)"[^>]*alt="([^"]+)"[^>]*>',
                       r'{{\1|\2}}', html_text)
    html_text = re.sub(r'\s+', '', html_text).strip()
    html_text = re.sub(r'<br\s*/?>', '\n', html_text)
    return html_text

attr_name = {
    '収録商品': 'product',
    'カードタイプ': 'type',
    '作品名': 'series',
    '参加ユニット': 'unit',
    'コスト': 'cost',
    'ブレード': 'blade',
    'スコア': 'score',
    '基本ハート': 'base_heart',
    '必要ハート': 'need_heart',
    'ブレードハート': 'blade_heart',
    'レアリティ': 'rarity',
}

async def fetch_card_info(client, semaphore, card_no: str):
    url = f"https://llofficial-cardgame.com/cardlist/detail/"
    data = {
        "cardno": card_no
    }
    async with semaphore:
        resp = await client.post(url, headers=headers, data=data)
        text = resp.text
    card_info = {}
    card_info["card_no"] = card_no
    
    # img
    if img := re.search(r'<div class="image"><img src="(.*?)"', text, re.DOTALL):
        if img[1].startswith("http"):
            card_info["img"] = img[1]
        else:
            card_info["img"] = "https://llofficial-cardgame.com" + img[1]
    
    # name
    if name := re.search(r'<p class="info-Heading">(.*?)</p>', text, re.DOTALL):
        card_info["name"] = name[1]
    
    # info detail
    info_items = re.findall(r'<div class="dl-Item">.*?<dt><span>(.*?)</span></dt>.*?<dd>(.*?)</dd>', 
                            text, re.DOTALL)
    for info in info_items:
        card_info[attr_name.get(info[0], info[0])] = parse_html(info[1])
    for key in ["base_heart", "need_heart", "blade_heart"]:
        if key in card_info:
            card_info[key] = card_info[key].replace(
                r"{{icon_b_all.png|ALL1}}", 
                r'<spanclass="iconb_all">1</span>')
            hearts = re.findall(r'<span\s*class="[^"]*\bicon\s*([^"]+)\b[^"]*">([^<]*)</span>', 
                                card_info[key], re.DOTALL)
            card_info[key] = {key: (int(value) if value else 1) for key, value in hearts}
    if "blade" in card_info: card_info["blade"] = int(card_info["blade"])
    if "cost" in card_info: card_info["cost"] = int(card_info["cost"])
    if "score" in card_info: card_info["score"] = int(card_info["score"])
    
    # ability
    if ability := re.search(r'<p class="info-Text">(.*?)</p>', text, re.DOTALL):
        card_info["ability"] = parse_html(ability[1])
    
    # faq
    card_info["faq"] = []
    faq_items = re.findall(r'<div class="faq-Item">(.*?)</div>', text, re.DOTALL)
    for faq_text in faq_items:
        faq = {}
        if title := re.search(r'Modal_Heading">(.*?)</p>', faq_text, re.DOTALL):
            faq["title"] = title[1]
        if question := re.search(r'question">(.*?)</p>', faq_text, re.DOTALL):
            faq["question"] = parse_html(question[1])
        if answer := re.search(r'answer">(.*?)</p>', faq_text, re.DOTALL):
            faq["answer"] = parse_html(answer[1])
        faq["relation"] = []
        for relation in re.findall(r'\[(.*?)：(.*?)\]', faq_text, re.DOTALL):
            faq["relation"].append({
                "card_no": relation[0].strip(),
                "name": relation[1].strip()
            })
        card_info["faq"].append(faq)
    
    # rarity list
    card_info["rarity_list"] = [{
        "card_no": card_info["card_no"],
        "name": card_info["name"]
    }]
    rarity_items = re.findall(r"""relatedCard\('(.*?)', .*?alt="(.*?)"/>""", text, re.DOTALL)
    for rarity_item in rarity_items:
        card_info["rarity_list"].append({
            "card_no": rarity_item[0].strip(),
            "name": rarity_item[1].strip()
        })
    
    print(f"{card_info['card_no']} {card_info['name']} fetched")
    return card_info



async def main():
    # async with httpx.AsyncClient(timeout=None) as client:
    #     pprint.pprint(await fetch_card_info(client, asyncio.Semaphore(10), "PL!N-bp1-012-R＋"),sort_dicts=False)
    
    async with httpx.AsyncClient(timeout=None) as client:
        product_list = await fetch_product(client)
        products = { product["product_id"]: product for product in product_list }
        
        all_card_no = []
        card_no_lists = await asyncio.gather(
            *(fetch_card_no_list(client, product["product_id"]) for product in product_list)
        )
        for product_id, card_no_list in card_no_lists:
            products[product_id]["card_list"] = card_no_list
            all_card_no += card_no_list
        with open("products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, indent=4, ensure_ascii=False)
        
        cards = { card_no: {} for card_no in all_card_no }
        semaphore = asyncio.Semaphore(10)
        card_info_lists = await asyncio.gather(
            *(fetch_card_info(client, semaphore, card_no) for card_no in all_card_no)
        )
        for card_info in card_info_lists:
            cards[card_info["card_no"]] = card_info
        with open("cards.json", "w", encoding="utf-8") as f:
            json.dump(cards, f, indent=4, ensure_ascii=False)



if __name__ == "__main__":
    asyncio.run(main())
