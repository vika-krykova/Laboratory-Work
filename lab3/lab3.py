#!/usr/bin/env python3

import argparse
import json
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "WikimediaLab3/1.0 (student-project; contact@example.com)"
}

DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://commons.wikimedia.org/",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

API = {
    "wikipedia": "https://{lang}.wikipedia.org/w/api.php",
    "wikidata": "https://www.wikidata.org/w/api.php",
    "wiktionary": "https://{lang}.wiktionary.org/w/api.php",
    "commons": "https://commons.wikimedia.org/w/api.php",
}

LANG_MAP = {
    "en": "en-GB",
    "ru": "ru-RU",
    "de": "de-DE",
    "fr": "fr-FR",
    "es": "es-ES",
    "it": "it-IT",
    "uk": "uk-UA",
    "zh": "zh-CN",
    "ja": "ja-JP",
    "pl": "pl-PL",
}


def api_get(url, params, max_attempts=5):
    params.setdefault("format", "json")
    params.setdefault("formatversion", 2)

    for attempt in range(max_attempts):
        try:
            response = requests.get(
                url, params=params, headers=HEADERS, timeout=30
            )

            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  429, ждем {wait} сек (попытка {attempt + 1}/{max_attempts})...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            return response.json()

        except (requests.Timeout, requests.ConnectionError) as e:
            wait = 5 * (attempt + 1)
            print(f"  Сетевая ошибка: {type(e).__name__}, "
                  f"ждем {wait} сек (попытка {attempt + 1}/{max_attempts})...")
            time.sleep(wait)

    raise requests.HTTPError(f"Не удалось получить {url} после {max_attempts} попыток")


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["style", "script", "table"]):
        tag.decompose()
    return soup.get_text(" ", strip=True)


def extract_html(parse_data):
    html = parse_data.get("text", "")
    if isinstance(html, dict):
        html = html.get("*", "")
    return html


def translate_text(text, source="auto", target="ru"):
    if not text or not text.strip():
        return text

    if source == "auto":
        source = "en"

    source = LANG_MAP.get(source, source)
    target = LANG_MAP.get(target, target)

    try:
        from deep_translator import MyMemoryTranslator
        chunks = [text[i:i + 450] for i in range(0, len(text), 450)]
        result = []
        for i, chunk in enumerate(chunks):
            if i > 0:
                time.sleep(0.5)
            try:
                translated = MyMemoryTranslator(source=source, target=target).translate(chunk)
                result.append(translated or chunk)
            except Exception as e:
                print(f"  Ошибка перевода куска: {e}")
                result.append(chunk)
        return " ".join(result)
    except Exception as e:
        print(f"  Ошибка перевода: {e}")
        return text


def search_wikipedia(query, lang):
    url = API["wikipedia"].format(lang=lang)
    data = api_get(url, {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": 1,
    })
    results = data.get("query", {}).get("search", [])
    return results[0]["title"] if results else None


def get_wikipedia_article(title, lang, text_limit=5000, translate_to=None):
    url = API["wikipedia"].format(lang=lang)
    data = api_get(url, {
        "action": "parse",
        "page": title,
        "prop": "text|links|images|externallinks",
        "redirects": 1,
    })

    if "error" in data:
        return None

    parse = data["parse"]
    text = html_to_text(extract_html(parse))

    links = []
    for item in parse.get("links", []):
        if item.get("ns") == 0 and "title" in item:
            t = item["title"]
            if t not in links:
                links.append(t)

    images = []
    for item in parse.get("images", []):
        if isinstance(item, dict):
            t = item.get("title")
        else:
            t = item
        if t and t not in images:
            images.append(t)

    external = parse.get("externallinks", [])
    title_final = parse.get("title", title)

    if translate_to and lang != translate_to:
        title_final = translate_text(title_final, source=lang, target=translate_to)
        time.sleep(0.5)
        text = translate_text(text[:text_limit], source=lang, target=translate_to)

    return {
        "title": title_final,
        "url": f"https://{lang}.wikipedia.org/wiki/{quote(parse.get('title', title).replace(' ', '_'))}",
        "text": text[:text_limit],
        "links": links,
        "images": images[:15],
        "external_links": external[:20],
    }


