# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
import os
import re

import arxiv
from scrapy.exceptions import DropItem


DEFAULT_INCLUDE_KEYWORDS = [
    "vision-language-action",
    "vision language action",
    "vla",
    "robot foundation model",
    "robotic foundation model",
    "embodied agent",
    "embodied agents",
    "game agent",
    "game agents",
    "minecraft agent",
    "minecraft agents",
]

DEPRECATED_INCLUDE_KEYWORD_SETS = {
    (
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
    ),
    (
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
    ),
}

MODEL_TERMS = [
    "vision-language model",
    "vision language model",
    "vision-language models",
    "vision language models",
    "large vision-language model",
    "large vision-language models",
    "large vision language model",
    "large vision language models",
    "visual language model",
    "visual language models",
    "video-language model",
    "video language model",
    "video-language models",
    "video language models",
    "multimodal large language model",
    "multimodal large language models",
    "multimodal llm",
    "multimodal llms",
    "vision-language-action",
    "vision language action",
    "vlm",
    "vlms",
    "lvlm",
    "lvlms",
    "mllm",
    "mllms",
    "llm",
    "llms",
    "vla",
]

ROBOTICS_TERMS = [
    "robot",
    "robots",
    "robotic",
    "robotics",
    "embodied",
    "manipulation",
    "manipulator",
    "navigation",
    "locomotion",
    "grasp",
    "grasping",
    "mobile robot",
    "mobile robots",
    "humanoid",
    "humanoids",
    "autonomous driving",
    "motion planning",
    "path planning",
    "task planning",
    "robot planning",
    "robotic planning",
    "embodied planning",
    "robot control",
    "robotic control",
    "embodied control",
    "visuomotor control",
    "visual motor control",
    "physical world",
    "3d scene",
    "3d scenes",
    "world model",
    "world models",
    "world modeling",
    "world modelling",
]

STRONG_ROBOTICS_TERMS = [
    "robot",
    "robots",
    "robotic",
    "robotics",
    "embodied",
    "manipulation",
    "manipulator",
    "navigation",
    "locomotion",
    "grasp",
    "grasping",
    "mobile robot",
    "mobile robots",
    "humanoid",
    "humanoids",
    "autonomous driving",
    "physical world",
    "3d scene",
    "3d scenes",
    "world model",
    "world models",
]

GAME_TERMS = [
    "game agent",
    "game agents",
    "game-playing agent",
    "game playing agent",
    "game-playing agents",
    "game playing agents",
    "game environment",
    "game environments",
    "game benchmark",
    "game benchmarks",
    "game-based benchmark",
    "game based benchmark",
    "gameplay reasoning",
    "gameplay understanding",
    "gameplay video understanding",
    "minecraft",
    "minecraft agent",
    "minecraft agents",
    "minecraft benchmark",
    "minecraft environment",
    "minecraft environments",
    "video game",
    "video games",
    "videogame",
    "game ai",
    "game engine",
    "game engines",
]

EXCLUDED_APPLICATION_TERMS = [
    "medical",
    "clinical",
    "radiology",
    "radiological",
    "retinal",
    "retina",
    "ct analysis",
    "mri",
    "x-ray",
    "chest x-ray",
    "surgical",
    "surgery",
    "education",
    "educational",
    "nursing",
    "chart",
    "charts",
    "plot",
    "anime",
    "food",
    "satellite",
    "remote sensing",
    "geospatial",
    "aerial",
    "microscopy",
    "agriculture",
]

