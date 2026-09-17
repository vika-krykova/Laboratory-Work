import requests
from bs4 import BeautifulSoup
from rutermextract import TermExtractor
from graphviz import Digraph

urls = [
    "https://www.severstal.com/",
    "https://mmk.ru/",
    "https://nlmk.com/",
    "https://www.nornickel.ru/",
    "https://www.rusal.ru/",
    "https://omk.ru/",
    "https://www.rmk-group.ru/",
    "https://www.uralsteel.com/",
    "https://www.amet.ru/",
    "https://www.vsmpo.ru/",
    "https://www.ruspolymet.ru/",
    "https://www.metalinfo.ru/",
    "https://www.uralmash.ru/",
    "https://metaprom.ru/",
    "https://metaltorg.ru/",
    "https://metallotorg.ru/",
    "https://www.ugmk.com/",
    "https://www.stalmet.ru/",
    "https://www.rusmet.ru/",
    "https://www.mc.ru/",
    "https://metalexpert.ru/",
    "https://www.steel-news.ru/",
    "https://www.metalbulletin.ru/",
    "https://metallurgmash.ru/",
    "https://www.metallolom.ru/",
    "https://www.mcena.ru/",
    "https://www.steelland.ru/",
    "https://www.metkom.ru/",
    "https://www.tdmetall.ru/",
    "https://www.metallobaza.ru/"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"
}

STOP_WORDS = {
    "компания", "контакты", "россия", "продукция", "услуги",
    "инвесторы", "новости", "документы", "поставщики", "карьера",
    "пресс-центр", "раскрытие информации", "устойчивое развитие",
    "руководство", "акционеры", "клиенты", "партнёры", "производство",
    "предприятие", "страница", "раздел", "статья", "обработка",
    "персональные данные", "политика", "согласие", "карта сайта",
    "корпоративное управление", "численность персонала", "информации",
    "команда", "инновации", "экология"
}

extractor = TermExtractor()
sites_terms = {}


def get_site_name(url):
    name = url.replace("https://", "").replace("http://", "")
    name = name.replace("www.", "")
    return name.split("/")[0]


def get_text(url):
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        return text[:20000]
    except requests.RequestException:
        return ""


def get_terms(text):
    terms = []
    for term in extractor(text):
        word = term.normalized.lower()
        if len(word) >= 4 and word not in STOP_WORDS:
            terms.append(word)
        if len(terms) == 20:
            break
    return set(terms)


for url in urls:
    if len(sites_terms) == 25:
        break
    site_name = get_site_name(url)
    print("Обрабатывается:", site_name)
    text = get_text(url)
    terms = get_terms(text)
    if not terms:
        terms = {site_name}
    sites_terms[site_name] = terms

if len(sites_terms) < 25:
    print(f"Получилось обработать только {len(sites_terms)} сайтов из 25.")

graph = Digraph("Metallurgy")
graph.attr(charset="UTF-8")

for site, terms in sites_terms.items():
    graph.node(site, tooltip=", ".join(sorted(terms)))

sites = list(sites_terms)

for i in range(len(sites)):
    for j in range(i + 1, len(sites)):
        common = sites_terms[sites[i]] & sites_terms[sites[j]]
        if common:
            label = ", ".join(sorted(common)[:3])
            graph.edge(sites[i], sites[j], label=label)

with open("metallurgy_graph.dot", "w", encoding="utf-8") as f:
    f.write(graph.source)

try:
    graph.render("metallurgy_graph", format="png", cleanup=True)
except Exception:
    pass

print("Создан файл metallurgy_graph.dot")