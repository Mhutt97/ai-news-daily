"""Gemini AI summarizer and UK Finance-prioritised digest generator."""

from __future__ import annotations

from datetime import datetime
import html
import json
from pathlib import Path
import re
import urllib.request

from src.config import DIGESTS_DIR, Settings
from src.dashboard import analyze_uk_finance_benefit
from src.sources import NewsItem


SYSTEM_PROMPT = """You are an expert AI industry editor preparing a high-signal Daily AI Briefing tailored for a UK reader who wants both UK Finance Team AI news and global AI breakthroughs.
Given a list of today's raw AI articles, blog posts, research papers, and community discussions, produce a concise, well-structured Markdown digest with these exact sections in order:

1. ## 🇬🇧💷 UK Finance & CFO Teams AI Spotlight
   - Highlight the most relevant AI developments, tools, case studies, and regulatory updates (FCA, ICAEW, ACCA, UK banking/fintech, accounting, FP&A, audit, CFO workflows) for finance teams in the UK.
   - For each item: **[Title](URL)** (*Source*) — Concise 1-sentence summary + **UK Finance Benefit:** 1-sentence practical takeaway for a UK finance team.

2. ## 🔥 Top 5 Global AI Must-Read Stories
   - Pick the 5 highest-impact announcements or breakthroughs across all sources.
   - For each: **[Title](URL)** (*Source*) — 1–2 sentence explanation of what happened and how it benefits or impacts finance/enterprise teams.

3. ## 🏢 AI Labs & Industry News
   - Summarize notable updates from OpenAI, Google DeepMind, Hugging Face, TechCrunch, The Verge, Ars Technica, and MIT Tech Review.

4. ## 📄 Trending Research Papers
   - Highlight the top papers from Hugging Face Daily Papers and ArXiv (cs.AI / cs.LG) with plain-English takeaways.

5. ## 💬 Community Pulse (Hacker News & Reddit)
   - Summarize the top discussions from Hacker News, r/MachineLearning, and r/LocalLLaMA.

Keep every link intact using `[Title](URL)` markdown syntax. Be concise, factual, and avoid hype."""


def summarize_with_gemini(items: list[NewsItem], settings: Settings) -> str | None:
    """Use the Gemini REST API to generate a curated Markdown digest."""
    if not settings.gemini_api_key or not items:
        return None

    serialized = "\n".join(
        f"- [{item.category} | {item.source}] {item.title} ({item.url}) :: {item.summary}"
        for item in items[:60]
    )
    today_str = datetime.now().strftime("%B %d, %Y")
    prompt = f"{SYSTEM_PROMPT}\n\nDate: {today_str}\n\nRaw Feed Items:\n{serialized}"

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3},
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        candidates = body.get("candidates", [])
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts).strip()
            if text:
                cta = (
                    f"📊 **[Open Interactive UK Finance & AI Dashboard →]({settings.dashboard_url})**\n\n"
                    if settings.dashboard_url
                    else ""
                )
                return f"# 🤖 Daily AI News Briefing — {today_str}\n\n{cta}{text}"
    except Exception as exc:
        print(f"[warn] Gemini API summarization failed, using structured digest: {exc}")
    return None


