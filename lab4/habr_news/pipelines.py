import ftfy
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem


class CleaningPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        for field in ['title', 'summary', 'hub']:
            if adapter.get(field):
                text = ftfy.fix_text(adapter[field])
                text = ' '.join(text.split())
                adapter[field] = text

        return item


class DuplicationPipeline:
    def __init__(self):
        self.seen_urls = set()

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        url = adapter.get('url')
        if url in self.seen_urls:
            raise DropItem(f'Дубликат: {url}')
        self.seen_urls.add(url)
        return item


class ValidationPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)
        required = ['title', 'url']
        for field in required:
            if not adapter.get(field):
                raise DropItem(f'Отсутствует поле "{field}": {dict(item)}')
        return item