def collect_graph_articles(root_title, lang, limit):
    articles = {}
    queue = [root_title]
    visited = {root_title}
    failed = 0

    while queue and len(articles) < limit:
        title = queue.pop(0)
        if title in articles:
            continue

        try:
            article = get_wikipedia_article(title, lang, text_limit=500)
        except requests.RequestException:
            failed += 1
            continue

        if not article:
            failed += 1
            continue

        articles[article["title"]] = {
            "title": article["title"],
            "url": article["url"],
            "links": article["links"],
        }

        print(f"  собрано {len(articles)}/{limit}: {article['title'][:60]}")

        for link in article["links"]:
            if link not in visited and ":" not in link:
                visited.add(link)
                queue.append(link)

    if failed:
        print(f"  не удалось загрузить: {failed} статей")

    return articles


def get_wikidata(query, lang):
    search = api_get(API["wikidata"], {
        "action": "wbsearchentities",
        "search": query,
        "language": lang,
        "uselang": lang,
        "limit": 1,
    })

    hits = search.get("search", [])
    if not hits:
        return None

    entity_id = hits[0]["id"]

    data = api_get(API["wikidata"], {
        "action": "wbgetentities",
        "ids": entity_id,
        "languages": f"{lang}|en",
    })

    entity = data.get("entities", {}).get(entity_id, {})

    labels = {k: v.get("value") for k, v in entity.get("labels", {}).items()}
    descriptions = {k: v.get("value") for k, v in entity.get("descriptions", {}).items()}
    sitelinks = {k: v.get("title") for k, v in entity.get("sitelinks", {}).items()}

    return {
        "id": entity_id,
        "url": f"https://www.wikidata.org/wiki/{entity_id}",
        "labels": labels,
        "descriptions": descriptions,
        "sitelinks": sitelinks,
    }


def get_wiktionary(query, lang):
    url = API["wiktionary"].format(lang=lang)

    words = query.split()
    word = words[-1] if words else query

    data = api_get(url, {
        "action": "query",
        "list": "search",
        "srsearch": word,
        "srlimit": 1,
    })
    results = data.get("query", {}).get("search", [])
    if not results:
        return None

    title = results[0]["title"]

    data = api_get(url, {
        "action": "parse",
        "page": title,
        "prop": "text|links",
        "redirects": 1,
    })

    if "error" in data:
        return None

    parse = data["parse"]
    text = html_to_text(extract_html(parse))

    links = [
        item["title"] for item in parse.get("links", [])
        if "title" in item
    ]

    title_final = parse.get("title", title)

    return {
        "title": title_final,
        "url": f"https://{lang}.wiktionary.org/wiki/{quote(title_final.replace(' ', '_'))}",
        "text": text[:3000],
        "links": links[:30],
    }


def get_commons(query, limit=10):
    data = api_get(API["commons"], {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": limit,
        "prop": "imageinfo",
        "iiprop": "url|size|mime",
    })

    pages = data.get("query", {}).get("pages", [])
    files = []
    for page in pages:
        info = page.get("imageinfo", [])
        if not info:
            continue
        i = info[0]
        files.append({
            "title": page.get("title"),
            "url": i.get("url"),
            "mime": i.get("mime"),
            "width": i.get("width"),
            "height": i.get("height"),
            "page": f"https://commons.wikimedia.org/wiki/{quote(page.get('title', ''))}",
        })
    return files


def download_with_retry(url, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            response = requests.get(url, headers=DOWNLOAD_HEADERS, timeout=60)

            if response.status_code == 429:
                wait = 10 * (attempt + 1)
                print(f"  429, ждем {wait} сек (попытка {attempt + 1}/{max_attempts})...")
                time.sleep(wait)
                continue

            if response.status_code == 403:
                print("  403 Forbidden - нет доступа к файлу")
                return None

            response.raise_for_status()
            return response.content

        except (requests.Timeout, requests.ConnectionError) as e:
            wait = 5 * (attempt + 1)
            print(f"  Сетевая ошибка: {type(e).__name__}, ждем {wait} сек...")
            time.sleep(wait)

    return None


def get_picture_of_the_day(output_dir, lang="en"):
    today = date.today()
    url = (
        f"https://api.wikimedia.org/feed/v1/wikipedia/{lang}/featured/"
        f"{today.year}/{today.month:02d}/{today.day:02d}"
    )

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"  Ошибка Feed API: {e}")
        return None

    image = data.get("image")
    if not image:
        print("  Feed API не вернул картинку дня")
        return None

    image_url = image.get("image", {}).get("source")
    if not image_url:
        print("  В ответе нет ссылки на картинку")
        return None

    image_url_clean = image_url.split("?")[0]

    description = image.get("description", {}).get("text", "")
    title = image.get("title", "")

    content = download_with_retry(image_url_clean)
    if not content:
        print("  Не удалось скачать картинку после нескольких попыток")
        return None

    original_filename = image_url_clean.split("/")[-1]
    image_path = output_dir / original_filename
    text_path = output_dir / (original_filename + ".txt")

    image_path.write_bytes(content)
    text_path.write_text(
        f"Название: {title}\n"
        f"URL: {image_url_clean}\n"
        f"Дата: {today.isoformat()}\n\n"
        f"{description}\n",
        encoding="utf-8",
    )

    return {
        "image": str(image_path),
        "description": str(text_path),
        "url": image_url_clean,
        "text": description[:300],
    }


