"""Multi-source AI news fetcher (RSS/Atom, ArXiv API, Hugging Face Papers, Hacker News, Reddit)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AINewsDailyBot/1.0 (+https://github.com/ai-news-daily)"
)


@dataclass
class NewsItem:
    """Represents a single news article, paper, or community discussion."""

    title: str
    url: str
    source: str
    category: str
    published_at: str
    summary: str = ""
    score: int | None = None

    def to_dict(self) -> dict:
        return asdict(self)


RSS_FEEDS: list[dict[str, str]] = [
    # Category 0: UK Finance & CFO AI News (Top Priority)
    {
        "name": "UK CFO & Finance Teams AI",
        "category": "UK Finance & CFO AI",
        "url": "https://news.google.com/rss/search?q=(%22AI%22+OR+%22artificial+intelligence%22)+AND+(%22CFO%22+OR+%22finance+team%22+OR+%22finance+leaders%22+OR+%22accounting%22+OR+%22FP%26A%22+OR+%22internal+audit%22)+UK+-SEO+when:7d&hl=en-GB&gl=GB&ceid=GB:en",
    },
    {
        "name": "UK Financial Services & Big Four AI",
        "category": "UK Finance & CFO AI",
        "url": "https://news.google.com/rss/search?q=(%22AI%22+OR+%22generative+AI%22)+AND+(%22UK+finance%22+OR+%22FCA%22+OR+%22ICAEW%22+OR+%22ACCA%22+OR+%22Deloitte%22+OR+%22EY%22+OR+%22PwC%22+OR+%22KPMG%22)+UK+-SEO+when:7d&hl=en-GB&gl=GB&ceid=GB:en",
    },
    # Category 1: AI Labs & Official Blogs
    {
        "name": "OpenAI News",
        "category": "AI Labs & Blogs",
        "url": "https://openai.com/news/rss.xml",
    },
    {
        "name": "Google AI & DeepMind Blog",
        "category": "AI Labs & Blogs",
        "url": "https://blog.google/technology/ai/rss/",
    },
    {
        "name": "Hugging Face Blog",
        "category": "AI Labs & Blogs",
        "url": "https://huggingface.co/blog/feed.xml",
    },
    # Category 2: Tech & AI News Sites
    {
        "name": "TechCrunch AI",
        "category": "Tech & AI News",
        "url": "https://techcrunch.com/category/artificial-intelligence/feed/",
    },
    {
        "name": "The Verge AI",
        "category": "Tech & AI News",
        "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    },
    {
        "name": "Ars Technica AI",
        "category": "Tech & AI News",
        "url": "https://arstechnica.com/ai/feed/",
    },
    {
        "name": "MIT Technology Review AI",
        "category": "Tech & AI News",
        "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    },
    # Category 4 (part): Reddit AI Communities
    {
        "name": "r/MachineLearning",
        "category": "Hacker News & Reddit",
        "url": "https://www.reddit.com/r/MachineLearning/top/.rss?t=day",
    },
    {
        "name": "r/LocalLLaMA",
        "category": "Hacker News & Reddit",
        "url": "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=day",
    },
]


def _clean_html(raw_text: str, max_len: int = 280) -> str:
    """Strip HTML tags, decode entities, and truncate cleanly."""
    if not raw_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", raw_text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        return text[: max_len - 1].rsplit(" ", 1)[0] + "…"
    return text


def _parse_datetime(raw_date: str) -> datetime | None:
    """Parse RFC-2822 or ISO-8601 date strings into UTC datetime."""
    if not raw_date:
        return None
    raw_date = raw_date.strip()
    try:
        dt = parsedate_to_datetime(raw_date)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        iso_str = raw_date.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _http_get(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/rss+xml, application/xml, application/json, text/xml, */*",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_rss_feed(
    feed_info: dict[str, str], cutoff: datetime, max_items: int = 5
) -> list[NewsItem]:
    """Fetch and parse a standard RSS 2.0 or Atom feed."""
    raw = _http_get(feed_info["url"])
    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}

    items: list[NewsItem] = []
    # Check RSS 2.0 <item> elements
    rss_items = root.findall(".//item")
    if rss_items:
        for elem in rss_items:
            raw_title = _clean_html(elem.findtext("title") or "", max_len=220)
            link = (elem.findtext("link") or "").strip()
            desc = _clean_html(elem.findtext("description") or "")
            source_tag = _clean_html(elem.findtext("source") or "", max_len=60)

            title = raw_title
            publisher = source_tag or feed_info["name"]
            if " - " in raw_title and (source_tag or "news.google.com" in feed_info["url"]):
                 main_t, _, tail_pub = raw_title.rpartition(" - ")
                 if main_t and tail_pub and len(tail_pub) < 45:
                     title = main_t.strip()
                     publisher = source_tag or tail_pub.strip()

            # If description just repeats the title (common in Google News RSS), clear it
            if desc and title and desc.lower().startswith(title[:35].lower()):
                desc = ""

            pub_raw = (
                elem.findtext("pubDate")
                or elem.findtext("{http://purl.org/dc/elements/1.1/}date")
                or ""
            )
            dt = _parse_datetime(pub_raw)
            if dt and dt < cutoff and len(items) >= 2:
                continue
            if title and link:
                items.append(
                    NewsItem(
                        title=title,
                        url=link,
                        source=publisher,
                        category=feed_info["category"],
                        published_at=dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "Recent",
                        summary=desc,
                    )
                )
            if len(items) >= max_items:
                break
        return items

    # Check Atom <entry> elements
    atom_entries = root.findall(".//atom:entry", ns) or root.findall(".//entry")
    for entry in atom_entries:
        title_el = entry.find("atom:title", ns)
        if title_el is None:
            title_el = entry.find("title")
        title = _clean_html(title_el.text if title_el is not None and title_el.text else "", 200)

        link = ""
        for link_el in entry.findall("atom:link", ns) + entry.findall("link"):
            href = link_el.attrib.get("href", "").strip()
            rel = link_el.attrib.get("rel", "alternate")
            if href and rel in ("alternate", ""):
                link = href
                break
            if href and not link:
                link = href

        summary_el = (
            entry.find("atom:summary", ns)
            or entry.find("atom:content", ns)
            or entry.find("summary")
            or entry.find("content")
        )
        desc = _clean_html(summary_el.text if summary_el is not None and summary_el.text else "")

        pub_el = (
            entry.find("atom:published", ns)
            or entry.find("atom:updated", ns)
            or entry.find("published")
            or entry.find("updated")
        )
        pub_raw = pub_el.text if pub_el is not None and pub_el.text else ""
        dt = _parse_datetime(pub_raw)
        if dt and dt < cutoff and len(items) >= 2:
            continue

        if title and link:
            items.append(
                NewsItem(
                    title=title,
                    url=link,
                    source=feed_info["name"],
                    category=feed_info["category"],
                    published_at=dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "Recent",
                    summary=desc,
                )
            )
        if len(items) >= max_items:
            break

    return items


def fetch_hacker_news(cutoff: datetime, max_items: int = 6) -> list[NewsItem]:
    """Fetch top AI stories from Hacker News Algolia API over the lookback window."""
    cutoff_ts = int(cutoff.timestamp())
    query = urllib.parse.quote("AI OR LLM OR GPT OR Claude OR Gemini OR DeepMind OR OpenAI")
    url = (
        f"https://hn.algolia.com/api/v1/search?query={query}"
        f"&tags=story&numericFilters=created_at_i>{cutoff_ts},points>20&hitsPerPage={max_items}"
    )
    raw = _http_get(url)
    data = json.loads(raw.decode("utf-8"))
    items: list[NewsItem] = []
    for hit in data.get("hits", [])[:max_items]:
        title = hit.get("title") or ""
        story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        points = hit.get("points", 0)
        comments = hit.get("num_comments", 0)
        created_at = hit.get("created_at", "")
        dt = _parse_datetime(created_at)
        items.append(
            NewsItem(
                title=title,
                url=story_url,
                source="Hacker News",
                category="Hacker News & Reddit",
                published_at=dt.strftime("%Y-%m-%d %H:%M UTC") if dt else "Recent",
                summary=f"{points} points · {comments} comments on HN (https://news.ycombinator.com/item?id={hit.get('objectID')})",
                score=points,
            )
        )
    return items


def fetch_huggingface_papers(max_items: int = 5) -> list[NewsItem]:
    """Fetch trending daily AI papers from Hugging Face Daily Papers API."""
    url = "https://huggingface.co/api/daily_papers?limit=10"
    raw = _http_get(url)
    data = json.loads(raw.decode("utf-8"))
    items: list[NewsItem] = []
    for entry in data[:max_items]:
        paper = entry.get("paper", {})
        paper_id = paper.get("id", "")
        title = _clean_html(entry.get("title") or paper.get("title") or "", 220)
        summary = _clean_html(entry.get("summary") or paper.get("summary") or "", 280)
        upvotes = paper.get("upvotes", 0)
        pub_at = paper.get("publishedAt") or entry.get("publishedAt") or ""
        dt = _parse_datetime(pub_at)
        if title and paper_id:
            items.append(
                NewsItem(
                    title=title,
                    url=f"https://huggingface.co/papers/{paper_id}",
                    source="HF Daily Papers",
                    category="Research Papers",
                    published_at=dt.strftime("%Y-%m-%d") if dt else "Recent",
                    summary=f"[{upvotes} upvotes] {summary}",
                    score=upvotes,
                )
            )
    return items


def fetch_arxiv_papers(max_items: int = 5) -> list[NewsItem]:
    """Fetch latest cs.AI and cs.LG papers from the ArXiv API."""
    url = (
        "http://export.arxiv.org/api/query?"
        "search_query=cat:cs.AI+OR+cat:cs.LG&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_items}"
    )
    raw = _http_get(url)
    root = ET.fromstring(raw)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items: list[NewsItem] = []
    for entry in root.findall("atom:entry", ns)[:max_items]:
        title = _clean_html(entry.findtext("atom:title", default="", namespaces=ns), 220)
        link = entry.findtext("atom:id", default="", namespaces=ns).strip()
        summary = _clean_html(entry.findtext("atom:summary", default="", namespaces=ns), 260)
        pub_raw = entry.findtext("atom:published", default="", namespaces=ns)
        dt = _parse_datetime(pub_raw)
        if title and link:
            items.append(
                NewsItem(
                    title=title,
                    url=link,
                    source="ArXiv (cs.AI / cs.LG)",
                    category="Research Papers",
                    published_at=dt.strftime("%Y-%m-%d") if dt else "Recent",
                    summary=summary,
                )
            )
    return items


def fetch_all_news(lookback_hours: int = 24, max_items_per_source: int = 5) -> list[NewsItem]:
    """Fetch AI news across all categories in parallel."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    all_items: list[NewsItem] = []

    with ThreadPoolExecutor(max_workers=8) as pool:
        future_map = {}
        for feed in RSS_FEEDS:
            future = pool.submit(fetch_rss_feed, feed, cutoff, max_items_per_source)
            future_map[future] = feed["name"]

        future_map[pool.submit(fetch_hacker_news, cutoff, max_items_per_source)] = "Hacker News"
        future_map[pool.submit(fetch_huggingface_papers, max_items_per_source)] = "HF Daily Papers"
        future_map[pool.submit(fetch_arxiv_papers, max_items_per_source)] = "ArXiv"

        for future in as_completed(future_map):
            source_name = future_map[future]
            try:
                result = future.result()
                all_items.extend(result)
            except Exception as exc:
                print(f"[warn] Failed to fetch {source_name}: {exc}")

    # Deduplicate by normalized title
    seen_titles: set[str] = set()
    unique_items: list[NewsItem] = []
    for item in all_items:
        norm = re.sub(r"\W+", "", item.title.lower())
        if norm and norm not in seen_titles:
            seen_titles.add(norm)
            unique_items.append(item)

    return unique_items
