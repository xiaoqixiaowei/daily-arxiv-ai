# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import arxiv
import os
from scrapy.exceptions import DropItem


DEFAULT_INCLUDE_KEYWORDS = [
    "game agent",
    "game agents",
    "gaming agent",
    "game ai",
    "game-playing",
    "game playing",
    "minecraft",
    "videogame",
    "video game",
    "video games",
    "game environment",
    "game environments",
    "game benchmark",
    "game benchmarks",
    "gameplay",
    "game engine",
    "game engines",
    "in-game",
    "cross-game",
    "super mario",
    "card games",
    "role-playing game",
    "video role-playing",
    "rpg generation",
    "endless runner game",
]

GAME_MEDIA_TERMS = [
    "video game",
    "video games",
    "videogame",
    "gameplay",
    "game engine",
    "game engines",
    "in-game",
    "cross-game",
    "minecraft",
    "super mario",
    "card games",
    "role-playing game",
    "video role-playing",
    "rpg generation",
    "endless runner game",
]

NON_VIDEO_GAME_TERMS = [
    "game theory",
    "game-theoretic",
    "nash",
    "markov games",
    "mean-field games",
    "potential games",
    "impartial games",
    "specification gaming",
    "gaming the metric",
    "auditee gaming",
    "strategic gaming",
    "pricing agents",
    "cross-sectional quantitative trading",
    "fake news",
    "cognitive workload",
    "healthcare workers",
    "audio large language models",
    "personality-shaped emotional responses",
    "persona expressivity",
    "computationally hard problems",
    "misalignment contagion",
    "fake news",
    "table tennis",
    "bug report",
    "politically aligned",
    "speech-driven facial animation",
    "agentic video generation",
    "ethical data communication",
    "forest management",
    "six-way lightmaps",
    "3d avatars",
    "transformational games",
    "language preservation",
    "video benchmark for complex perception",
    "garment deformation",
    "xr prototyping",
]

AGENT_CONTEXT_TERMS = [
    "agent",
    "agents",
    "vlm",
    "vlms",
    "reinforcement learning",
    "decision-making",
    "decision making",
    "planning",
    "control",
    "navigation",
    "world model",
    "world models",
    "embodied",
    "environment",
    "environments",
    "benchmark",
    "benchmarks",
]


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 100
        self.client = arxiv.Client(self.page_size)
        include_keywords = os.environ.get("INCLUDE_KEYWORDS", "")
        self.include_keywords = [
            keyword.strip().lower()
            for keyword in include_keywords.split(",")
            if keyword.strip()
        ] or DEFAULT_INCLUDE_KEYWORDS

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
        if not self.matches_include_keywords(item):
            raise DropItem(f"Skipped {item['id']} because it did not match INCLUDE_KEYWORDS")
        return item

    def matches_include_keywords(self, item: dict) -> bool:
        haystack = " ".join([
            item.get("title") or "",
            item.get("summary") or "",
            item.get("comment") or "",
            " ".join(item.get("categories") or []),
        ]).lower()
        if any(term in haystack for term in NON_VIDEO_GAME_TERMS):
            return False

        if any(keyword in haystack for keyword in self.include_keywords):
            return True

        has_game_context = any(term in haystack for term in GAME_MEDIA_TERMS)
        has_agent_context = any(term in haystack for term in AGENT_CONTEXT_TERMS)
        return has_game_context and has_agent_context
