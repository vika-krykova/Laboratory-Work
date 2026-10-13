import scrapy


class NewsItem(scrapy.Item):
    title = scrapy.Field()
    url = scrapy.Field()
    date = scrapy.Field()
    summary = scrapy.Field()
    source = scrapy.Field()
    hub = scrapy.Field()


class ProductItem(scrapy.Item):
    title = scrapy.Field()
    price = scrapy.Field()
    rating = scrapy.Field()
    url = scrapy.Field()
    description = scrapy.Field()