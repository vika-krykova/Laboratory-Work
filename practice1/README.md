Практическая работа 1 - Поиск по архиву Common Crawl

Установка:
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 tabulate warcio
```

Запуск:
```bash
python practice1.py <ключевые-слова> --domain <домен> [--limit N] [--show-text]
```

Аргументы:
- `keywords` - одно или несколько ключевых слов
- `--domain` - домен обязательный
- `--limit` - лимит результатов на домен (по умолчанию 10)
- `--show-text` - загрузить и показать фрагмент текста страницы

Примеры:

```bash
1. Пермь и ПНИПУ
python practice1.py Пермь --domain pstu.ru --limit 10 --show-text

2. Кафедра ИТАС
python practice1.py ИТАС --domain pstu.ru --limit 10 --show-text

3. МГУ vs МФТИ (запускать дважды и сравнить число строк)
python practice1.py --domain msu.ru --limit 50
python practice1.py --domain mipt.ru --limit 50

4. Пастернак + Пермь
python practice1.py Пастернак Пермь --domain pstu.ru psu.ru permkrai.ru --limit 20 --show-text
```

Что выводится:
1. Таблица: URL, дата архивации, заголовок, фрагмент текста (при `--show-text`)
2. Общее число найденных строк
3. Распределение результатов по доменам
4. Распределение результатов по годам

