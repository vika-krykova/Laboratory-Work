# Практика 6. Автоматический анализ и семантическая обработка видео

> Заготовка сгенерирована автоматически. Таблицы и графики — результат запуска; разделы «Комментарий»
> и «Обоснование» нужно написать самому по своим данным (что получилось, что нет, почему).

## 0. Данные
Обработано роликов: **9**, проанализировано кадров: **2093**,
лемматизация: **pymorphy3**.

| id | title | duration_s | resolution | codec | fps | has_audio | views | engagement | segments | words |
|---|---|---|---|---|---|---|---|---|---|---|
| rutube_08af8248a11aee5979a43cb6df284e11 | Спортпит для выносливости | 143 | 1280x720 | h264 | 30.0 | True | 38 | 0.0 | 36 | 277 |
| rutube_3e388e8cf320b2eb29a9dfaf6c802f26 | Высокие и вкусные маффины! За 10 минут! Всё с | 281 | 1280x720 | h264 | 29.97 | True | 14249 | 0.0 | 2 | 20 |
| rutube_4cd6078befc2f6272e70b6bc0853cfb5 | Красим стены и фасад своими руками. Краска дл | 123 | 1280x720 | h264 | 30.0 | True | 7017 | 0.0 | 35 | 216 |
| rutube_8f8c0083faabf7ac15b2720f6bb5207f | Это Турецкое варенье 🔥 Бьёт все рекорды и по  | 117 | 1280x720 | h264 | 29.97 | True | 8738 | 0.0 | 26 | 228 |
| rutube_95bee9be257ec61a293a817496dfe663 | 5 ИДЕЙ ДЛЯ ТЮНИНГА ВЕЛОСИПЕДА // КАК УЛУЧШИТЬ | 333 | 1280x720 | h264 | 25.0 | True | 3868 | 0.0 | 109 | 823 |
| rutube_9faaafec8ce2cc8f4715cec9ef7f7a44 | Быстрая утренняя зарядка | 5 минут для энерги | 326 | 1280x720 | h264 | 50.0 | True | 52536 | 0.0 | 91 | 514 |
| rutube_dd8a753d1c55cdec53242ebcc82a08a8 | Как наносить жидкие обои на стену, пошаговая  | 198 | 1280x720 | h264 | 25.0 | True | 16760 | 0.0 | 38 | 308 |
| rutube_e5f6511f905d08cea67a19257a7368af | Лучшие Сырники РЕЦЕПТ НА МИЛЛИОН со 100% резу | 227 | 1280x720 | h264 | 29.97 | True | 203966 | 0.0 | 67 | 492 |
| rutube_ebc42ced8d6858b2ee7b29f3bde1e53e | Укладка ламината своими руками. Как избежать  | 341 | 1280x720 | h264 | 30.0 | True | 127599 | 0.0 | 97 | 816 |

Пропуски и предупреждения (data/errors.csv):

| time | source | stage | reason |
|---|---|---|---|
| 2026-11-03 20:39:27 | https://youtu.be/_iVIQMCyOmA | collect | DownloadError: [0;31mERROR:[0m [youtube] _iVIQMCyOmA: Unable to download API page: HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0) (caused by TransportError("HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0)")) |
| 2026-11-03 20:42:08 | https://youtu.be/B6Q0IHYGgiw | collect | DownloadError: [0;31mERROR:[0m [youtube] B6Q0IHYGgiw: Unable to download API page: HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0) (caused by TransportError("HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0)")) |
| 2026-11-03 20:44:49 | https://youtu.be/JHqMDJTddXQ | collect | DownloadError: [0;31mERROR:[0m [youtube] JHqMDJTddXQ: Unable to download API page: HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0) (caused by TransportError("HTTPSConnectionPool(host='www.youtube.com', port=443): Read timed out. (read timeout=20.0)")) |
| 2026-11-03 20:55:19 | https://rutube.ru/video/ebc42ced8d6858b2ee7b29f3bde1e53e/ | collect | FileNotFoundError: [Errno 2] No such file or directory: 'ffprobe' |

**Комментарий:** _TODO_

