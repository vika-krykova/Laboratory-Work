import argparse
import io
import json
import socket

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo


INDEX_URL = "https://index.commoncrawl.org/CC-MAIN-2024-30-index"
WARC_URL = "https://data.commoncrawl.org/{filename}"

SKIP_PARTS = ("robots.txt", "sitemap", "/wiki/", "?C=", "&O=", ".pdf", ".xml", "?id=")


def search_cdx(domain, limit):
    url_pattern = f"*.{domain}/*"

    params = [
        ("url", url_pattern),
        ("output", "json"),
        ("filter", "status:200"),
        ("filter", "mime:text/html"),
        ("limit", str(limit)),
    ]

    for attempt in range(3):
        try:
            response = requests.get(INDEX_URL, params=params, timeout=30)
            if response.status_code in (502, 504):
                print(f"Сервер CDX не ответил ({response.status_code}), повтор...")
                continue
            response.raise_for_status()
            break
        except requests.RequestException as e:
            print(f"Ошибка CDX: {e}")
            if attempt == 2:
                return []
    else:
        return []

    records = []
    for line in response.text.splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        url = record.get("url", "")
        if any(part in url for part in SKIP_PARTS):
            continue
        records.append(record)
        if len(records) >= limit:
            break

    return records


def load_warc(record):
    from warcio.archiveiterator import ArchiveIterator

    start = int(record["offset"])
    end = start + int(record["length"]) - 1

    response = requests.get(
        WARC_URL.format(filename=record["filename"]),
        headers={"Range": f"bytes={start}-{end}"},
        timeout=60,
    )
    response.raise_for_status()

    stream = io.BytesIO(response.content)

    for entry in ArchiveIterator(stream):
        if entry.rec_type == "response":
            html = entry.content_stream().read()
            soup = BeautifulSoup(html, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""
            text = soup.get_text(" ", strip=True)
            return title, text[:30000]

    return "", ""


def build_table(records, keywords, show_text):
    rows = []
    kept = []

    for record in records:
        title = ""
        text = ""

        if show_text:
            try:
                title, text = load_warc(record)
            except Exception as e:
                print(f"Не удалось загрузить WARC: {record.get('url', '')} -> {e}")
                continue

            if keywords:
                page = (title + " " + text).lower()
                if not all(kw.lower() in page for kw in keywords):
                    continue

        kept.append(record)
        rows.append([
            record.get("url", ""),
            record.get("timestamp", ""),
            title,
            text[:200] if show_text else "",
        ])

    headers = ["URL", "Дата архивации", "Заголовок страницы", "Фрагмент текста"]
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\nВсего строк: {len(rows)}")

    return kept


def show_distribution(records):
    from collections import Counter

    if not records:
        return

    domains = Counter()
    years = Counter()

    for record in records:
        url = record.get("url", "")
        if "://" in url:
            domains[url.split("/")[2]] += 1

        timestamp = record.get("timestamp", "")
        if len(timestamp) >= 4:
            years[timestamp[:4]] += 1

    print("\nРаспределение по доменам:")
    for domain, count in domains.most_common():
        print(f"  {domain}: {count}")

    print("\nРаспределение по годам:")
    for year, count in sorted(years.items()):
        print(f"  {year}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Поиск по архиву Common Crawl")
    parser.add_argument("keywords", nargs="*", default=[],
                        help="Ключевые слова для поиска")
    parser.add_argument("--domain", nargs="+", required=True,
                        help="Домен (например, pstu.ru)")
    parser.add_argument("--limit", type=int, default=10,
                        help="Ограничение числа результатов")
    parser.add_argument("--show-text", action="store_true",
                        help="Показать фрагмент текста страницы")

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit должен быть больше нуля")

    fetch_limit = args.limit * 2 if args.show_text else args.limit

    records = []
    for domain in args.domain:
        print(f"Поиск по домену: {domain}")
        found = search_cdx(domain, fetch_limit)
        print(f"  найдено: {len(found)}")
        records.extend(found)

    kept = build_table(records, args.keywords, args.show_text)
    show_distribution(kept)


if __name__ == "__main__":
    main()