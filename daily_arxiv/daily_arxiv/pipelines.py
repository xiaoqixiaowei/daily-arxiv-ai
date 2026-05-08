# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import arxiv
import os
from scrapy.exceptions import DropItem


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 100
        self.client = arxiv.Client(self.page_size)
        include_keywords = os.environ.get("INCLUDE_KEYWORDS", "")
        self.include_keywords = [
            keyword.strip().lower()
            for keyword in include_keywords.split(",")
            if keyword.strip()
        ]

    def process_item(self, item: dict, spider):
        item["pdf"] = f"https://arxiv.org/pdf/{item['id']}"
        item["abs"] = f"https://arxiv.org/abs/{item['id']}"
        search = arxiv.Search(
            id_list=[item["id"]],
        )
        paper = next(self.client.results(search))
        item["authors"] = [a.name for a in paper.authors]
        item["title"] = paper.title
        item["categories"] = paper.categories
        item["comment"] = paper.comment
        item["summary"] = paper.summary
        if self.include_keywords and not self.matches_include_keywords(item):
            raise DropItem(f"Skipped {item['id']} because it did not match INCLUDE_KEYWORDS")
        return item

    def matches_include_keywords(self, item: dict) -> bool:
        haystack = " ".join([
            item.get("title") or "",
            item.get("summary") or "",
            item.get("comment") or "",
            " ".join(item.get("categories") or []),
        ]).lower()
        return any(keyword in haystack for keyword in self.include_keywords)
