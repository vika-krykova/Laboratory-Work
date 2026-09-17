Лабораторная работа 1 - Граф металлургии

Установка:
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install requests beautifulsoup4 rutermextract graphviz
```

Для PNG:
Graphviz: `sudo apt install graphviz` (Ubuntu), `brew install graphviz` (macOS).

Запуск:
```bash
python lab1.py
```

Скрипт обрабатывает 25 сайтов, извлекает термины через `rutermextract`, строит граф и сохраняет:
- `metallurgy_graph.dot` - в формате DOT
- `metallurgy_graph.png` - визуализация

