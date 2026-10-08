import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from graphviz import Graph
from rutermextract import TermExtractor

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
}

STOP_WORDS = {
    "компания", "контакты", "россия", "продукция", "услуги",
    "инвесторы", "новости", "документы", "поставщики", "карьера",
    "пресс-центр", "раскрытие информации", "устойчивое развитие",
    "руководство", "акционеры", "клиенты", "партнёры", "производство",
    "предприятие", "страница", "раздел", "статья", "обработка",
    "персональные данные", "политика", "согласие", "карта сайта",
    "корпоративное управление", "численность персонала", "информации",
    "команда", "инновации", "экология",
    "январь", "февраль", "март", "апрель", "май", "июнь",
    "июль", "август", "сентябрь", "октябрь", "ноябрь", "декабрь",
    "понедельник", "вторник", "среда", "четверг", "пятница",
    "суббота", "воскресенье",
    "год", "года", "году", "годы", "лет",
    "день", "дни", "дня", "дней",
    "время", "сегодня", "вчера", "завтра",
}

ERROR_MARKER = "__ERROR__:"

extractor = TermExtractor()


def domain_key(url):
    key = url.replace("https://", "").replace("http://", "").replace("www.", "")
    return key.split("/")[0].lower()


def load_sources(path):
    urls = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)
    return urls


def deduplicate(urls):
    seen = set()
    unique = []
    for url in urls:
        key = domain_key(url)
        if key not in seen:
            seen.add(key)
            unique.append(url)
    return unique


def cache_path(url, cache_dir):
    h = hashlib.md5(url.encode("utf-8")).hexdigest()
    return Path(cache_dir) / f"{h}.txt"


def get_text(url, text_limit, use_cache, cache_dir):
    cache_file = cache_path(url, cache_dir)

    if use_cache and cache_file.exists():
        cached = cache_file.read_text(encoding="utf-8")
        if cached.startswith(ERROR_MARKER):
            return "", "cache"
        return cached, "cache"

    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)[:text_limit]
        if use_cache:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(text, encoding="utf-8")
        return text, "network"
    except requests.RequestException as e:
        err_msg = str(e)
        if use_cache:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(ERROR_MARKER + err_msg, encoding="utf-8")
        return "", err_msg


def get_terms(text, max_terms):
    terms = set()
    for term in extractor(text):
        word = term.normalized.lower()
        if len(word) >= 4 and word not in STOP_WORDS:
            terms.add(word)
            if len(terms) >= max_terms:
                break
    return terms


def build_graph(sites_terms, threshold):
    graph = Graph("Metallurgy")
    graph.attr(charset="UTF-8")
    graph.attr(overlap="false", splines="true")

    for site, terms in sites_terms.items():
        graph.node(site, tooltip=", ".join(sorted(terms)))

    sites = list(sites_terms)
    for i in range(len(sites)):
        for j in range(i + 1, len(sites)):
            common = sites_terms[sites[i]] & sites_terms[sites[j]]
            if len(common) >= threshold:
                label = ", ".join(sorted(common)[:3])
                graph.edge(sites[i], sites[j], label=label)

    return graph


def main():
    parser = argparse.ArgumentParser(
        description="Граф информационных ресурсов металлургической отрасли"
    )
    parser.add_argument("--sources", default="sources.txt",
                        help="Файл со списком URL (по умолчанию: sources.txt)")
    parser.add_argument("--output-dir", default="output",
                        help="Папка для результатов (по умолчанию: output)")
    parser.add_argument("--cache-dir", default=".cache",
                        help="Папка для кэша (по умолчанию: .cache)")
    parser.add_argument("--terms", type=int, default=20,
                        help="Максимум терминов на ресурс (по умолчанию: 20)")
    parser.add_argument("--threshold", type=int, default=2,
                        help="Минимум общих терминов для связи (по умолчанию: 2)")
    parser.add_argument("--limit-sites", type=int, default=0,
                        help="Обработать только N первых сайтов (0 = все)")
    parser.add_argument("--text-limit", type=int, default=100000,
                        help="Максимум символов текста на страницу (по умолчанию: 100000)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Отключить кэширование")

    args = parser.parse_args()

    if not Path(args.sources).exists():
        sys.exit(f"Файл {args.sources} не найден. Создайте его со списком URL.")

    urls = load_sources(args.sources)
    if not urls:
        sys.exit(f"Файл {args.sources} пуст или содержит только комментарии.")

    urls = deduplicate(urls)
    if args.limit_sites > 0:
        urls = urls[:args.limit_sites]

    use_cache = not args.no_cache
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Обрабатываю {len(urls)} сайтов, кэш: {'вкл' if use_cache else 'выкл'}")
    print("=" * 60)

    sites_terms = {}
    errors = {}

    for i, url in enumerate(urls, 1):
        site = domain_key(url)
        print(f"[{i}/{len(urls)}] {site}... ", end="", flush=True)

        start = time.time()
        text, source = get_text(url, args.text_limit, use_cache, args.cache_dir)
        elapsed = time.time() - start

        if not text:
            errors[url] = source if source != "cache" else "ошибка (из кэша)"
            if source == "cache":
                print("ОШИБКА (из кэша)")
            else:
                short = source[:80] + "..." if len(source) > 80 else source
                print(f"ОШИБКА ({elapsed:.1f}с): {short}")
            continue

        terms = get_terms(text, args.terms)
        if not terms:
            errors[url] = "нет терминов (rutermextract вернул пусто)"
            print(f"нет терминов ({elapsed:.1f}с)")
            continue

        sites_terms[site] = terms
        origin = "из кэша" if source == "cache" else f"{len(text)} симв, {elapsed:.1f}с"
        print(f"OK, {len(terms)} терминов, {origin}")

    print("=" * 60)
    print(f"Успешно: {len(sites_terms)}")
    print(f"Ошибок:  {len(errors)}")

    if len(sites_terms) < 2:
        sys.exit("Слишком мало успешно обработанных сайтов для построения графа.")

    graph = build_graph(sites_terms, args.threshold)
    dot_file = output_dir / "metallurgy_graph.dot"
    dot_file.write_text(graph.source, encoding="utf-8")
    print(f"Создан {dot_file}")

    try:
        graph.render(str(output_dir / "metallurgy_graph"), format="png", cleanup=True)
        print(f"Создан {output_dir / 'metallurgy_graph.png'}")
    except Exception as e:
        print(f"PNG не создан: {e}")

    if errors:
        errors_file = output_dir / "errors.json"
        errors_file.write_text(
            json.dumps(errors, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Лог ошибок: {errors_file}")


if __name__ == "__main__":
    main()
