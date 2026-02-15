import time
import os
from typing import Any, Dict, List, Tuple

from hunterAgent.core.ai import ChatMessage, OpenAICompatClient
from hunterAgent.core.config import Settings
from hunterAgent.core.db import get_read_events_by_period


def _period_window(report_type: str) -> Tuple[int, int, str]:
    now = int(time.time())
    rt = (report_type or "daily").strip().lower()
    if rt == "daily":
        start = now - 24 * 3600
        label = "Last 24 hours"
    elif rt == "weekly":
        start = now - 7 * 24 * 3600
        label = "Last 7 days"
    elif rt == "monthly":
        start = now - 30 * 24 * 3600
        label = "Last 30 days"
    elif rt == "full":
        start = 0
        label = "All time"
    else:
        start = now - 24 * 3600
        label = "Last 24 hours"
    return start, now, label


def _summarize_events(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    title_set = set()
    tag_counts: Dict[str, int] = {}
    for e in events:
        t = (e.get("title") or "").strip()
        if t:
            title_set.add(t)
        for tag in (e.get("tags") or []):
            s = str(tag).strip()
            if not s:
                continue
            tag_counts[s] = tag_counts.get(s, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    return {
        "total_reads": len(events),
        "unique_titles": len(title_set),
        "top_tags": [{"tag": k, "count": v} for k, v in top_tags],
    }


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


def run_report(
    *,
    settings: Settings,
    llm: OpenAICompatClient,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    report_type = str(payload.get("type") or "daily")
    start, end, label = _period_window(report_type)
    limit = int(payload.get("limit") or 5000)
    limit = max(50, min(20000, limit))

    events = get_read_events_by_period(settings, start, end, limit=limit)
    summary = _summarize_events(events)

    max_events = int(payload.get("max_events") or 120)
    sample = events[: max(0, min(500, max_events))]
    sample_compact = [
        {"read_time": e.get("read_time"), "title": e.get("title"), "tags": (e.get("tags") or [])[:40]}
        for e in sample
    ]

    system = (
        "你是代号 'Alice' 的战术资料库副官。现在是例行汇报时间，你需要总结指定周期内的'战术行动'（阅读记录）。\n"
        "你的任务：\n"
        "1. **数据可视化**：用文字把枯燥的阅读数描述成'作战场次'或'弹药消耗量'。\n"
        "2. **高光时刻**：点名表扬（或挂出）他看的最多的那本。\n"
        "3. **战术建议**：基于当前数据，给出一个幽默的后续建议（例如：'建议适当补充全年龄向资源以缓解审美疲劳'）。\n"
    )
    user = (
        "请根据下列时间范围生成一份简洁的阅读报告。\n\n"
        f"报告类型: {report_type}\n"
        f"时间范围: {label}\n\n"
        f"统计摘要(JSON):\n{summary}\n\n"
        f"最近阅读事件样本(JSON):\n{sample_compact}\n\n"
        "输出要求:\n"
        "- Telegram 可读的 Markdown（尽量少用复杂 Markdown）。\n"
        "- 至少包含: 概览、Top 标签、值得注意的标题、阅读节律（如能看出来）、一个温和的建议。\n"
    )
    text = llm.chat(
        model=str(payload.get("model") or settings.llm_model),
        messages=[ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
        temperature=0.5,
        max_tokens=int(payload.get("max_tokens") or 1800),
    )

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

    return {
        "intent": "REPORT",
        "narrative": str(text or "").strip(),
        "results": results,
    }
