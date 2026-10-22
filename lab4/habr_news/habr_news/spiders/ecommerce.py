import scrapy
from scrapy_playwright.page import PageMethod
from habr_news.items import ProductItem


class EcommerceSpider(scrapy.Spider):
    name = 'ecommerce'
    allowed_domains = ['scrapingcourse.com']
    start_urls = ['https://scrapingcourse.com/ecommerce/']

    custom_settings = {
        'ROBOTSTXT_OBEY': False,
    }

    MAX_PAGES = 22

    def closed(self, reason):
        stats = self.crawler.stats.get_stats()
        count = stats.get('item_scraped_count', 0)
        if count < 100:
            self.logger.warning(f'!!! ВНИМАНИЕ: собрано только {count} items (требуется 100+)')
        else:
            self.logger.info(f'OK: собрано {count} items (требуется 100+)')

    def __init__(self, category='', stores='', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.category = category
        self.stores = stores.split(',') if stores else []
        self.logger.info(f'Category={self.category}, Stores={self.stores}')

    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(
                url,
                meta={
                    'playwright': True,
                    'playwright_page_methods': [
                        PageMethod('wait_for_selector', 'li.product'),
                    ]
                },
                callback=self.parse,
            )

    def parse(self, response):
        products = response.css('li.product')
        self.logger.info(f'Найдено товаров: {len(products)}')

        for product in products:
            title = product.css('h2.woocommerce-loop-product__title::text').get()
            if title:
                title = title.strip()

            price_raw = product.css('.price .woocommerce-Price-amount bdi::text').getall()
            price = None
            if price_raw:
                price_text = ''.join(price_raw).replace('$', '').replace(',', '').strip()
                try:
                    price = float(price_text)
                except ValueError:
                    price = price_text

            url = product.css('a.woocommerce-LoopProduct-link::attr(href)').get()
            if url:
                url = response.urljoin(url)

            description = title
            rating = None

            yield ProductItem(
                title=title,
                price=price,
                rating=rating,
                url=url,
                description=description,
            )

        current_page = response.meta.get('page', 1)
        if current_page >= self.MAX_PAGES:
            self.logger.info(f'Достигнут лимит страниц ({self.MAX_PAGES})')
            return

        next_page = response.css('a.next.page-numbers::attr(href)').get()
        if not next_page:
            self.logger.info('Следующей страницы нет. Останавливаемся.')
            return

        next_page_num = current_page + 1
        self.logger.info(f'Переход на страницу {next_page_num}: {next_page}')

        yield scrapy.Request(
            response.urljoin(next_page),
            meta={
                'playwright': True,
                'page': next_page_num,
                'playwright_page_methods': [
                    PageMethod('wait_for_selector', 'li.product'),
                ]
            },
            callback=self.parse,
        )