## 1. Ключевые визуальные характеристики и объекты
| class | class_en | videos | frames | share_of_frames_% | mean_conf | max_per_frame |
|---|---|---|---|---|---|---|
| человек | person | 9 | 1108 | 52.9 | 0.83 | 3 |
| велосипед | bicycle | 1 | 211 | 10.1 | 0.82 | 2 |
| миска | bowl | 4 | 210 | 10.0 | 0.64 | 3 |
| скамейка | bench | 2 | 150 | 7.2 | 0.59 | 1 |
| торт | cake | 4 | 121 | 5.8 | 0.72 | 13 |
| обеденный стол | dining table | 5 | 98 | 4.7 | 0.55 | 1 |
| диван | couch | 1 | 87 | 4.2 | 0.46 | 2 |
| пончик | donut | 4 | 86 | 4.1 | 0.67 | 7 |
| чашка | cup | 4 | 65 | 3.1 | 0.54 | 2 |
| телефон | cell phone | 5 | 44 | 2.1 | 0.66 | 2 |
| банан | banana | 3 | 28 | 1.3 | 0.54 | 3 |
| ложка | spoon | 3 | 25 | 1.2 | 0.58 | 1 |
| холодильник | refrigerator | 1 | 24 | 1.1 | 0.44 | 1 |
| вилка | fork | 3 | 15 | 0.7 | 0.55 | 1 |
| апельсин | orange | 3 | 15 | 0.7 | 0.55 | 3 |

![](objects_top.png)

**Комментарий:** _TODO: какие объекты ожидались для темы, какие найдены, где модель ошибается_

## 2. Временные метки значимых событий
| вид | событий |
|---|---|
| объект | 167 |
| смена сцены | 157 |
| всплеск громкости | 4 |

Полный список: `events.csv`. Пример таймлайна:

![](timeline_example.png)
![](events_by_video.png)

**Комментарий:** _TODO_

## 3. Статистика по распознанным сущностям
Объекты — таблица в п.1 (`objects_stats.csv`). Самые частые термины в речи (`terms_stats.csv`):

| term | count | videos |
|---|---|---|
| берем | 16 | 5 |
| полоски | 16 | 1 |
| нужно | 15 | 5 |
| велосипеде | 15 | 1 |
| вниз | 13 | 2 |
| сырники | 13 | 1 |
| стену | 12 | 3 |
| получается | 10 | 4 |
| руки | 10 | 3 |
| укладываем | 9 | 2 |
| количество | 9 | 4 |
| вместе | 8 | 3 |
| делаем | 8 | 4 |
| диск | 8 | 1 |
| либо | 7 | 3 |
| самое | 7 | 3 |
| сильно | 7 | 3 |
| смесь | 6 | 3 |
| необходимо | 6 | 3 |
| сделать | 6 | 6 |

**Комментарий:** _TODO_

## 4. Интерактивная временная шкала
Файл `dashboard.html` (запуск: `python -m http.server` в корне проекта, затем `/out/dashboard.html`).
Поиск по слову или объекту, клик по событию/результату перематывает видео.

## 5. Тематические распределения
Метод: **kmeans**, silhouette по k: `{'2': 0.037, '3': 0.04, '4': 0.036, '5': 0.038, '6': 0.03}`.

| тема | роликов | ключевые слова | ролики |
|---|---|---|---|
| 0 | 3 | велосипеда, описании, вместе, вниз, выносливости, https, выросли, пустите | rutube_08af8248a11aee5979a43cb6df284e11, rutube_95bee9be257ec61a293a817496dfe663, rutube_9faaafec8ce2cc8f4715cec9ef7f7a44 |
| 1 | 3 | духовки, сахар, масло, минут, вкусные, kalnina, мука, сливочное | rutube_3e388e8cf320b2eb29a9dfaf6c802f26, rutube_8f8c0083faabf7ac15b2720f6bb5207f, rutube_e5f6511f905d08cea67a19257a7368af |
| 2 | 3 | стену, поверхность, материал, слой, краска, наносить, обои, жидкие | rutube_4cd6078befc2f6272e70b6bc0853cfb5, rutube_dd8a753d1c55cdec53242ebcc82a08a8, rutube_ebc42ced8d6858b2ee7b29f3bde1e53e |

![](topics.png)

**Комментарий:** _TODO: прочитайте 3–5 роликов из каждого кластера — тема действительно общая?_

## Обоснование параметров
| Параметр | Значение | Почему |
|---|---|---|
| YOLO | yolov8n.pt | _TODO (скорость/качество на CPU)_ |
| Порог conf | 0.4 | _TODO: см. `conf_sweep.png`_ |
| Whisper | tiny | _TODO_ |
| Шаг кадров | 1 / 2 / 5 с в зависимости от длины | компромисс «полнота / время» |
| Громкость | z ≥ 2.0, не тише -35.0 dB | _TODO_ |
| Смена сцены | корреляция гистограмм < 0.6 | _TODO_ |
| Объект как событие | ≥ 3.0 с, пропуск ≤ 2.0 с | _TODO_ |

![](conf_sweep.png)

## Ручная проверка
Результат `python validate.py --score` (случайные события, сверка с видео): _TODO_

## Ограничения и этика
_TODO: морфология при поиске, ошибки Whisper на шуме, условия платформ. Эмоции и «внимание» по лицам не выводились._
