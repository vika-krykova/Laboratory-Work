import scrapy
from datetime import datetime, timedelta
from habr_news.items import NewsItem


class NewsSpider(scrapy.Spider):
    name = 'news'
    allowed_domains = ['habr.com']
    start_urls = ['https://habr.com/ru/articles/']

    MAX_PAGES = 12

    def closed(self, reason):
        stats = self.crawler.stats.get_stats()
        count = stats.get('item_scraped_count', 0)
        if count < 100:
            self.logger.warning(f'!!! ВНИМАНИЕ: собрано только {count} items (требуется 100+)')
        else:
            self.logger.info(f'OK: собрано {count} items (требуется 100+)')

    def __init__(self, keywords=None, days=7, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.keywords = [k.strip().lower() for k in keywords.split(',')] if keywords else []
        self.days = int(days)
        self.cutoff_date = datetime.now() - timedelta(days=self.days)
        self.logger.info(f'Фильтр: keywords={self.keywords}, days={self.days}')

    def parse(self, response):
        articles = response.css('article.tm-articles-list__item')
        self.logger.info(f'Найдено статей на странице: {len(articles)}')

        for article in articles:
            title_parts = article.css('a.tm-title__link ::text').getall()
            title = ' '.join(t.strip() for t in title_parts if t.strip()) or None

            url = article.css('a.tm-title__link::attr(href)').get()
            date_str = article.css('time::attr(datetime)').get()

            summary_parts = article.css('div.lead p::text').getall()
            summary = ' '.join(s.strip() for s in summary_parts if s.strip())[:500] or None

            hub_spans = article.css('a.tm-publication-hub__link > span:first-child::text').getall()
            hub = ', '.join(h.strip() for h in hub_spans if h.strip()) or None

            if not title or not url:
                continue

            if date_str:
                try:
                    pub_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    if pub_date.tzinfo:
                        pub_date = pub_date.replace(tzinfo=None)
                    if pub_date < self.cutoff_date:
                        continue
                except ValueError as e:
                    self.logger.warning(f'Ошибка парсинга даты "{date_str}": {e}')

            if self.keywords:
                haystack = (title + ' ' + (summary or '')).lower()
                if not any(kw in haystack for kw in self.keywords):
                    continue

            yield NewsItem(
                title=title.strip(),
                url=response.urljoin(url),
                date=date_str,
                summary=summary,
                source='Habr',
                hub=hub,
            )

        current_page = response.meta.get('page', 1)
        if current_page >= self.MAX_PAGES:
            self.logger.info(f'Достигнут лимит страниц ({self.MAX_PAGES}). Останавливаемся.')
            return

        page_links = response.css('div.tm-pagination a::attr(href)').getall()
        if not page_links:
            self.logger.info('Ссылок пагинации не найдено. Останавливаемся.')
            return

        next_url = page_links[-1]
        next_page_num = current_page + 1

        self.logger.info(f'Переход на страницу {next_page_num}: {next_url}')
        yield response.follow(
            next_url,
            callback=self.parse,
            meta={'page': next_page_num}
        )
