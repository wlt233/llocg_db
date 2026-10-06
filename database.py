"""Download Japanese Love Live cards from the official card-list API."""

import argparse
import asyncio
import html
import json
import os
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin

import httpx
from tenacity import retry, stop_after_attempt, wait_random_exponential

BASE = "https://llofficial-cardgame.com/"
API = urljoin(BASE, "manage/card-list-user/")
CARD_IMAGES = urljoin(BASE, "wordpress/wp-content/images/cardlist/")
PRODUCT_IMAGES = urljoin(BASE, "wordpress/wp-content/images/thumb/")
HEADERS = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "referer": BASE}
COLORS = {"桃": "01", "赤": "02", "黄": "03", "緑": "04", "青": "05", "紫": "06", "無": "0"}
CATEGORIES = {"pack": "パック商品", "deck": "デッキ商品", "pr": "PRカード", "other": "その他"}


@retry(stop=stop_after_attempt(20), wait=wait_random_exponential(multiplier=4, min=5, max=60), reraise=True)
async def get_json(client, endpoint, params=None):
    response = await client.get(urljoin(API, endpoint), params=params, headers=HEADERS)
    response.raise_for_status()
    return response.json()


async def fetch_products(client):
    data = await get_json(client, "products")
    groups = data.get("products")
    if not isinstance(groups, list) or not groups:
        raise ValueError("Products API returned no product groups")
    products = {}
    for group in groups:
        for item in group.get("items", []):
            code = item.get("code")
            if not code:
                raise ValueError("Products API returned an item without a code")
            products[code] = {
                "img": urljoin(PRODUCT_IMAGES, item["img"]) if item.get("img") else "",
                "href": urljoin(BASE, item.get("url", "")),
                "product_id": code,
                "title": item.get("name", ""),
                "category": CATEGORIES.get(item.get("type"), item.get("type", "")),
                "release_date": item.get("date", ""),
            }
    if not products:
        raise ValueError("Products API returned no products")
    print(f"{len(products)} products fetched")
    return products


async def fetch_product_cards(client, semaphore, code):
    cards = []
    page = 1
    while True:
        async with semaphore:
            data = await get_json(client, "list", {"expansion": code, "page": page, "per_page": 100, "sort": "no"})
        items, total = data.get("items"), data.get("total")
        if not isinstance(items, list) or not isinstance(total, int):
            raise ValueError(f"Invalid card list for {code}, page {page}")
        if not items and len(cards) < total:
            raise ValueError(f"Card list ended early for {code}, page {page}")
        for item in items:
            if not item.get("id") or not item.get("card_number"):
                raise ValueError(f"Card without id or number in {code}")
            cards.append(item)
        if len(cards) >= total:
            break
        page += 1
    print(f"{code}: {len(cards)} cards fetched")
    return code, cards


def heart_counts(raw):
    counts = {}
    for index in range(7):
        key = "heart0" if index == 0 else f"heart{index:02d}"
        count = int(raw.get(key) or 0)
        if count:
            counts[key] = count
    if not counts:
        for color, count in re.findall(r"([桃赤黄緑青紫無])(\d+)", str(raw.get("heart") or "")):
            key = "heart" + COLORS[color]
            counts[key] = counts.get(key, 0) + int(count)
    return counts


def blade_hearts(value):
    counts = {}
    for color, count in re.findall(r"(ALL|桃|赤|黄|緑|青|紫|無)(\d+)", str(value or "")):
        key = "b_all" if color == "ALL" else "b_heart" + ("07" if color == "無" else COLORS[color])
        counts[key] = counts.get(key, 0) + int(count)
    return counts


def format_text(value, icons, markup=False):
    value = str(value or "")
    if markup:
        def image_token(match):
            tag = match.group()
            src = re.search(r'\bsrc=["\']([^"\']+)', tag)
            alt = re.search(r'\balt=["\']([^"\']*)', tag)
            if not src:
                return ""
            return "{{" + PurePosixPath(src.group(1)).name + "|" + html.unescape(alt.group(1) if alt else "") + "}}"
        value = re.sub(r"<img\b[^>]*>", image_token, value, flags=re.I)
        value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
        value = re.sub(r"<[^>]+>", "", value)
    else:
        tokens = [token for token in icons if token.startswith(("【", "["))]
        if tokens:
            pattern = re.compile("|".join(re.escape(token) for token in sorted(tokens, key=len, reverse=True)))
            value = pattern.sub(
                lambda match: "{{" + icons[match.group()] + "|" + match.group().strip("【】[]") + "}}",
                value,
            )
    return html.unescape(value).strip()


