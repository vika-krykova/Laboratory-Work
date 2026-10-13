import argparse
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings


def main():
    parser = argparse.ArgumentParser(description='Run web scraping spiders')
    parser.add_argument('--spider', required=True, choices=['news', 'ecommerce'],
                        help='Spider to run')
    parser.add_argument('--keywords', help='Keywords (comma-separated)')
    parser.add_argument('--days', type=int, default=7, help='Days back')
    parser.add_argument('--category', help='Category for ecommerce (резерв для реальных магазинов)')
    parser.add_argument('--stores', help='Stores for ecommerce (резерв для реальных магазинов)')
    parser.add_argument('--output', required=True, help='Output file (JSON or CSV)')
    args = parser.parse_args()

    settings = get_project_settings()
    settings.set('FEEDS', {
        args.output: {
            'format': 'json' if args.output.endswith('.json') else 'csv',
            'overwrite': True,
            'encoding': 'utf-8',
        }
    })

    process = CrawlerProcess(settings)

    if args.spider == 'news':
        from habr_news.spiders.news import NewsSpider
        process.crawl(NewsSpider, keywords=args.keywords, days=args.days)
    elif args.spider == 'ecommerce':
        from habr_news.spiders.ecommerce import EcommerceSpider
        process.crawl(EcommerceSpider, category=args.category, stores=args.stores)

    process.start()


if __name__ == '__main__':
    main()