def build_graph(articles, output="wikimedia_graph.dot"):
    titles = set(articles.keys())

    with open(output, "w", encoding="utf-8") as f:
        f.write("digraph WikimediaGraph {\n")
        f.write('    rankdir=LR;\n')
        f.write('    charset="UTF-8";\n')
        f.write('    node [shape=box, style=filled, fillcolor=lightblue];\n\n')

        for title in sorted(articles.keys()):
            safe = title.replace('"', '\\"')
            f.write(f'    "{safe}";\n')

        f.write("\n")

        edge_count = 0
        for title, article in articles.items():
            src = title.replace('"', '\\"')
            for link in article.get("links", []):
                if link in titles and link != title:
                    dst = link.replace('"', '\\"')
                    f.write(f'    "{src}" -> "{dst}";\n')
                    edge_count += 1

        f.write("}\n")

    return len(articles), edge_count


def main():
    parser = argparse.ArgumentParser(
        description="Wikimedia API - сбор данных о предметной области"
    )
    parser.add_argument("query", nargs="+",
                        help="Запрос: личность, объект, событие, животное")
    parser.add_argument("--lang", default="ru", help="Язык проектов (ru/en/...)")
    parser.add_argument("--depth", type=int, default=30,
                        help="Минимум статей в графе")
    parser.add_argument("--outdir", default="output",
                        help="Папка для результатов")
    parser.add_argument("--potd", action="store_true",
                        help="Скачать картинку дня")
    parser.add_argument("--no-wiktionary", action="store_true",
                        help="Пропустить Викисловарь")
    parser.add_argument("--translate", action="store_true",
                        help="Автоперевод статьи на русский")
    parser.add_argument("--translate-to", default="ru",
                        help="Язык перевода, по умолчанию ru")

    args = parser.parse_args()

    query = " ".join(args.query).strip()
    output_dir = Path(args.outdir)
    output_dir.mkdir(exist_ok=True)

    translate_to = args.translate_to if args.translate else None

    print(f"Запрос: «{query}» | язык: {args.lang}")
    if translate_to:
        print(f"Автоперевод: → {translate_to}")

    title = search_wikipedia(query, args.lang)
    if not title:
        print("Статья не найдена в Википедии")
        return
    print(f"Wikipedia: {title}")

    article = get_wikipedia_article(
        title, args.lang, text_limit=5000, translate_to=translate_to
    )
    if not article:
        print("Не удалось загрузить статью")
        return

    wikidata = get_wikidata(title, args.lang)
    if wikidata:
        print(f"Wikidata: {wikidata['id']}")

    wiktionary = None
    if not args.no_wiktionary:
        wiktionary = get_wiktionary(query, args.lang)
        if wiktionary:
            print(f"Wiktionary: {wiktionary['title']}")

    commons = get_commons(title, limit=10)
    print(f"Commons: {len(commons)} файлов")

    print(f"\nСбор статей для графа (минимум {args.depth})...")
    articles = collect_graph_articles(title, args.lang, args.depth)
    related = [a for t, a in articles.items() if t != article["title"]]

    result = {
        "query": query,
        "lang": args.lang,
        "translate_to": translate_to,
        "wikipedia": {
            "main_article": article,
            "related_articles": related,
        },
        "wikidata": wikidata,
        "wiktionary": wiktionary,
        "commons": {
            "files": commons,
        },
    }

    json_path = output_dir / "result.json"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON: {json_path}")

    dot_path = output_dir / "graph.dot"
    nodes, edges = build_graph(articles, str(dot_path))
    print(f"Граф: {dot_path} ({nodes} узлов, {edges} ребер)")

    if args.potd:
        print("\nКартинка дня...")
        potd = get_picture_of_the_day(output_dir, args.lang)
        if potd:
            print(f"  Картинка: {potd['image']}")
            print(f"  Описание: {potd['description']}")
        else:
            print("  Не удалось получить")


if __name__ == "__main__":
    main()
