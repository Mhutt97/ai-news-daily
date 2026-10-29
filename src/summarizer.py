"""Gemini AI summarizer, UK Finance-prioritised digest generator, and editorial HTML email renderer."""

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

GB_FLAG = "\U0001F1EC\U0001F1E7"

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


def _strip_gb_flag(text: str) -> str:
    """Remove raw GB flag emojis so Windows email clients never render two-letter 'GB' glyphs."""
    return text.replace(GB_FLAG, "").strip()


def _format_email_inline(text: str) -> str:
    """Format inline Markdown (links, bold, italic, code) with editorial email styling."""
    cleaned = _strip_gb_flag(text)
    escaped = html.escape(cleaned)
    escaped = re.sub(
        r"\[([^\]]+)\]\((https?://[^\)]+)\)",
        r'<a href="\2" target="_blank" style="color:#8b4cd4;text-decoration:underline;font-weight:700;">\1</a>',
        escaped,
    )
    escaped = re.sub(
        r"\*\*([^*]+)\*\*",
        r'<strong style="color:#171717;font-weight:700;">\1</strong>',
        escaped,
    )
    escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
    escaped = re.sub(
        r"`([^`]+)`",
        r'<code style="background-color:#f5f5f5;color:#171717;padding:2px 6px;border-radius:5px;font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;">\1</code>',
        escaped,
    )
    return escaped


def _section_theme(section_title: str) -> tuple[str, str]:
    """Return (eyebrow_label, accent_hex) for a digest section heading."""
    low = section_title.lower()
    if "uk finance" in low or "cfo" in low:
        return ("UK CFO · AUDIT · FCA SPOTLIGHT", "#8b4cd4")
    if "must-read" in low or "top 5" in low:
        return ("EXECUTIVE PRIORITY STORIES", "#8b4cd4")
    if "labs" in low or "official" in low:
        return ("FRONTIER AI LABS & RELEASES", "#009767")
    if "news" in low or "industry" in low:
        return ("ENTERPRISE & INDUSTRY COVERAGE", "#009767")
    if "research" in low or "paper" in low:
        return ("TECHNICAL & INFERENCE RESEARCH", "#6254ff")
    if "community" in low or "hacker news" in low or "reddit" in low:
        return ("ENGINEERING & COMMUNITY PULSE", "#6254ff")
    return ("INTELLIGENCE BRIEFING", "#8b4cd4")


def _tier_colors(score: int | None, default_accent: str) -> tuple[str, str, str, str]:
    """Return (accent_hex, badge_bg, badge_text, badge_border) for a story card."""
    if score is not None:
        if score >= 85:
            return ("#8b4cd4", "#f3ecfb", "#7133b8", "#dec9f6")
        if score >= 70:
            return ("#009767", "#e6f6f0", "#007a53", "#bce8d8")
        return ("#6254ff", "#eeedff", "#4f42e6", "#d2ceff")

    if default_accent == "#009767":
        return ("#009767", "#e6f6f0", "#007a53", "#bce8d8")
    if default_accent == "#6254ff":
        return ("#6254ff", "#eeedff", "#4f42e6", "#d2ceff")
    return ("#8b4cd4", "#f3ecfb", "#7133b8", "#dec9f6")


