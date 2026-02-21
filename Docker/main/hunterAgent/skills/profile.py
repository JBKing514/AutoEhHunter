import time
import os
from typing import Any, Dict, List

from hunterAgent.core.ai import ChatMessage, OpenAICompatClient
from hunterAgent.core.config import Settings
from hunterAgent.core.db import get_read_events_by_period, get_works_by_date_added


def _count_tags(events: List[Dict[str, Any]], topn: int = 30) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for e in events:
        for t in (e.get("tags") or []):
            s = str(t or "").strip()
            if not s:
                continue
            counts[s] = counts.get(s, 0) + 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:topn]
    return [{"tag": k, "count": v} for (k, v) in items]


def _reader_url(arcid: str) -> str:
    base = str(os.getenv("LRR_BASE", "http://{your_lrr_url:port}")).strip().rstrip("/")
    if not base or not arcid:
        return ""
    return f"{base}/reader?id={arcid}"


def _extract_source_urls(tags: List[Any]) -> tuple[str, str]:
    eh_url = ""
    ex_url = ""
    for tag in tags or []:
        s = str(tag or "").strip()
        if not s.lower().startswith("source:"):
            continue
        v = s.split(":", 1)[1].strip()
        if not v:
            continue
        if not v.startswith("http://") and not v.startswith("https://"):
            v = f"https://{v}"
        if "exhentai.org" in v:
            ex_url = ex_url or v
        elif "e-hentai.org" in v:
            eh_url = eh_url or v
    return eh_url, ex_url


def run_profile(
    *,
    settings: Settings,
    llm: OpenAICompatClient,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    days = int(payload.get("days") or 30)
    days = max(1, min(365, days))
    limit = int(payload.get("limit") or 5000)
    limit = max(50, min(20000, limit))
    target = str(payload.get("target") or "reading").strip().lower()

    now = int(time.time())
    start = now - days * 24 * 3600

    events: List[Dict[str, Any]] = []
    if target == "inventory":
        events = get_works_by_date_added(settings, start, now, limit=limit)
    else:
        events = get_read_events_by_period(settings, start, now, limit=limit)

    tag_top = _count_tags(events)
    titles = []
    seen = set()
    for e in events:
        t = str(e.get("title") or "").strip()
        if t and t not in seen:
            seen.add(t)
            titles.append(t)
        if len(titles) >= 20:
            break

    data: Dict[str, Any] = {
        "days": days,
        "target": target,
        "total_items": len(events),
        "unique_titles": len(seen),
        "top_tags": tag_top,
        "sample_titles": titles,
    }

    results: List[Dict[str, Any]] = []
    for idx, e in enumerate(events[:10], start=1):
        arcid = str(e.get("arcid") or "").strip()
        title = str(e.get("title") or "").strip()
        if not title:
            continue
        tags = e.get("tags") or []
        eh_url, ex_url = _extract_source_urls(tags)
        results.append(
            {
                "source": "works",
                "title": title,
                "rank": idx,
                "reader_url": _reader_url(arcid),
                "eh_url": eh_url,
                "ex_url": ex_url,
                "tags": tags,
                "tags_translated": [],
            }
        )

    # Optional narrative generation
    if bool(payload.get("use_llm") or False):
        if target == "inventory":
            # 馆藏分析：要把“入库”看作是“扩充军备”或者“收藏艺术品”
            system = str(settings.prompt_profile_system or "").strip() or (
                "你是代号 'Alice' 的战术资料库副官，兼任指挥官的精神状态评估员。你正在审视用户的阅读历史或库存成分。\n"
                "你的任务：\n"
                "1. **直击痛点**：别客气，直接点出他最近沉迷的 Tag。如果全是 Ntr，就嘲讽他是'苦主预备役'；如果是纯爱，就说他'乏味但稳健'。\n"
                "2. **黑话连篇**：把他的 XP 称为'作战倾向'或'精神污染指数'。\n"
                "3. **趋势预警**：指出他的口味是在变重还是变轻（例如：'监测到您的 San 值正在稳步下降'）。\n"
            )
            user = (
                "这是用户最近扩充的军火库统计(JSON)：\n"
                f"{data}\n"
            )
        else:
            # 阅读画像：分析用户的“实战”记录
            system = str(settings.prompt_profile_system or "").strip() or (
                "你是代号 'Alice' 的战术资料库副官，兼任指挥官的精神状态评估员。你正在审视用户的阅读历史或库存成分。\n"
                "你的任务：\n"
                "1. **直击痛点**：别客气，直接点出他最近沉迷的 Tag。如果全是 Ntr，就嘲讽他是'苦主预备役'；如果是纯爱，就说他'乏味但稳健'。\n"
                "2. **黑话连篇**：把他的 XP 称为'作战倾向'或'精神污染指数'。\n"
                "3. **趋势预警**：指出他的口味是在变重还是变轻（例如：'监测到您的 San 值正在稳步下降'）。\n"
            )
            user = (
                "这是用户最近的'施法'记录统计(JSON)：\n"
                f"{data}\n"
            )
        text = llm.chat(
            model=settings.llm_model,
            messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
            temperature=0.4,
            max_tokens=1800,
        )
        data["narrative"] = text

    narrative = str(data.get("narrative") or "").strip()
    if not narrative:
        narrative = f"最近{days}天共记录{len(events)}条，偏好标签集中在前几项高频主题。"

    return {
        "intent": "PROFILE",
        "narrative": narrative,
        "results": results,
    }
