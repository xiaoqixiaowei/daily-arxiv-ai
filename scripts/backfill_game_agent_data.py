import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

import arxiv

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "daily_arxiv"))

from daily_arxiv.pipelines import DailyArxivPipeline


DEFAULT_QUERIES = [
    '"vision-language model"',
    '"vision language model"',
    '"VLM"',
    '"multimodal large language model"',
    '"MLLM"',
    '"video-language model"',
    '"world model"',
    '"world models"',
    '"world modeling"',
    '"video world model"',
    '"generative world model"',
    '"action-conditioned world model"',
    '"embodied world model"',
    '"game agent"',
    '"game agents"',
    '"game-playing agent"',
    '"game playing agent"',
    '"multimodal game agent"',
    '"autonomous game agent"',
    '"LLM game agent"',
    '"VLM game agent"',
    '"game AI"',
    '"game benchmark"',
    '"game environment"',
    '"gameplay reasoning"',
    '"gameplay understanding"',
    '"Minecraft benchmark"',
    '"Minecraft agent"',
]


def normalize_id(entry_id: str) -> str:
    return entry_id.rsplit("/", 1)[-1].split("v", 1)[0]


def build_search_query() -> str:
    return " OR ".join(f"all:{query}" for query in DEFAULT_QUERIES)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-date", default=date.today().isoformat())
    parser.add_argument("--max-results", type=int, default=80)
    args = parser.parse_args()

    default_categories = "cs.CV,cs.AI,cs.RO,cs.CL"
    category_value = os.environ.get("CATEGORIES", default_categories) or default_categories
    categories = {
        category.strip()
        for category in category_value.split(",")
        if category.strip()
    }

    pipeline = DailyArxivPipeline()
    client = arxiv.Client(page_size=100, delay_seconds=3)
    search = arxiv.Search(
        query=build_search_query(),
        max_results=args.max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    papers = []
    seen = set()
    for paper in client.results(search):
        paper_categories = list(paper.categories)
        primary_category = paper_categories[0] if paper_categories else ""
        if categories and primary_category not in categories:
            continue

        item = {
            "id": normalize_id(paper.entry_id),
            "categories": paper_categories,
            "pdf": f"https://arxiv.org/pdf/{normalize_id(paper.entry_id)}",
            "abs": f"https://arxiv.org/abs/{normalize_id(paper.entry_id)}",
            "authors": [author.name for author in paper.authors],
            "title": paper.title,
            "comment": paper.comment,
            "summary": paper.summary,
        }
        if item["id"] in seen or not pipeline.matches_include_keywords(item):
            continue
        seen.add(item["id"])
        papers.append(item)

    raw_output = f"data/{args.output_date}.jsonl"
    with open(raw_output, "w", encoding="utf-8") as file:
        for paper in papers:
            file.write(json.dumps(paper, ensure_ascii=False) + "\n")

    print(f"Wrote {len(papers)} raw papers to {raw_output}")


if __name__ == "__main__":
    main()