def _parse_story_bullet(
    bullet_line: str, benefit_line: str | None
) -> dict[str, object]:
    """Parse a Markdown story bullet (from fallback or Gemini output) into structured card fields."""
    rest = bullet_line.strip()
    if rest.startswith(("- ", "* ")):
        rest = rest[2:].strip()

    title = ""
    url = ""
    link_match = re.match(r"^\*\*\[([^\]]+)\]\((https?://[^\)]+)\)\*\*(.*)$", rest)
    if not link_match:
        link_match = re.match(r"^\[([^\]]+)\]\((https?://[^\)]+)\)(.*)$", rest)

    if link_match:
        title = _strip_gb_flag(link_match.group(1))
        url = link_match.group(2).strip()
        tail = link_match.group(3).strip()
    else:
        tail = rest

    source = ""
    func_tag = ""
    score: int | None = None

    # Pattern A: (*Source* · Tag · Priority `99/100`)
    meta_full = re.match(
        r"^\(\*([^*]+)\*\s*·\s*([^·]+?)\s*·\s*Priority\s*`(\d+)/100`\)(.*)$",
        tail,
    )
    if meta_full:
        source = _strip_gb_flag(meta_full.group(1))
        func_tag = _strip_gb_flag(meta_full.group(2))
        score = int(meta_full.group(3))
        tail = meta_full.group(4).strip()
    else:
        # Pattern B: (*Source*)
        meta_simple = re.match(r"^\(\*([^*]+)\*\)(.*)$", tail)
        if meta_simple:
            source = _strip_gb_flag(meta_simple.group(1))
            tail = meta_simple.group(2).strip()

    # Extract inline UK Finance Benefit if Gemini wrote it on the same line
    extracted_benefit = ""
    if benefit_line:
        b_clean = _strip_gb_flag(benefit_line)
        b_clean = re.sub(
            r"^\*{0,2}\s*UK Finance Benefit:\s*\*{0,2}\s*",
            "",
            b_clean,
            flags=re.I,
        ).strip()
        extracted_benefit = b_clean

    inline_ben = re.split(
        r"\s*(?:\+\s*)?\*\*UK Finance Benefit:\*\*\s*|\s*\*UK Finance Benefit:\*\s*",
        tail,
        maxsplit=1,
        flags=re.I,
    )
    if len(inline_ben) == 2:
        tail = inline_ben[0].strip()
        if not extracted_benefit:
            extracted_benefit = _strip_gb_flag(inline_ben[1].strip())

    # Clean leading dash separator from summary
    tail = re.sub(r"^(?:—|–|-|:)\s*", "", tail).strip()

    return {
        "title": title,
        "url": url,
        "source": source,
        "func_tag": func_tag,
        "score": score,
        "summary": tail,
        "benefit": extracted_benefit,
    }


def _render_story_card_html(
    story: dict[str, object],
    rank_num: int,
    section_eyebrow: str,
    section_accent: str,
) -> str:
    """Render a single story card using email-safe presentation tables and the dashboard's editorial tokens."""
    title = str(story.get("title") or "")
    url = str(story.get("url") or "")
    source = str(story.get("source") or "")
    func_tag = str(story.get("func_tag") or "")
    score = story.get("score")
    score_int = int(score) if isinstance(score, int) else None
    summary = str(story.get("summary") or "")
    benefit = str(story.get("benefit") or "")

    accent, badge_bg, badge_fg, badge_border = _tier_colors(score_int, section_accent)
    eyebrow_text = html.escape(func_tag) if func_tag else html.escape(section_eyebrow)
    num_str = f"{rank_num:02d}"

    score_badge_html = ""
    if score_int is not None:
        urgent_pill = ""
        if score_int >= 94:
            urgent_pill = (
                '<span style="display:inline-block;background-color:#fdecee;color:#c80012;'
                'border:1px solid #f9c6cb;font-size:10px;font-weight:800;padding:2px 8px;'
                'border-radius:999px;text-transform:uppercase;letter-spacing:0.06em;margin-right:6px;">'
                "Action Required</span>"
            )
        score_badge_html = (
            f"{urgent_pill}"
            f'<span style="display:inline-block;background-color:{badge_bg};color:{badge_fg};'
            f'border:1px solid {badge_border};font-size:11px;font-weight:800;padding:2px 9px;'
            f'border-radius:999px;letter-spacing:0.01em;">{score_int}/100</span>'
        )

    if title and url:
        headline_html = (
            f'<a href="{html.escape(url)}" target="_blank" '
            f'style="color:#171717;font-size:17px;font-weight:800;line-height:1.36;'
            f'letter-spacing:-0.02em;text-decoration:none;">{html.escape(title)}</a>'
        )
    elif title:
        headline_html = (
            f'<span style="color:#171717;font-size:17px;font-weight:800;line-height:1.36;">'
            f"{html.escape(title)}</span>"
        )
    else:
        headline_html = (
            f'<span style="color:#262626;font-size:14.5px;line-height:1.55;">'
            f"{_format_email_inline(summary)}</span>"
        )
        summary = ""

    summary_html = ""
    if summary:
        summary_html = (
            f'<p style="margin:8px 0 0 0;color:#525252;font-size:13.8px;line-height:1.6;">'
            f"{_format_email_inline(summary)}</p>"
        )

    benefit_html = ""
    if benefit:
        benefit_html = (
            f'<div style="background:#fafafa;border:1px solid #efefef;border-left:3px solid {accent};border-radius:12px;margin-top:12px;padding:10px 14px;">'
            f'<div style="font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:0.1em;color:{accent};margin-bottom:4px;">'
            f'<span style="display:inline-block;background:#171717;color:#fff;font-size:9px;font-weight:800;padding:1px 5px;border-radius:4px;margin-right:6px;letter-spacing:0.06em;">UK</span>'
            f"Why It Matters &middot; Finance</div>"
            f'<div style="font-size:13px;line-height:1.55;color:#262626;">{_format_email_inline(benefit)}</div>'
            f"</div>"
        )

    footer_html = ""
    if source or url:
        left_pub = html.escape(source) if source else "Curated Source"
        right_link = (
            f'<a href="{html.escape(url)}" target="_blank" '
            f'style="color:#171717;font-size:12.5px;font-weight:800;text-decoration:none;">'
            f"Read story &#8599;</a>"
            if url
            else ""
        )
        footer_html = (
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
            f'style="border-top:1px solid #efefef;margin-top:12px;padding-top:10px;">'
            f'<tr><td align="left" style="font-size:12px;font-weight:600;color:#737373;">{left_pub}</td>'
            f'<td align="right">{right_link}</td></tr></table>'
        )

    return (
        f'<div style="background:#ffffff;border:1px solid #e5e5e5;border-radius:20px;margin-bottom:14px;padding:18px 20px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:8px;">'
        f'<tr><td align="left" style="font-size:11px;font-weight:800;text-transform:uppercase;letter-spacing:0.08em;color:{accent};">'
        f'<span style="display:inline-block;background:#f5f5f5;color:#525252;font-family:monospace;font-size:10.5px;font-weight:800;padding:2px 7px;border-radius:999px;margin-right:6px;">{num_str}</span>{eyebrow_text}</td>'
        f'<td align="right" style="white-space:nowrap;">{score_badge_html}</td></tr></table>'
        f"<div>{headline_html}</div>"
        f"{summary_html}{benefit_html}{footer_html}"
        f"</div>"
    )


