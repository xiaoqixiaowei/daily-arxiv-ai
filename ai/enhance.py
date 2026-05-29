import os
import json
import sys
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from threading import Lock
# INSERT_YOUR_CODE
import requests

import dotenv
import argparse
from tqdm import tqdm

from langchain_openai import ChatOpenAI
from langchain.prompts import (
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)
from structure import Structure

if os.path.exists('.env'):
    dotenv.load_dotenv()
template = open("template.txt", "r").read()
system = open("system.txt", "r").read()
json_output_instruction = """
Return only one valid JSON object with exactly these string fields:
{{
  "tldr": "...",
  "motivation": "...",
  "method": "...",
  "result": "...",
  "conclusion": "..."
}}
Do not wrap the JSON in Markdown fences. Do not add any text before or after the JSON.
"""

REQUIRED_AI_FIELDS = ["tldr", "motivation", "method", "result", "conclusion"]

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=str, required=True, help="jsonline data file")
    parser.add_argument("--max_workers", type=int, default=1, help="Maximum number of parallel workers")
    parser.add_argument("--request_interval", type=float, default=None, help="Minimum seconds between LLM requests")
    return parser.parse_args()

def wait_for_llm_slot(rate_lock: Lock, rate_state: Dict, request_interval: float):
    """Keep LLM calls under provider RPM limits across worker threads."""
    if request_interval <= 0:
        return

    with rate_lock:
        now = time.monotonic()
        wait_seconds = rate_state["next_request_at"] - now
        if wait_seconds > 0:
            time.sleep(wait_seconds)
            now = time.monotonic()
        rate_state["next_request_at"] = now + request_interval

