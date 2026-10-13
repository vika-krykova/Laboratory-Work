BOT_NAME = "habr_news"

SPIDER_MODULES = ["habr_news.spiders"]
NEWSPIDER_MODULE = "habr_news.spiders"

ADDONS = {}

ROBOTSTXT_OBEY = True

CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 1

DOWNLOADER_MIDDLEWARES = {
    "scrapy.downloadermiddlewares.useragent.UserAgentMiddleware": None,
    "scrapy_user_agents.middlewares.RandomUserAgentMiddleware": 400,
}

ITEM_PIPELINES = {
    "habr_news.pipelines.CleaningPipeline": 300,
    "habr_news.pipelines.DuplicationPipeline": 400,
    "habr_news.pipelines.ValidationPipeline": 500,
}

FEED_EXPORT_ENCODING = "utf-8"

RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 429]

RANDOMIZE_DOWNLOAD_DELAY = True

CONCURRENT_REQUESTS = 8

LOG_LEVEL = "INFO"

DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
}

TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor"

PLAYWRIGHT_BROWSER_TYPE = "chromium"

PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--no-sandbox",
        "--disable-dev-shm-usage",
    ],
}

PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 30000