"""专题预设配置的加载与打分过滤。

配置源是仓库根目录的 topics.json，GUI（专题下拉）与 cli.py（批量抓取）共用，
改关键词/打分规则不需要动代码。

筛选逻辑是**标题加权打分**而非简单包含：强相关词（二进制/逆向/IDA/pwn…）
给正分，噪音词（git/patch-package/前端…）给负分，标题总分 >= min_score 才收录。
这样可以避开 CSDN 搜索 API 把 "git patch"、"patch-package" 之类当成命中的问题。
"""
import json
import os
from typing import Dict, List, Optional, Tuple

_TOPICS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "topics.json")

_CACHE: Optional[Dict] = None


def load_topics(path: str = _TOPICS_PATH, force: bool = False) -> Dict:
    """读取专题配置，返回 {topic_id: topic_dict}，保留原始顺序。"""
    global _CACHE
    if _CACHE is not None and not force and path == _TOPICS_PATH:
        return _CACHE

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    topics = {}
    for topic in data.get("topics", []):
        if "id" not in topic:
            continue
        topic.setdefault("keywords", [])
        topic.setdefault("score_terms", [])
        topic.setdefault("exclude_any", [])
        topic.setdefault("min_score", 4)
        topics[topic["id"]] = topic

    if path == _TOPICS_PATH:
        _CACHE = topics
    return topics


def topic_names(topics: Optional[Dict] = None) -> List[str]:
    topics = topics or load_topics()
    return [f"{t['name']}（{tid}）" for tid, t in topics.items()]


def get_topic(topic_id: str, topics: Optional[Dict] = None) -> Dict:
    topics = topics or load_topics()
    if topic_id not in topics:
        raise KeyError(f"未知专题 id: {topic_id}（可用：{', '.join(topics)}）")
    return topics[topic_id]


def score_title(title: str, topic: Dict) -> int:
    """按 score_terms 给标题打分，并按特殊词出现次数累加（最多计 2 次）。"""
    lowered = (title or "").lower()
    total = 0
    for group in topic.get("score_terms", []):
        weight = int(group.get("weight", 0))
        hits = 0
        for term in group.get("terms", []):
            if term.lower() in lowered:
                hits += 1
        total += weight * min(hits, 2)
    return total


def title_matches(title: str, topic: Dict) -> bool:
    """标题是否达到专题收录阈值。"""
    lowered = (title or "").lower()
    excludes = [w.lower() for w in topic.get("exclude_any", [])]
    if any(w in lowered for w in excludes):
        return False
    return score_title(title, topic) >= int(topic.get("min_score", 4))


def filter_results(results: List[Dict], topic: Optional[Dict] = None) -> List[Dict]:
    """按标题分数过滤，然后按 URL 去重（保留分数最高的一条）。"""
    scored: List[Tuple[int, Dict]] = []
    for item in results:
        url = item.get("url", "")
        title = item.get("title", "")
        if not url:
            continue
        if topic is None:
            scored.append((0, item))
            continue
        score = score_title(title, topic)
        if score < int(topic.get("min_score", 4)):
            continue
        entry = dict(item)
        entry["score"] = score
        scored.append((score, entry))

    best: Dict[str, Tuple[int, Dict]] = {}
    for score, item in scored:
        url = item["url"]
        if url not in best or score > best[url][0]:
            best[url] = (score, item)

    kept = [item for _, item in best.values()]
    kept.sort(key=lambda entry: entry.get("score", 0), reverse=True)
    return kept
