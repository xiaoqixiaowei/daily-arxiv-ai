import scrapy
import os
import re


DEFAULT_CATEGORIES = "cs.CV,cs.AI,cs.RO,cs.CL"
DEPRECATED_DEFAULT_CATEGORIES = {
    "cs.CV,cs.CL,cs.AI,cs.GR,cs.LG",
    "cs.CV,cs.AI,cs.GR,cs.LG,cs.CL",
}


class ArxivSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = normalize_categories(os.environ.get("CATEGORIES"))
        categories = categories.split(",")
        # 保存目标分类列表，用于后续验证
        self.target_categories = set(map(str.strip, categories))
        self.start_urls = [
            f"https://arxiv.org/list/{cat}/new" for cat in self.target_categories
        ]  # 起始URL（计算机科学领域的最新论文）

    name = "arxiv"  # 爬虫名称
    allowed_domains = ["arxiv.org"]  # 允许爬取的域名

    def parse(self, response):
        # 提取每篇论文的信息
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        # 遍历每篇论文的详细信息
        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue
                
            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            # 获取论文ID
            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue
                
            arxiv_id = abstract_link.split("/")[-1]
            
            # 获取对应的论文描述部分 (dd元素)
            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue
            
            # 提取论文分类信息 - 在subjects部分
            subjects_text = " ".join(paper_dd.css(".list-subjects ::text").getall())
            
            if subjects_text:
                # 解析分类信息，通常格式如 "Computer Vision and Pattern Recognition (cs.CV)"
                # 提取括号中的分类代码
                categories_in_paper = re.findall(r'\(([^)]+)\)', subjects_text)
                
                # 检查论文分类是否与目标分类有交集
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    yield {
                        "id": arxiv_id,
                        "categories": list(paper_categories),  # 添加分类信息用于调试
                        "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
                        "abs": f"https://arxiv.org/abs/{arxiv_id}",
                        "authors": extract_authors(paper_dd),
                        "title": extract_title(paper_dd),
                        "comment": extract_comment(paper_dd),
                        "summary": extract_summary(paper_dd),
                    }
                    self.logger.info(f"Found paper {arxiv_id} with categories {paper_categories}")
                else:
                    self.logger.debug(f"Skipped paper {arxiv_id} with categories {paper_categories} (not in target {self.target_categories})")
            else:
                # 如果无法获取分类信息，记录警告但仍然返回论文（保持向后兼容）
                self.logger.warning(f"Could not extract categories for paper {arxiv_id}, including anyway")
                yield {
                    "id": arxiv_id,
                    "categories": [],
                    "pdf": f"https://arxiv.org/pdf/{arxiv_id}",
                    "abs": f"https://arxiv.org/abs/{arxiv_id}",
                    "authors": extract_authors(paper_dd),
                    "title": extract_title(paper_dd),
                    "comment": extract_comment(paper_dd),
                    "summary": extract_summary(paper_dd),
                }


def normalize_categories(raw_categories: str | None) -> str:
    categories = (raw_categories or DEFAULT_CATEGORIES).strip()
    normalized = ",".join(
        category.strip()
        for category in categories.split(",")
        if category.strip()
    )
    category_set = set(normalized.split(","))
    if (
        normalized in DEPRECATED_DEFAULT_CATEGORIES
        or "cs.GR" in category_set
        or "cs.LG" in category_set
    ):
        return DEFAULT_CATEGORIES
    return normalized or DEFAULT_CATEGORIES


def extract_title(paper_dd) -> str:
    text = " ".join(paper_dd.css(".list-title ::text").getall())
    return clean_descriptor_text(text, "Title:")


def extract_authors(paper_dd) -> list[str]:
    return [
        normalize_space(author)
        for author in paper_dd.css(".list-authors a::text").getall()
        if normalize_space(author)
    ]


def extract_comment(paper_dd) -> str | None:
    text = " ".join(paper_dd.css(".list-comments ::text").getall())
    comment = clean_descriptor_text(text, "Comments:")
    return comment or None


def extract_summary(paper_dd) -> str:
    paragraphs = []
    for paragraph in paper_dd.css("p.mathjax"):
        text = normalize_space(" ".join(paragraph.css("::text").getall()))
        if text:
            paragraphs.append(text)
    return "\n  ".join(paragraphs)


def clean_descriptor_text(text: str, descriptor: str) -> str:
    text = normalize_space(text)
    if text.startswith(descriptor):
        text = text[len(descriptor):]
    return normalize_space(text)


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
