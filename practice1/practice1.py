import argparse
import io
import json
import socket
import time
from collections import Counter

import requests
from bs4 import BeautifulSoup
from tabulate import tabulate

_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_getaddrinfo

INDEX_URLS = [
    "https://index.commoncrawl.org/CC-MAIN-2025-05-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-51-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-46-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-42-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-38-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-33-index",
    "https://index.commoncrawl.org/CC-MAIN-2024-30-index",
]
WARC_URL = "https://data.commoncrawl.org/{filename}"

SKIP_PARTS = ("robots.txt", "sitemap", "/wiki/", "?C=", "&O=", ".pdf", ".xml", "?id=")


def search_cdx(domain, limit):
    url_pattern = f"*.{domain}/*"
    records = []

    for index_url in INDEX_URLS:
        if len(records) >= limit:
            break

        params = [
            ("url", url_pattern),
            ("output", "json"),
            ("filter", "status:200"),
            ("filter", "mime:text/html"),
            ("limit", str(limit)),
        ]

        print(f"  [{index_url.split('/')[-1]}]", end=" ")

        for attempt in range(3):
            try:
                response = requests.get(index_url, params=params, timeout=30)
                if response.status_code in (502, 504):
                    print(f"CDX {response.status_code}, повтор...")
                    time.sleep(2 ** attempt)
                    continue
                if response.status_code != 200:
                    print(f"HTTP {response.status_code}")
                    break
                response.raise_for_status()
                break
            except requests.RequestException as e:
                print(f"ошибка: {e}")
                if attempt == 2:
                    break
                time.sleep(2 ** attempt)
        else:
            continue

        added = 0
        for line in response.text.splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            url = record.get("url", "")
            if any(part in url for part in SKIP_PARTS):
                continue
            records.append(record)
            added += 1
            if len(records) >= limit:
                break

        print(f"+{added}")

    return records[:limit]


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


def build_table(records_by_domain, keywords, show_text, limit_per_domain):
    rows = []
    kept = []

    for domain, records in records_by_domain.items():
        kept_in_domain = 0
        total = len(records)

        print(f"\n--- Домен: {domain} ---")
        for i, record in enumerate(records, 1):
            if kept_in_domain >= limit_per_domain:
                break

            title = ""
            text = ""

            print(f"[{i}/{total}] загрузка WARC: {record.get('url', '')[:70]}")
            try:
                title, text = load_warc(record)
            except Exception as e:
                print(f"    Не удалось загрузить WARC -> {e}")
                continue

            if keywords:
                page = (title + " " + text).lower()
                if not all(kw.lower() in page for kw in keywords):
                    continue

            kept.append(record)
            kept_in_domain += 1
            row = [
                record.get("url", ""),
                record.get("timestamp", ""),
                title,
            ]
            if show_text:
                row.append(text[:200])
            rows.append(row)

    headers = ["URL", "Дата архивации", "Заголовок страницы"]
    if show_text:
        headers.append("Фрагмент текста")
    print()
    print(tabulate(rows, headers=headers, tablefmt="grid"))
    print(f"\nВсего строк: {len(rows)}")

    return kept


def show_distribution(records):
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
    parser.add_argument("--domain", nargs="+", default=["pstu.ru"],
                        help="Домены (по умолчанию: pstu.ru)")
    parser.add_argument("--limit", type=int, default=10,
                        help="Ограничение числа результатов на каждый домен")
    parser.add_argument("--show-text", action="store_true",
                        help="Показать фрагмент текста страницы")

    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limit должен быть больше нуля")

    fetch_per_domain = args.limit * 2 if args.keywords else args.limit

    records_by_domain = {}
    for domain in args.domain:
        print(f"Поиск по домену: {domain}")
        found = search_cdx(domain, fetch_per_domain)
        print(f"  найдено: {len(found)}")
        records_by_domain[domain] = found

    kept = build_table(records_by_domain, args.keywords, args.show_text, args.limit)
    show_distribution(kept)


if __name__ == "__main__":
    main()