def convert_card(data, series_map=None):
    raw = data.get("card")
    if not isinstance(raw, dict) or not raw.get("card_number") or not raw.get("picture"):
        raise ValueError("Card detail API returned an incomplete card")
    icons = data.get("textIcons") or {}
    card = {
        "card_no": raw["card_number"],
        "img": urljoin(CARD_IMAGES, raw["picture"]),
        "name": raw.get("card_name", ""),
        "product": " / ".join(expansion.get("name", "") for expansion in data.get("expansions", []) if expansion.get("name")),
        "type": raw.get("card_kind", ""),
        "rare": raw.get("rare", ""),
    }
    if raw.get("work_title") not in (None, "", "-"):
        card["series"] = "\n".join(
            (series_map or {}).get(part.strip(), part.strip())
            for part in raw["work_title"].split("/") if part.strip()
        )
    if raw.get("unit_name") not in (None, "", "-"):
        card["unit"] = raw["unit_name"]

    hearts = heart_counts(raw)
    if card["type"] == "ライブ":
        if str(raw.get("blade_heart") or "").isdigit():
            card["score"] = int(raw["blade_heart"])
        if hearts:
            card["need_heart"] = hearts
        blade = blade_hearts(raw.get("blade") or raw.get("attack"))
        if blade:
            card["blade_heart"] = blade
        special = {}
        for name, count in re.findall(r"(スコア|ドロー)(\d*)", str(raw.get("cost") or "")):
            key = "score" if name == "スコア" else "draw"
            special[key] = special.get(key, 0) + int(count or 1)
        if special:
            card["special_heart"] = special
    elif card["type"] == "メンバー":
        if str(raw.get("cost") or "").isdigit():
            card["cost"] = int(raw["cost"])
        if hearts:
            card["base_heart"] = hearts
        blade = blade_hearts(raw.get("blade_heart"))
        if blade:
            card["blade_heart"] = blade
        blade_count = raw.get("blade") or raw.get("attack")
        if str(blade_count or "").isdigit():
            card["blade"] = int(blade_count)

    ability = raw.get("text_html") or raw.get("text")
    if ability and ability != "-":
        card["ability"] = format_text(ability, icons, markup=bool(raw.get("text_html")))

    card["faq"] = []
    for item in data.get("faqs", []):
        date = item.get("update_time") or item.get("date") or ""
        title = f"Q{item.get('qa_id', '')}" + (f"（{date.replace('-', '.')}）" if date else "")
        relation = [
            {"card_no": number.strip(), "name": name.strip()}
            for number, name in re.findall(r"\[([^\[\]：]+)\s*：\s*([^\[\]]+)\]", item.get("card_names") or "")
        ]
        card["faq"].append({
            "title": title,
            "question": format_text(item.get("question"), icons),
            "answer": format_text(item.get("answer"), icons),
            "relation": relation,
        })
    card["rare_list"] = [{"card_no": card["card_no"], "name": card["name"]}]
    card["rare_list"].extend(
        {"card_no": item["card_number"], "name": item.get("card_name", "")}
        for item in data.get("relationCards", []) if item.get("card_number")
    )
    return card


async def fetch_card_info(client, semaphore, item, series_map):
    async with semaphore:
        data = await get_json(client, "detail", {"id": item["id"]})
    card = convert_card(data, series_map)
    if card["card_no"] != item["card_number"]:
        raise ValueError(f"Detail/list mismatch for card id {item['id']}")
    return card


async def download_image(client, semaphore, url, path):
    target = Path(path)
    if target.exists():
        return
    async with semaphore:
        try:
            response = await get_image(client, url)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(response.content)
        except httpx.HTTPError as error:
            print(f"Image download failed: {url}: {error}")


@retry(stop=stop_after_attempt(10), wait=wait_random_exponential(multiplier=4, min=5, max=60), reraise=True)
async def get_image(client, url):
    response = await client.get(url, headers=HEADERS)
    response.raise_for_status()
    return response


async def download_missing_images():
    products = json.loads(Path("json/products.json").read_text(encoding="utf-8"))
    cards = json.loads(Path("json/cards.json").read_text(encoding="utf-8"))
    images = [(item["img"], item["_img"]) for item in (*products.values(), *cards.values())
              if item.get("img") and item.get("_img") and not Path(item["_img"]).exists()]
    print(f"{len(images)} missing images")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        semaphore = asyncio.Semaphore(3)
        await asyncio.gather(*(download_image(client, semaphore, url, path) for url, path in images))


def write_json(path, data):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=4, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, target)


async def main(download_images=True):
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        products = await fetch_products(client)
        form = await get_json(client, "createSearchForm")
        series_map = form.get("legacy", {}).get("work_title_display_by_value", {})
        list_semaphore = asyncio.Semaphore(4)
        lists = await asyncio.gather(*(fetch_product_cards(client, list_semaphore, code) for code in products))
        unique = {}
        for code, items in lists:
            products[code]["card_list"] = [item["card_number"] for item in items]
            for item in items:
                unique[item["card_number"]] = item
        if not unique:
            raise ValueError("Card API returned no cards; existing JSON files were kept")

        semaphore = asyncio.Semaphore(3)
        tasks = [asyncio.create_task(fetch_card_info(client, semaphore, item, series_map))
                 for item in unique.values()]
        details = []
        for count, task in enumerate(asyncio.as_completed(tasks), 1):
            details.append(await task)
            if count % 100 == 0:
                print(f"{count}/{len(tasks)} card details fetched")
        cards = {card["card_no"]: card for card in details}
        images = []
        for product in products.values():
            if product["img"]:
                path = "img/products/" + product["img"].rsplit("/", 1)[-1]
                product["_img"] = path
                images.append((product["img"], path))
        for card in cards.values():
            picture = card["img"].removeprefix(CARD_IMAGES)
            parts = PurePosixPath(picture).parts
            if picture.startswith("/") or any(part in (".", "..") for part in parts):
                raise ValueError(f"Invalid image path: {picture!r}")
            path = str(Path("img/cards", *parts)).replace("\\", "/")
            card["_img"] = path
            images.append((card["img"], path))

        write_json("json/products.json", products)
        write_json("json/cards.json", cards)
        print(f"Saved {len(products)} products and {len(cards)} cards")
        if download_images:
            await asyncio.gather(*(download_image(client, semaphore, url, path) for url, path in images))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-images", action="store_true", help="Update JSON without downloading images")
    parser.add_argument("--images-only", action="store_true", help="Download missing images from existing JSON files")
    args = parser.parse_args()
    if args.images_only:
        asyncio.run(download_missing_images())
    else:
        asyncio.run(main(download_images=not args.skip_images))