def build_fallback_markdown(items: list[NewsItem], settings: Settings | None = None) -> str:
    """Build a structured Markdown digest prioritised for UK Finance Teams."""
    today_str = datetime.now().strftime("%B %d, %Y")
    dashboard_url = settings.dashboard_url if settings else "https://mhutt97.github.io/ai-news-daily/"

    lines: list[str] = [
        f"# 🤖 Daily AI News Briefing — {today_str}",
        "",
        f"📊 **[Open Interactive UK Finance & AI Dashboard →]({dashboard_url})**",
        "",
        f"*Curated across {len(items)} latest items, prioritised for UK Finance Teams alongside global AI breakthroughs.*",
        "",
    ]

    categories = [
        ("🇬🇧💷 UK Finance & CFO Teams AI Spotlight", "UK Finance & CFO AI"),
        ("🏢 AI Labs & Official Blogs", "AI Labs & Blogs"),
        ("📰 Tech & AI News Sites", "Tech & AI News"),
        ("📄 Research Papers (HF Daily Papers & ArXiv)", "Research Papers"),
        ("💬 Community Pulse (Hacker News & Reddit)", "Hacker News & Reddit"),
    ]

    for heading, cat_key in categories:
        cat_items = [i for i in items if i.category == cat_key]
        if not cat_items:
            continue
        # Sort within each category by UK Finance priority score descending
        scored_items = [
            (analyze_uk_finance_benefit(it), it) for it in cat_items
        ]
        scored_items.sort(key=lambda pair: pair[0][0], reverse=True)

        lines.append(f"## {heading}")
        lines.append("")
        for (score, _tier, func_tag, clean_summary, benefit), item in scored_items[:8]:
            summary_snippet = f" — {clean_summary}" if clean_summary else ""
            lines.append(
                f"- **[{item.title}]({item.url})** (*{item.source}* · {func_tag} · Priority `{score}/100`){summary_snippet}  \n"
                f"  *🇬🇧 UK Finance Benefit:* {benefit}"
            )
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def markdown_to_html(md_text: str, dashboard_url: str = "https://mhutt97.github.io/ai-news-daily/") -> str:
    """Convert the Markdown digest into a clean, responsive HTML email with a prominent Dashboard button."""
    html_lines: list[str] = []
    in_list = False

    def format_inline(text: str) -> str:
        escaped = html.escape(text)
        escaped = re.sub(
            r"\[([^\]]+)\]\((https?://[^\)]+)\)",
            r'<a href="\2" style="color:#2563eb;text-decoration:none;font-weight:600;">\1</a>',
            escaped,
        )
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
        escaped = re.sub(
            r"`([^`]+)`",
            r'<code style="background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:12px;">\1</code>',
            escaped,
        )
        return escaped

    for raw_line in md_text.splitlines():
        line = raw_line.strip()
        if not line:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue
        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(
                f'<h1 style="font-size:22px;color:#0f172a;border-bottom:2px solid #e2e8f0;padding-bottom:10px;margin-top:0;">'
                f"{format_inline(line[2:])}</h1>"
            )
        elif line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(
                f'<h2 style="font-size:17px;color:#1e293b;margin-top:24px;margin-bottom:10px;padding-bottom:4px;border-bottom:1px solid #f1f5f9;">'
                f"{format_inline(line[3:])}</h2>"
            )
        elif line.startswith("- ") or line.startswith("* "):
            if not in_list:
                html_lines.append('<ul style="padding-left:20px;line-height:1.6;color:#334155;">')
                in_list = True
            html_lines.append(f'<li style="margin-bottom:12px;">{format_inline(line[2:])}')
        elif in_list and line.startswith("*🇬🇧"):
            html_lines.append(
                f'<div style="margin-top:4px;padding:6px 10px;background:#fef3c7;border-left:3px solid #f59e0b;border-radius:4px;font-size:13px;color:#92400e;">'
                f"{format_inline(line)}</div></li>"
            )
        else:
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f'<p style="color:#475569;line-height:1.6;">{format_inline(line)}</p>')

    if in_list:
        html_lines.append("</ul>")

    body_content = "\n".join(html_lines)
    cta_banner = f"""
    <div style="background:linear-gradient(135deg,#0f172a,#1e3a8a);border-radius:10px;padding:18px 22px;margin-bottom:22px;text-align:center;">
      <div style="color:#fbbf24;font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:6px;">
        🇬🇧💷 Interactive UK Finance & AI Briefing
      </div>
      <a href="{html.escape(dashboard_url)}" style="display:inline-block;background:#3b82f6;color:#ffffff;font-weight:700;font-size:14px;padding:10px 20px;border-radius:8px;text-decoration:none;">
        📊 Open Interactive Dashboard →
      </a>
    </div>
    """
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Daily AI News Briefing</title></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:740px;margin:0 auto;padding:24px;background:#f8fafc;">
  <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:28px;box-shadow:0 1px 3px rgba(0,0,0,0.04);">
    {cta_banner}
    {body_content}
  </div>
</body>
</html>"""


def generate_and_save_digest(
    items: list[NewsItem], settings: Settings
) -> tuple[str, str, Path, Path]:
    """Generate Markdown + HTML digests and save them to digests/YYYY-MM-DD.{md,html}."""
    DIGESTS_DIR.mkdir(parents=True, exist_ok=True)
    date_slug = datetime.now().strftime("%Y-%m-%d")

    md_digest = summarize_with_gemini(items, settings)
    if not md_digest:
        md_digest = build_fallback_markdown(items, settings)

    html_digest = markdown_to_html(md_digest, settings.dashboard_url)

    md_path = DIGESTS_DIR / f"{date_slug}.md"
    html_path = DIGESTS_DIR / f"{date_slug}.html"
    md_path.write_text(md_digest, encoding="utf-8")
    html_path.write_text(html_digest, encoding="utf-8")

    return md_digest, html_digest, md_path, html_path