def markdown_to_html(
    md_text: str, dashboard_url: str = "https://mhutt97.github.io/ai-news-daily/"
) -> str:
    """Render the Markdown digest into an executive HTML email sharing the dashboard's editorial design package."""
    raw_lines = md_text.splitlines()
    n = len(raw_lines)

    date_display = datetime.now().strftime("%B %d, %Y")
    curated_total_hint: int | None = None

    sections_html: list[str] = []
    current_sec_eyebrow = "EXECUTIVE BRIEFING"
    current_sec_accent = "#8b4cd4"
    total_stories = 0
    uk_spotlight_count = 0
    high_priority_count = 0
    section_count = 0
    in_uk_section = False

    i = 0
    while i < n:
        line = raw_lines[i].strip()
        if not line:
            i += 1
            continue

        # Top-level Markdown title (# ...)
        if line.startswith("# "):
            heading_text = _strip_gb_flag(line[2:])
            if "—" in heading_text:
                date_display = heading_text.split("—", 1)[1].strip()
            i += 1
            continue

        # Skip standalone Markdown dashboard CTA line (rendered prominently in Hero bar)
        if "Open Interactive UK Finance & AI Dashboard" in line:
            i += 1
            continue

        # Extract total items hint from intro italic line if present
        intro_match = re.search(r"Curated across\s+(\d+)\s+latest items", line, re.I)
        if intro_match:
            curated_total_hint = int(intro_match.group(1))
            i += 1
            continue

        # Section Heading (## ...)
        if line.startswith("## "):
            raw_sec = _strip_gb_flag(line[3:]).strip()
            current_sec_eyebrow, current_sec_accent = _section_theme(raw_sec)
            in_uk_section = "uk finance" in raw_sec.lower() or "cfo" in raw_sec.lower()
            top_margin = "8px" if section_count == 0 else "30px"
            section_count += 1
            sections_html.append(f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="margin-top:{top_margin};margin-bottom:16px;border-bottom:1px solid #e5e5e5;">
              <tr>
                <td style="padding-bottom:11px;">
                  <div style="font-size:10.5px;font-weight:800;text-transform:uppercase;letter-spacing:0.14em;color:{current_sec_accent};margin-bottom:4px;">
                    <span style="display:inline-block;width:7px;height:7px;border-radius:999px;background-color:{current_sec_accent};margin-right:6px;vertical-align:middle;"></span><span style="vertical-align:middle;">{html.escape(current_sec_eyebrow)}</span>
                  </div>
                  <h2 style="margin:0;color:#171717;font-size:20px;font-weight:800;letter-spacing:-0.025em;line-height:1.25;">
                    {html.escape(raw_sec)}
                  </h2>
                </td>
              </tr>
            </table>""")
            i += 1
            continue

        # Bullet item (- ... or * ...)
        if line.startswith(("- ", "* ")):
            benefit_line: str | None = None
            if i + 1 < n:
                next_stripped = raw_lines[i + 1].strip()
                if "UK Finance Benefit:" in next_stripped and not next_stripped.startswith(("- ", "* [", "**[")):
                    benefit_line = next_stripped
                    i += 1

            story = _parse_story_bullet(line, benefit_line)
            total_stories += 1
            score_val = story.get("score")
            if in_uk_section:
                uk_spotlight_count += 1
            if isinstance(score_val, int) and score_val >= 85:
                high_priority_count += 1
            elif in_uk_section and score_val is None:
                high_priority_count += 1

            sections_html.append(
                _render_story_card_html(
                    story,
                    total_stories,
                    current_sec_eyebrow,
                    current_sec_accent,
                )
            )
            i += 1
            continue

        # Any standalone paragraph
        sections_html.append(
            f'<p style="margin:0 0 14px 0;color:#525252;font-size:14px;line-height:1.6;">'
            f"{_format_email_inline(line)}</p>"
        )
        i += 1

    display_total = curated_total_hint or total_stories
    display_high = high_priority_count or uk_spotlight_count
    safe_dash_url = html.escape(dashboard_url)
    safe_date = html.escape(date_display)
    body_cards_html = "\n".join(sections_html)

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="color-scheme" content="light" />
  <meta name="supported-color-schemes" content="light" />
  <title>UK Finance &amp; AI Daily Briefing &mdash; {safe_date}</title>
  <link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap" rel="stylesheet" />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    body, table, td, p, a, h1, h2 {{
      font-family: 'Satoshi', 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    }}
    @supports (-webkit-background-clip: text) {{
      .hero-tri-gradient {{
        background: linear-gradient(90deg, #cd408f 0%, #8b4cd4 50%, #6254ff 100%);
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
      }}
    }}
    @media only screen and (max-width: 620px) {{
      .outer-pad {{ padding: 8px !important; }}
      .hero-pad {{ padding: 26px 16px 28px !important; }}
      .hero-h1 {{ font-size: 30px !important; }}
      .sheet-pad {{ padding: 22px 14px !important; border-radius: 20px !important; }}
      .pill-cta-desc {{ display: none !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#171717;color:#171717;-webkit-font-smoothing:antialiased;">
  <!-- Inbox Preview Preheader -->
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;mso-hide:all;">
    UK Finance &amp; AI intelligence in 5 minutes &mdash; {display_total} curated stories ranked for UK CFOs, Audit, FP&amp;A &amp; FCA compliance ({safe_date}).
  </div>

  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#171717" style="background-color:#171717;">
    <tr>
      <td align="center" class="outer-pad" style="padding:12px 12px 28px 12px;">

        <!-- 1. OBSIDIAN MASTHEAD -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:680px;border-bottom:1px solid #2a2a2a;">
          <tr>
            <td align="left" valign="middle" style="padding:14px 10px;">
              <a href="{safe_dash_url}" target="_blank" style="text-decoration:none;color:#ffffff;">
                <span style="display:inline-block;width:32px;height:32px;line-height:32px;text-align:center;border-radius:8px;background-color:#ffffff;color:#171717;font-size:13.5px;font-weight:900;letter-spacing:-0.04em;vertical-align:middle;margin-right:9px;">AI</span><span style="font-size:17.5px;font-weight:800;letter-spacing:-0.03em;color:#ffffff;vertical-align:middle;margin-right:8px;">UK Finance &amp; AI</span><span style="display:inline-block;background-color:#262626;border:1px solid #383838;color:#e5e5e5;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;padding:3px 8px;border-radius:999px;vertical-align:middle;">Daily Briefing</span>
              </a>
            </td>
            <td align="right" valign="middle" style="padding:14px 10px;white-space:nowrap;">
              <a href="{safe_dash_url}" target="_blank" style="display:inline-block;background-color:#ffffff;color:#171717;font-size:12px;font-weight:800;padding:7px 14px;border-radius:999px;text-decoration:none;">
                Web Dashboard &#8599;
              </a>
            </td>
          </tr>
        </table>

        <!-- 2. EDITORIAL HERO STAGE -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:680px;">
          <tr>
            <td align="center" class="hero-pad" style="padding:34px 20px 36px 20px;text-align:center;">
              <!-- Live Date Eyebrow Pill -->
              <div style="margin-bottom:18px;">
                <span style="display:inline-block;background-color:#222222;border:1px solid #333333;border-radius:999px;padding:6px 14px;font-size:11.5px;font-weight:700;color:#d4d4d4;letter-spacing:0.02em;">
                  <span style="display:inline-block;width:7px;height:7px;border-radius:999px;background-color:#00c758;margin-right:7px;vertical-align:middle;"></span><span style="vertical-align:middle;">{safe_date} &middot; Morning Intelligence Edition</span>
                </span>
              </div>

              <!-- Hero Display Headline -->
              <h1 class="hero-h1" style="margin:0 0 14px 0;color:#ffffff;font-size:40px;font-weight:800;line-height:1.08;letter-spacing:-0.038em;">
                UK Finance &amp; AI news<br />
                in <span class="hero-tri-gradient" style="color:#b56bff;">5 minutes</span> a day.
              </h1>

              <p style="margin:0 auto 24px auto;max-width:500px;color:#a3a3a3;font-size:15.5px;line-height:1.55;font-weight:400;">
                Get the latest AI breakthroughs, understand why they matter for UK CFOs, Audit &amp; FCA compliance, and apply them in your work.
              </p>

              <!-- White Rounded Pill CTA Bar (mirrors Dashboard Hero Bar) -->
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:520px;background-color:#ffffff;border-radius:14px;border-collapse:separate;">
                <tr>
                  <td align="left" valign="middle" class="pill-cta-desc" style="padding:10px 14px 10px 18px;font-size:13px;font-weight:600;color:#525252;">
                    Filter by CFO / Audit / FP&amp;A Role Lens &amp; export CSV
                  </td>
                  <td align="right" valign="middle" style="padding:7px 7px 7px 10px;white-space:nowrap;">
                    <a href="{safe_dash_url}" target="_blank" style="display:inline-block;background-color:#171717;color:#ffffff;font-size:13px;font-weight:800;padding:11px 18px;border-radius:10px;text-decoration:none;letter-spacing:-0.01em;">
                      Open Interactive Dashboard &rarr;
                    </a>
                  </td>
                </tr>
              </table>

              <!-- Signal Snapshot Pills -->
              <div style="margin-top:20px;font-size:12px;color:#a3a3a3;">
                <span style="display:inline-block;background-color:#222222;border:1px solid #303030;border-radius:999px;padding:4px 11px;margin:3px;color:#e5e5e5;font-weight:700;">
                  <span style="color:#b56bff;">{display_high}</span> High UK Finance
                </span>
                <span style="display:inline-block;background-color:#222222;border:1px solid #303030;border-radius:999px;padding:4px 11px;margin:3px;color:#e5e5e5;font-weight:700;">
                  <span style="color:#00c758;">{total_stories}</span> Briefed Below
                </span>
                <span style="display:inline-block;background-color:#222222;border:1px solid #303030;border-radius:999px;padding:4px 11px;margin:3px;color:#e5e5e5;font-weight:700;">
                  {display_total} Curated Today
                </span>
              </div>
            </td>
          </tr>
        </table>

        <!-- 3. ROUNDED WHITE .sheet EDITORIAL PAPER BODY -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" bgcolor="#ffffff" style="max-width:680px;background-color:#ffffff;border-radius:26px;border-collapse:separate;">
          <tr>
            <td class="sheet-pad" style="padding:30px 26px 22px 26px;">
              {body_cards_html}
            </td>
          </tr>
        </table>

        <!-- 4. OBSIDIAN FOOTER -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:680px;margin-top:16px;">
          <tr>
            <td align="center" style="padding:22px 18px 10px 18px;text-align:center;">
              <div style="margin-bottom:10px;">
                <span style="display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:6px;background-color:#ffffff;color:#171717;font-size:10.5px;font-weight:900;vertical-align:middle;margin-right:7px;">AI</span><span style="font-size:14.5px;font-weight:800;color:#ffffff;vertical-align:middle;">UK Finance &amp; AI &middot; Daily Intelligence</span>
              </div>
              <p style="margin:0 0 14px 0;font-size:12.5px;line-height:1.6;color:#8a8a8a;">
                <a href="{safe_dash_url}" target="_blank" style="color:#d4d4d4;font-weight:700;text-decoration:underline;">Live Dashboard</a>
                &nbsp;&middot;&nbsp;
                <a href="{safe_dash_url}#stories" target="_blank" style="color:#d4d4d4;font-weight:700;text-decoration:underline;">All {display_total} Stories &amp; Search</a>
              </p>
              <p style="margin:0;font-size:11px;line-height:1.55;color:#666666;">
                Algorithmic executive briefing curated for UK CFO, Audit, FP&amp;A &amp; FCA compliance discussion. Does not constitute regulated FCA financial or legal advice.
              </p>
            </td>
          </tr>
        </table>

      </td>
    </tr>
  </table>
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