def process_single_item(chain, item: Dict, language: str, rate_lock: Lock, rate_state: Dict, request_interval: float) -> Dict:
    def is_sensitive(content: str) -> bool:
        """
        调用 spam.dw-dengwei.workers.dev 接口检测内容是否包含敏感词。
        返回 True 表示触发敏感词，False 表示未触发。
        """
        try:
            resp = requests.post(
                "https://spam.dw-dengwei.workers.dev",
                json={"text": content},
                timeout=5
            )
            if resp.status_code == 200:
                result = resp.json()
                # 约定接口返回 {"sensitive": true/false, ...}
                return result.get("sensitive", True)
            else:
                # 如果接口异常，默认放行，避免网络波动清空整日结果
                print(f"Sensitive check failed with status {resp.status_code}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Sensitive check error: {e}", file=sys.stderr)
            return False

    def check_github_code(content: str) -> Dict:
        """提取并验证 GitHub 链接"""
        code_info = {}

        # 1. 优先匹配 github.com/owner/repo 格式
        github_pattern = r"https?://github\.com/([a-zA-Z0-9-_]+)/([a-zA-Z0-9-_\.]+)"
        match = re.search(github_pattern, content)

        if match:
            owner, repo = match.groups()
            # 清理 repo 名称，去掉可能的 .git 后缀或末尾的标点
            repo = repo.rstrip(".git").rstrip(".,)")

            full_url = f"https://github.com/{owner}/{repo}"
            code_info["code_url"] = full_url

            # 尝试调用 GitHub API 获取信息
            github_token = os.environ.get("TOKEN_GITHUB")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"token {github_token}"

            try:
                api_url = f"https://api.github.com/repos/{owner}/{repo}"
                resp = requests.get(api_url, headers=headers, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    code_info["code_stars"] = data.get("stargazers_count", 0)
                    code_info["code_last_update"] = data.get("pushed_at", "")[:10]
            except Exception:
                # API 调用失败不影响主流程
                pass
            return code_info

        # 2. 如果没有 github.com，尝试匹配 github.io
        github_io_pattern = r"https?://[a-zA-Z0-9-_]+\.github\.io(?:/[a-zA-Z0-9-_\.]+)*"
        match_io = re.search(github_io_pattern, content)

        if match_io:
            url = match_io.group(0)
            # 清理末尾标点
            url = url.rstrip(".,)")
            code_info["code_url"] = url
            # github.io 不进行 star 和 update 判断

        return code_info

    # 检查 summary 字段
    if is_sensitive(item.get("summary", "")):
        return None

    # 检测代码可用性
    code_info = check_github_code(item.get("summary", ""))
    if code_info:
        item.update(code_info)

    """处理单个数据项"""
    default_ai_fields = build_fallback_ai(item, language)

    try:
        if chain is None:
            item['AI'] = default_ai_fields
        else:
            wait_for_llm_slot(rate_lock, rate_state, request_interval)
            response = chain.invoke({
                "language": language,
                "content": item['summary']
            })
            content = response.content if hasattr(response, "content") else str(response)
            item['AI'] = parse_ai_response(content, default_ai_fields, item.get('id', 'unknown'))
    except Exception as e:
        # Catch any other exceptions and provide default values
        print(f"Unexpected error for {item.get('id', 'unknown')}: {e}", file=sys.stderr)
        item['AI'] = default_ai_fields

    # Final validation to ensure all required fields exist
    for field in REQUIRED_AI_FIELDS:
        if field not in item['AI']:
            item['AI'][field] = default_ai_fields[field]

    # 检查 AI 生成的所有字段
    for v in item.get("AI", {}).values():
        if is_sensitive(str(v)):
            return None
    return item

def split_sentences(text: str) -> List[str]:
    """Split English/Chinese abstract text into compact sentence chunks."""
    if not text:
        return []
    matches = re.findall(r"[^.!?。！？]+[.!?。！？]+|[^.!?。！？]+$", text)
    return [sentence.strip() for sentence in matches if sentence.strip()]

def first_matching_sentence(sentences: List[str], patterns: List[str], fallback_index: int = 0) -> str:
    compiled = [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    for sentence in sentences:
        if any(pattern.search(sentence) for pattern in compiled):
            return sentence
    if not sentences:
        return ""
    fallback_index = max(0, min(fallback_index, len(sentences) - 1))
    return sentences[fallback_index]

def build_fallback_ai(item: Dict, language: str) -> Dict:
    """
    Build a non-empty structured preview when the LLM call fails.
    This keeps downstream Markdown/site rendering alive without pretending
    the fallback is a full AI-written analysis.
    """
    summary = item.get("summary", "")
    sentences = split_sentences(summary)
    first_two = " ".join(sentences[:2]) or summary

    motivation = first_matching_sentence(
        sentences,
        ["ready", "challenge", "gap", "remain", "lack", "underexplored", "problem"],
        0
    )
    method = first_matching_sentence(
        sentences,
        ["introduce", "present", "propose", "develop", "framework", "benchmark", "system"],
        1
    )
    result = first_matching_sentence(
        sentences,
        ["result", "show", "evaluate", "achieve", "yield", "improve", "experiment"],
        2
    )
    conclusion = sentences[-1] if sentences else first_two

    return {
        "tldr": f"Raw abstract preview: {first_two}",
        "motivation": f"Motivation: {motivation}",
        "method": f"Method: {method}",
        "result": f"Result: {result}",
        "conclusion": f"Conclusion: {conclusion}"
    }

def parse_ai_response(content: str, default_ai_fields: Dict, paper_id: str) -> Dict:
    """Parse a JSON object from a normal chat completion response."""
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            print(f"Failed to find JSON in AI response for {paper_id}", file=sys.stderr)
            return default_ai_fields
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON for {paper_id}: {e}", file=sys.stderr)
            return default_ai_fields

    if not isinstance(parsed, dict):
        print(f"AI response for {paper_id} is not a JSON object", file=sys.stderr)
        return default_ai_fields

    try:
        return Structure.model_validate({**default_ai_fields, **parsed}).model_dump()
    except Exception as e:
        print(f"Failed to validate AI response for {paper_id}: {e}", file=sys.stderr)
        return {**default_ai_fields, **parsed}

def process_all_items(data: List[Dict], model_name: str, language: str, max_workers: int) -> List[Dict]:
    """并行处理所有数据项"""
    base_url = os.environ.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_API_BASE")
    request_interval = float(os.environ.get("LLM_REQUEST_INTERVAL_SECONDS") or "6.5")
    chain = None

    if os.environ.get("OPENAI_API_KEY"):
        llm = ChatOpenAI(model=model_name, base_url=base_url)
        print('Connect to:', model_name, 'base_url:', base_url or 'default', 'request_interval:', request_interval, file=sys.stderr)

        prompt_template = ChatPromptTemplate.from_messages([
            SystemMessagePromptTemplate.from_template(system + json_output_instruction),
            HumanMessagePromptTemplate.from_template(template=template)
        ])

        chain = prompt_template | llm
    else:
        print('OPENAI_API_KEY is not set; using structured fallback previews.', file=sys.stderr)

    # 使用线程池并行处理
    processed_data = [None] * len(data)  # 预分配结果列表
    rate_lock = Lock()
    rate_state = {"next_request_at": 0.0}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_idx = {
            executor.submit(process_single_item, chain, item, language, rate_lock, rate_state, request_interval): idx
            for idx, item in enumerate(data)
        }

        # 使用tqdm显示进度
        for future in tqdm(
            as_completed(future_to_idx),
            total=len(data),
            desc="Processing items"
        ):
            idx = future_to_idx[future]
            try:
                result = future.result()
                processed_data[idx] = result
            except Exception as e:
                print(f"Item at index {idx} generated an exception: {e}", file=sys.stderr)
                # Add default AI fields to ensure consistency
                processed_data[idx] = data[idx]
                processed_data[idx]['AI'] = {
                    "tldr": "Processing failed",
                    "motivation": "Processing failed",
                    "method": "Processing failed",
                    "result": "Processing failed",
                    "conclusion": "Processing failed"
                }

    return processed_data

def main():
    args = parse_args()
    model_name = os.environ.get("MODEL_NAME") or 'glm-5.1'
    language = os.environ.get("LANGUAGE") or 'Chinese'
    if args.request_interval is not None:
        os.environ["LLM_REQUEST_INTERVAL_SECONDS"] = str(args.request_interval)

    # 检查并删除目标文件
    target_file = args.data.replace('.jsonl', f'_AI_enhanced_{language}.jsonl')
    if os.path.exists(target_file):
        os.remove(target_file)
        print(f'Removed existing file: {target_file}', file=sys.stderr)

    # 读取数据
    data = []
    with open(args.data, "r") as f:
        for line in f:
            data.append(json.loads(line))

    # 去重
    seen_ids = set()
    unique_data = []
    for item in data:
        if item['id'] not in seen_ids:
            seen_ids.add(item['id'])
            unique_data.append(item)

    data = unique_data
    print('Open:', args.data, file=sys.stderr)

    # 并行处理所有数据
    processed_data = process_all_items(
        data,
        model_name,
        language,
        args.max_workers
    )

    # 保存结果
    with open(target_file, "w") as f:
        for item in processed_data:
            if item is not None:
                f.write(json.dumps(item) + "\n")

if __name__ == "__main__":
    main()