NEGATIVE_TERMS = [
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

DEFAULT_MAX_PAPERS = 10
DEFAULT_ARXIV_API_DELAY_SECONDS = 8.0
DEFAULT_ARXIV_API_NUM_RETRIES = 5


class DailyArxivPipeline:
    def __init__(self):
        self.page_size = 1
        self.max_papers = get_int_env("MAX_PAPERS", DEFAULT_MAX_PAPERS)
        self.kept_count = 0
        self.client = arxiv.Client(
            page_size=self.page_size,
            delay_seconds=get_float_env(
                "ARXIV_API_DELAY_SECONDS",
                DEFAULT_ARXIV_API_DELAY_SECONDS,
            ),
            num_retries=get_int_env(
                "ARXIV_API_NUM_RETRIES",
                DEFAULT_ARXIV_API_NUM_RETRIES,
            ),
        )
        include_keywords = os.environ.get("INCLUDE_KEYWORDS", "")
        self.include_keywords = [
            keyword.strip().lower()
            for keyword in include_keywords.split(",")
            if keyword.strip()
        ]
        if tuple(self.include_keywords) in DEPRECATED_INCLUDE_KEYWORD_SETS:
            self.include_keywords = []
        self.include_keywords = self.include_keywords or DEFAULT_INCLUDE_KEYWORDS

    def process_item(self, item: dict, spider):
        if self.max_papers > 0 and self.kept_count >= self.max_papers:
            self.close_for_max_papers(spider)
            raise DropItem(f"Skipped {item['id']}: max_papers_reached({self.max_papers})")

        item["pdf"] = f"https://arxiv.org/pdf/{item['id']}"
        item["abs"] = f"https://arxiv.org/abs/{item['id']}"
        search = arxiv.Search(
            id_list=[item["id"]],
            max_results=1,
        )
        try:
            paper = next(self.client.results(search))
        except StopIteration as exc:
            spider.logger.warning("dropped: arxiv_api_empty %s", item["id"])
            raise DropItem(f"Skipped {item['id']}: arxiv_api_empty") from exc
        except arxiv.HTTPError as exc:
            spider.logger.warning("dropped: arxiv_api_error(%s) %s", exc, item["id"])
            raise DropItem(f"Skipped {item['id']}: arxiv_api_error({exc})") from exc

        item["authors"] = [a.name for a in paper.authors]
        item["title"] = paper.title
        item["categories"] = paper.categories
        item["comment"] = paper.comment
        item["summary"] = paper.summary
        matched, reason = self.get_match_reason(item)
        if not matched:
            spider.logger.info("dropped: %s %s", reason, item["id"])
            raise DropItem(f"Skipped {item['id']}: {reason}")
        spider.logger.info("kept: %s %s", reason, item["id"])
        self.kept_count += 1
        if self.max_papers > 0 and self.kept_count >= self.max_papers:
            self.close_for_max_papers(spider)
        return item

    def close_for_max_papers(self, spider):
        spider.logger.info(
            "max_papers reached: closing spider after %s kept papers",
            self.kept_count,
        )
        spider.crawler.engine.close_spider(
            spider,
            reason=f"max_papers_{self.max_papers}",
        )

    def matches_include_keywords(self, item: dict) -> bool:
        matched, _ = self.get_match_reason(item)
        return matched

    def get_match_reason(self, item: dict) -> tuple[bool, str]:
        haystack = " ".join([
            item.get("title") or "",
            item.get("summary") or "",
            item.get("comment") or "",
            " ".join(item.get("categories") or []),
        ]).lower()

        negative_hits = find_terms(haystack, NEGATIVE_TERMS)
        if negative_hits:
            return False, f"negative_term({negative_hits[0]})"

        forced_hits = find_terms(haystack, self.include_keywords)
        robotics_hits = find_terms(haystack, ROBOTICS_TERMS)
        strong_robotics_hits = find_terms(haystack, STRONG_ROBOTICS_TERMS)
        game_hits = find_terms(haystack, GAME_TERMS)
        if forced_hits:
            return True, f"strong_include({forced_hits[0]})"

        model_hits = find_terms(haystack, MODEL_TERMS)
        if not model_hits:
            return False, "missing_model_term"

        application_hits = find_terms(haystack, EXCLUDED_APPLICATION_TERMS)
        if application_hits and not (strong_robotics_hits or game_hits):
            return False, f"generic_vlm_application({application_hits[0]})"

        if game_hits:
            return True, f"llm/vlm+game({game_hits[0]})"

        if robotics_hits:
            return True, f"vlm+robotics({robotics_hits[0]})"

        return False, "generic_vlm_without_robotics_or_game"


def find_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term_in_text(term, text)]


def term_in_text(term: str, text: str) -> bool:
    if not term:
        return False
    term = term.lower()
    if re.fullmatch(r"[a-z0-9]+", term) and len(term) <= 5:
        return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
    return term in text


def get_int_env(name: str, default: int) -> int:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        return int(raw_value)
    except ValueError:
        return default


def get_float_env(name: str, default: float) -> float:
    raw_value = os.environ.get(name, str(default)).strip()
    try:
        return float(raw_value)
    except ValueError:
        return default
