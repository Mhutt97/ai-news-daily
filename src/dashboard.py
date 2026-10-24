"""Interactive UK Finance & AI News Dashboard generator and Finance Benefit prioritization engine."""

from __future__ import annotations

from datetime import datetime
import html
import json
from pathlib import Path
import re
import urllib.request

from src.config import PROJECT_ROOT, Settings
from src.sources import NewsItem

DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_DASHBOARD_URL = "https://mhutt97.github.io/ai-news-daily/"


def analyze_uk_finance_benefit(item: NewsItem) -> tuple[int, str, str, str, str]:
    """
    Evaluate a news item for UK Finance Team priority.
    Returns (priority_score_0_to_100, priority_tier, func_tag, concise_summary, uk_finance_benefit).
    """
    title_l = item.title.lower()
    text = f"{item.title} {item.summary} {item.source} {item.category}".lower()

    clean_summary = (item.summary or "").strip()
    if clean_summary and clean_summary.lower().startswith(title_l[:32]):
        clean_summary = ""

    stat_match = re.search(
        r"(\d+%|\£\d+[a-z]*|\$\d+\s*(?:billion|million|bn|m)|\d+×)",
        item.title,
        re.IGNORECASE,
    )
    stat_str = stat_match.group(1) if stat_match else ""

    score = 45
    tier = "General AI News"
    func_tag = "🌐 Industry Update"
    benefit = (
        f"General awareness from {item.source}: tracks broader AI model and market "
        f"developments that may flow into enterprise tools."
    )

    if item.category == "UK Finance & CFO AI":
        score = 90
        tier = "High UK Finance Impact"
        func_tag = "🇬🇧 UK Finance"
        benefit = (
            f"Published by {item.source}: benchmarks how UK financial services and "
            f"corporate finance teams are governing and deploying AI."
        )

    if re.search(r"\b(fca|financial conduct authority|bank of england|pra)\b", text):
        score = 99
        tier = "High UK Finance Impact"
        func_tag = "🏛️ FCA & Regulation"
        benefit = (
            f"Regulatory Guidance ({item.source}): Essential reading for UK finance and compliance "
            f"teams aligning AI governance, explainability, and risk controls with FCA expectations."
        )
    elif re.search(r"\b(cci|disclosure|consumer duty|reporting|frc|icaew|acca|hmrc)\b", text):
        score = 97
        tier = "High UK Finance Impact"
        func_tag = "📊 Reporting & Disclosure"
        benefit = (
            f"UK Reporting & Disclosure ({item.source}): Shows how finance and regulatory reporting "
            f"teams can turn UK disclosure and compliance requirements into clearer stakeholder assurance."
        )
    elif re.search(
        r"\b(soc|attestation|certification|assurance|selective auditing|dataset-use auditing)\b",
        text,
    ):
        score = 96
        tier = "High UK Finance Impact"
        func_tag = "🛡️ Audit & Assurance"
        benefit = (
            f"AI Assurance & Controls ({item.source}): Practical framework for using SOC reporting, "
            f"independent attestation, and selective auditing to verify AI outputs in financial workflows."
        )
    elif re.search(
        r"\b(internal auditor|internal auditors|external audit|kpmg|deloitte|pwc|ey|bdo)\b",
        text,
    ):
        score = max(score, 94)
        tier = "High UK Finance Impact"
        func_tag = "🛡️ Audit & Big Four"
        benefit = (
            f"Audit Practice Benchmark ({item.source}): Tracks how internal audit teams and Big Four "
            f"advisors are adopting AI for risk testing, sampling, and control validation."
        )
    elif re.search(
        r"\b(cfo|cfos|finance leader|finance leaders|finance team|finance teams|fp&a|accountant|accounting)\b",
        text,
    ):
        score = 96
        tier = "High UK Finance Impact"
        func_tag = "📈 CFO & Strategy"
        if stat_str:
            benefit = (
                f"CFO Benchmark ({stat_str} headline stat via {item.source}): Highlights the tension "
                f"between rapid AI rollout pressure and the need for controlled, accurate finance workflows."
            )
        else:
            benefit = (
                f"CFO & Finance Operations ({item.source}): Directly applicable to UK finance leaders "
                f"prioritising ROI, month-end automation, and team upskilling."
            )
    elif re.search(r"\b(banking|uk finance|fintech|payments|treasury|lending)\b", text):
        score = max(score, 93)
        tier = "High UK Finance Impact"
        func_tag = "🏦 UK Banking & Treasury"
        benefit = (
            f"UK Financial Sector Insight ({item.source}): Examines operational, cultural, and legacy-system "
            f"hurdles beyond technology when rolling out AI across UK banking and finance functions."
        )
    elif re.search(
        r"\b(no internet|live internet|containment|securing|red-team|llm-attacker|privacy|gmail|data)\b",
        text,
    ):
        score = max(score, 84)
        tier = "Finance Ops & Governance"
        func_tag = "🔒 Data Privacy & Risk"
        benefit = (
            f"Data Governance Alert ({item.source}): Important context for finance teams evaluating "
            f"model containment, cloud privacy settings, and protecting confidential financial data."
        )
    elif re.search(
        r"\b(agent|agents|voice|local|macbook|harness|storage|scaling|multi-tenancy)\b",
        text,
    ):
        score = max(score, 78)
        tier = "Finance Ops & Productivity"
        func_tag = "🤖 AI Agents & Ops"
        benefit = (
            f"Enterprise AI Infrastructure ({item.source}): Demonstrates how production AI harnesses, "
            f"local models, and messaging agents are maturing for day-to-day business workflows."
        )
    elif re.search(
        r"\b(gemini|gpt|claude|grok|frontier model|openai|deepmind|trainium)\b", text
    ):
        score = max(score, 74)
        tier = "Finance Ops & Productivity"
        func_tag = "🧠 Frontier Models"
        benefit = (
            f"Model Capability Update ({item.source}): Tracks frontier model releases, reliability, "
            f"and compute economics that underpin enterprise copilot and analytics tools."
        )
    elif item.category == "Research Papers":
        score = 58
        tier = "General AI & Research"
        func_tag = "🔬 Research Paper"
        benefit = (
            f"Early Research Signal ({item.source}): Technical paper on model efficiency, reasoning, "
            f"or evaluation benchmarks that will influence next-generation enterprise AI."
        )
    elif item.category == "Hacker News & Reddit":
        score = 52
        tier = "General AI & Research"
        func_tag = "💬 Community Pulse"
        benefit = (
            f"Practitioner Discussion ({item.source}): Highlights real-world engineering debates around "
            f"LLM memory, model steering, and AI research quality."
        )

    return score, tier, func_tag, clean_summary, benefit


def enrich_items_with_gemini(
    items: list[NewsItem], settings: Settings
) -> dict[int, dict[str, object]]:
    """Optionally use Gemini API to refine concise summaries and UK finance team benefits."""
    if not settings.gemini_api_key or not items:
        return {}

    subset = items[:30]
    prompt_lines = [
        "You are a UK CFO & Finance Director advisor. For each news item below (indexed 0..N), return a JSON array of objects with keys:",
        '`{"idx": int, "score": int (1-100 priority for a UK finance team), "func_tag": "short tag e.g. 🏛️ FCA & Regulation | 🛡️ Audit & Controls | 📈 CFO Strategy | 🔒 Data Privacy | 🤖 AI Agents | 🔬 Research", "summary": "concise 1-sentence plain-English summary", "benefit": "specific, non-repetitive 1-sentence takeaway for a UK finance team"}`.',
        "Return ONLY valid JSON.",
        "",
    ]
    for idx, it in enumerate(subset):
        prompt_lines.append(
            f"{idx}. [{it.category} | {it.source}] {it.title} :: {it.summary}"
        )

    api_url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    )
    payload = {
        "contents": [{"parts": [{"text": "\n".join(prompt_lines)}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = (
            body.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return {int(row["idx"]): row for row in parsed if "idx" in row}
    except Exception as exc:
        print(f"[info] Using built-in UK Finance prioritization engine ({exc})")
    return {}


def prepare_prioritized_cards(
    items: list[NewsItem], settings: Settings
) -> list[dict[str, object]]:
    """Enrich and sort all news items by UK Finance Team priority score descending."""
    gemini_map = enrich_items_with_gemini(items, settings)
    cards: list[dict[str, object]] = []

    for idx, item in enumerate(items):
        score, tier, func_tag, summary, benefit = analyze_uk_finance_benefit(item)
        if idx in gemini_map:
            g = gemini_map[idx]
            score = int(g.get("score", score))
            func_tag = str(g.get("func_tag") or func_tag)
            summary = str(g.get("summary") or summary)
            benefit = str(g.get("benefit") or benefit)
            if score >= 85:
                tier = "High UK Finance Impact"
            elif score >= 70:
                tier = "Finance Ops & Productivity"
            else:
                tier = "General AI & Research"

        cards.append(
            {
                "id": f"item-{idx}",
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "category": item.category,
                "published_at": item.published_at,
                "score": score,
                "tier": tier,
                "func_tag": func_tag,
                "summary": summary,
                "benefit": benefit,
            }
        )

    cards.sort(key=lambda c: int(c["score"]), reverse=True)
    return cards


def build_dashboard_html(cards: list[dict[str, object]], date_str: str) -> str:
    """Render a modern, mobile-first, animated UK Finance & AI Intelligence Dashboard."""
    high_impact_count = sum(1 for c in cards if int(c["score"]) >= 85)
    ops_count = sum(1 for c in cards if 70 <= int(c["score"]) < 85)
    general_count = sum(1 for c in cards if int(c["score"]) < 70)

    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#070b14" />
  <title>UK Finance & AI Daily Intelligence — {html.escape(date_str)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@500;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg: #070b14;
      --bg-mesh-1: rgba(59, 130, 246, 0.11);
      --bg-mesh-2: rgba(245, 158, 11, 0.08);
      --surface: rgba(17, 24, 39, 0.82);
      --surface-solid: #111827;
      --surface-elevated: #192338;
      --surface-hover: #1e293b;
      --glass-bg: rgba(15, 23, 42, 0.78);
      --border: rgba(255, 255, 255, 0.09);
      --border-subtle: rgba(255, 255, 255, 0.06);
      --text: #f8fafc;
      --text-secondary: #cbd5e1;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --accent-glow: rgba(59, 130, 246, 0.35);
      --gold-bg: rgba(245, 158, 11, 0.13);
      --gold-border: rgba(245, 158, 11, 0.42);
      --gold-text: #fbbf24;
      --emerald-bg: rgba(16, 185, 129, 0.13);
      --emerald-border: rgba(16, 185, 129, 0.38);
      --emerald-text: #34d399;
      --blue-bg: rgba(59, 130, 246, 0.13);
      --blue-border: rgba(59, 130, 246, 0.38);
      --blue-text: #60a5fa;
      --benefit-bg: rgba(9, 14, 26, 0.68);
      --hero-gradient: linear-gradient(135deg, rgba(30, 41, 59, 0.85) 0%, rgba(15, 23, 42, 0.94) 100%);
      --card-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.45);
      --spring: cubic-bezier(0.22, 1, 0.36, 1);
    }}
    [data-theme="light"] {{
      --bg: #f4f7fb;
      --bg-mesh-1: rgba(37, 99, 235, 0.07);
      --bg-mesh-2: rgba(245, 158, 11, 0.07);
      --surface: rgba(255, 255, 255, 0.92);
      --surface-solid: #ffffff;
      --surface-elevated: #f1f5f9;
      --surface-hover: #f8fafc;
      --glass-bg: rgba(255, 255, 255, 0.85);
      --border: #e2e8f0;
      --border-subtle: #edf2f7;
      --text: #0f172a;
      --text-secondary: #334155;
      --muted: #64748b;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
      --accent-glow: rgba(37, 99, 235, 0.2);
      --gold-bg: #fef3c7;
      --gold-border: #f59e0b;
      --gold-text: #b45309;
      --emerald-bg: #d1fae5;
      --emerald-border: #10b981;
      --emerald-text: #047857;
      --blue-bg: #dbeafe;
      --blue-border: #3b82f6;
      --blue-text: #1d4ed8;
      --benefit-bg: #f8fafc;
      --hero-gradient: linear-gradient(135deg, #ffffff 0%, #eff6ff 100%);
      --card-shadow: 0 10px 25px -8px rgba(15, 23, 42, 0.07);
    }}

    * {{ box-sizing: border-box; -webkit-tap-highlight-color: transparent; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      font-family: "Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background-color: var(--bg);
      background-image:
        radial-gradient(at 12% 0%, var(--bg-mesh-2) 0px, transparent 50%),
        radial-gradient(at 88% 4%, var(--bg-mesh-1) 0px, transparent 50%);
      background-attachment: fixed;
      color: var(--text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
      overflow-x: hidden;
    }}

    /* Top Scroll Progress Bar */
    #scrollProgress {{
      position: fixed;
      top: 0;
      left: 0;
      height: 3px;
      width: 0%;
      background: linear-gradient(90deg, #f59e0b 0%, #3b82f6 55%, #10b981 100%);
      z-index: 999;
      transition: width 0.08s linear;
    }}

    .container {{
      max-width: 1260px;
      margin: 0 auto;
      padding: 28px 20px 96px;
    }}

    /* Header */
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
      animation: fadeSlideDown 0.6s var(--spring) both;
    }}
    .brand-row {{
      display: flex;
       flex-wrap: wrap;
      align-items: center;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .brand-badge {{
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-family: "Plus Jakarta Sans", sans-serif;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.09em;
      padding: 5px 12px;
      border-radius: 999px;
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      color: var(--gold-text);
    }}
    .live-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
      animation: pulseDot 2s infinite;
    }}
    .date-chip {{
      font-family: "JetBrains Mono", monospace;
      font-size: 11.5px;
      color: var(--muted);
      padding: 4px 10px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    h1 {{
      margin: 0;
      font-family: "Plus Jakarta Sans", sans-serif;
      font-size: clamp(23px, 3.2vw, 34px);
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.18;
    }}
    .subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: clamp(13.5px, 1.5vw, 15px);
      max-width: 68ch;
    }}
    .header-actions {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 10px 16px;
      min-height: 42px;
      border-radius: 11px;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      transition: transform 0.2s var(--spring), border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
      user-select: none;
    }}
    .btn:hover {{
      transform: translateY(-2px);
      border-color: var(--accent);
      background: var(--surface-hover);
      box-shadow: 0 6px 18px -6px var(--accent-glow);
    }}
    .btn:active {{
      transform: translateY(0) scale(0.97);
    }}
    .btn-primary {{
      background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
      border-color: rgba(255, 255, 255, 0.15);
      color: #ffffff;
      box-shadow: 0 6px 18px -4px rgba(37, 99, 235, 0.45);
    }}
    .btn-primary:hover {{
      background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
      border-color: rgba(255, 255, 255, 0.3);
    }}

    /* 60-Second CFO Hero Brief */
    .hero-section {{
      margin: 24px 0 26px;
      background: var(--hero-gradient);
      border: 1px solid var(--gold-border);
      border-radius: 18px;
      padding: 22px;
      box-shadow: var(--card-shadow);
      position: relative;
      overflow: hidden;
      animation: fadeSlideUp 0.65s 0.08s var(--spring) both;
    }}
    .hero-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      margin-bottom: 16px;
    }}
    .hero-title {{
      display: flex;
      align-items: center;
      gap: 9px;
      font-family: "Plus Jakarta Sans", sans-serif;
      font-size: clamp(14px, 1.8vw, 16px);
      font-weight: 800;
      color: var(--gold-text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin: 0;
    }}
    .hero-sub {{
      font-size: 12.5px;
      color: var(--muted);
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
      gap: 16px;
    }}
    .hero-card {{
      background: var(--surface);
      backdrop-filter: blur(10px);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      transition: transform 0.28s var(--spring), border-color 0.25s ease, box-shadow 0.28s ease;
    }}
    .hero-card:hover {{
      border-color: var(--gold-border);
      transform: translateY(-4px);
      box-shadow: 0 14px 28px -10px rgba(245, 158, 11, 0.2);
    }}
    .rank-pill {{
      font-family: "JetBrains Mono", monospace;
      font-size: 10.5px;
      font-weight: 700;
      padding: 3px 9px;
      border-radius: 6px;
      background: var(--gold-bg);
      color: var(--gold-text);
      border: 1px solid var(--gold-border);
    }}

    /* KPI Strip */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 24px;
      animation: fadeSlideUp 0.65s 0.15s var(--spring) both;
    }}
    .kpi-card {{
      background: var(--surface);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px 18px;
      cursor: pointer;
      position: relative;
      overflow: hidden;
      transition: transform 0.25s var(--spring), border-color 0.2s ease, box-shadow 0.25s ease;
    }}
    .kpi-card::after {{
      content: "";
      position: absolute;
      inset: 0;
      background: radial-gradient(320px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(59, 130, 246, 0.1), transparent 40%);
      opacity: 0;
      transition: opacity 0.25s;
      pointer-events: none;
    }}
    .kpi-card:hover {{
      transform: translateY(-3px);
      border-color: var(--accent);
      box-shadow: var(--card-shadow);
    }}
    .kpi-card:hover::after {{
      opacity: 1;
    }}
    .kpi-card.active-kpi {{
      border-color: var(--accent);
      box-shadow: 0 0 0 1px var(--accent);
    }}
    .kpi-label {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
    }}
    .kpi-val {{
      font-family: "Plus Jakarta Sans", sans-serif;
      font-size: clamp(22px, 2.5vw, 28px);
      font-weight: 800;
      margin-top: 4px;
      line-height: 1.1;
    }}
    .kpi-sub {{
      font-size: 11.5px;
      color: var(--muted);
      margin-top: 4px;
    }}

    /* Glassmorphic Sticky Filter & View Bar */
    .controls {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      background: var(--glass-bg);
      backdrop-filter: blur(16px);
      -webkit-backdrop-filter: blur(16px);
      border: 1px solid var(--border);
      padding: 10px 14px;
      border-radius: 15px;
      position: sticky;
      top: 10px;
      z-index: 40;
      box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.35);
      transition: box-shadow 0.2s ease;
    }}
    .tabs {{
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      max-width: 100%;
      scrollbar-width: none;
      -ms-overflow-style: none;
      padding-bottom: 2px;
    }}
    .tabs::-webkit-scrollbar {{
      display: none;
    }}
    .tab {{
      cursor: pointer;
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      padding: 8px 13px;
      min-height: 38px;
      border-radius: 9px;
      font-size: 12.5px;
      font-weight: 600;
      white-space: nowrap;
      flex-shrink: 0;
      transition: all 0.2s var(--spring);
    }}
    .tab:hover {{
      color: var(--text);
      background: var(--surface-hover);
    }}
    .tab.active {{
      background: var(--accent);
      color: #ffffff;
      box-shadow: 0 4px 12px -2px var(--accent-glow);
    }}
    .right-controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      justify-content: flex-end;
      min-width: 240px;
    }}
    .search-wrap {{
      position: relative;
      flex: 1;
      max-width: 290px;
    }}
    .search-input {{
      width: 100%;
      padding: 8px 32px 8px 13px;
      min-height: 38px;
      border-radius: 9px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      font-size: 13px;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }}
    .search-input:focus {{
      outline: none;
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-glow);
    }}
    .kbd-hint {{
      position: absolute;
      right: 9px;
      top: 50%;
      transform: translateY(-50%);
      font-family: "JetBrains Mono", monospace;
      font-size: 10.5px;
      color: var(--muted);
      border: 1px solid var(--border);
      padding: 1px 5px;
      border-radius: 4px;
      pointer-events: none;
    }}
    .view-toggle {{
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: 9px;
      overflow: hidden;
      background: var(--bg);
      flex-shrink: 0;
    }}
    .view-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      color: var(--muted);
      padding: 7px 11px;
      min-height: 36px;
      font-size: 12px;
      font-weight: 600;
      transition: background 0.15s, color 0.15s;
    }}
    .view-btn.active {{
      background: var(--surface-elevated);
      color: var(--text);
    }}

    /* Cards Grid View */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 18px;
    }}
    .news-card {{
      background: var(--surface);
      backdrop-filter: blur(8px);
      border: 1px solid var(--border);
      border-radius: 16px;
      padding: 22px 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      overflow: hidden;
      box-shadow: var(--card-shadow);
      opacity: 0;
      transform: translateY(22px) scale(0.985);
      transition:
        opacity 0.55s var(--spring),
        transform 0.55s var(--spring),
        border-color 0.22s ease,
        box-shadow 0.25s ease;
    }}
    .news-card.in-view {{
      opacity: 1;
      transform: translateY(0) scale(1);
    }}
    .news-card::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: radial-gradient(450px circle at var(--mouse-x, 50%) var(--mouse-y, 50%), rgba(59, 130, 246, 0.08), transparent 45%);
      opacity: 0;
      transition: opacity 0.3s ease;
      pointer-events: none;
    }}
    .news-card:hover {{
      transform: translateY(-4px) scale(1.003);
      border-color: var(--accent);
      box-shadow: 0 18px 36px -12px rgba(0, 0, 0, 0.5), 0 0 0 1px var(--accent-glow);
    }}
    .news-card:hover::before {{
      opacity: 1;
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 8px;
      margin-bottom: 12px;
    }}
    .tag-group {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
    }}
    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .badge-high {{
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      color: var(--gold-text);
    }}
    .badge-ops {{
      background: var(--emerald-bg);
      border: 1px solid var(--emerald-border);
      color: var(--emerald-text);
    }}
    .badge-gen {{
      background: var(--blue-bg);
      border: 1px solid var(--blue-border);
      color: var(--blue-text);
    }}
    .pub-pill {{
      font-size: 11px;
      font-weight: 600;
      padding: 3px 9px;
      border-radius: 6px;
      background: var(--surface-elevated);
      color: var(--text-secondary);
      border: 1px solid var(--border-subtle);
    }}
    .card-actions {{
      display: flex;
      align-items: center;
      gap: 2px;
    }}
    .icon-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      font-size: 15px;
      color: var(--muted);
      width: 32px;
      height: 32px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      transition: background 0.15s, color 0.15s, transform 0.2s var(--spring);
    }}
    .icon-btn:hover {{
      background: var(--surface-elevated);
      color: var(--text);
      transform: scale(1.12);
    }}
    .icon-btn.saved {{
      color: #fbbf24;
      animation: starPop 0.35s var(--spring);
    }}
    .card-title {{
      margin: 0 0 10px;
      font-family: "Plus Jakarta Sans", sans-serif;
      font-size: 16.5px;
      font-weight: 700;
      line-height: 1.4;
    }}
    .card-title a {{
      color: var(--text);
      text-decoration: none;
      transition: color 0.15s ease;
    }}
    .card-title a:hover {{
      color: var(--accent);
    }}
    .card-summary {{
      font-size: 13.5px;
      color: var(--muted);
      margin: 0 0 14px;
      line-height: 1.55;
    }}
    .benefit-box {{
      background: var(--benefit-bg);
      border-left: 3px solid var(--gold-text);
      padding: 12px 14px;
      border-radius: 9px;
      font-size: 12.8px;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }}
    .benefit-box.ops-box {{ border-left-color: var(--emerald-text); }}
    .benefit-box.gen-box {{ border-left-color: var(--blue-text); }}
    .benefit-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 5px;
    }}
    .benefit-label {{
      font-size: 10.5px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--gold-text);
    }}
    .ops-box .benefit-label {{ color: var(--emerald-text); }}
    .gen-box .benefit-label {{ color: var(--blue-text); }}
    .score-meter-wrap {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-family: "JetBrains Mono", monospace;
      font-size: 10.5px;
      color: var(--muted);
    }}
    .score-bar {{
      width: 44px;
      height: 5px;
      background: var(--border);
      border-radius: 99px;
      overflow: hidden;
    }}
    .score-fill {{
      height: 100%;
      border-radius: 99px;
      background: var(--gold-text);
    }}
    .ops-box .score-fill {{ background: var(--emerald-text); }}
    .gen-box .score-fill {{ background: var(--blue-text); }}

    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
      padding-top: 12px;
      border-top: 1px solid var(--border-subtle);
    }}
    .read-link {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .read-link span.arrow {{
      display: inline-block;
      transition: transform 0.2s var(--spring);
    }}
    .news-card:hover .read-link span.arrow,
    .hero-card:hover .read-link span.arrow {{
      transform: translateX(4px);
    }}

    /* Compact Table View */
    .compact-table-wrap {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 15px;
      overflow-x: auto;
      box-shadow: var(--card-shadow);
      animation: fadeSlideUp 0.4s var(--spring) both;
    }}
    table.compact-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13.5px;
    }}
    .compact-table th {{
      text-align: left;
      padding: 13px 16px;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--muted);
      border-bottom: 1px solid var(--border);
      background: var(--surface-elevated);
      white-space: nowrap;
    }}
    .compact-table td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border-subtle);
      vertical-align: top;
      transition: background 0.15s;
    }}
    .compact-table tr:hover td {{
      background: var(--surface-hover);
    }}
    .compact-headline {{
      font-family: "Plus Jakarta Sans", sans-serif;
      font-weight: 700;
      color: var(--text);
      text-decoration: none;
      display: block;
      margin-bottom: 3px;
    }}
    .compact-headline:hover {{
      color: var(--accent);
    }}
    .compact-takeaway {{
      font-size: 12.5px;
      color: var(--muted);
    }}

    /* Floating Back-to-Top Button */
    #backToTop {{
      position: fixed;
      bottom: 24px;
      left: 24px;
      width: 44px;
      height: 44px;
      border-radius: 50%;
      border: 1px solid var(--border);
      background: var(--glass-bg);
      backdrop-filter: blur(12px);
      color: var(--text);
      font-size: 18px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.35);
      opacity: 0;
      transform: translateY(14px) scale(0.9);
      pointer-events: none;
      transition: all 0.25s var(--spring);
      z-index: 90;
    }}
    #backToTop.visible {{
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }}
    #backToTop:hover {{
      border-color: var(--accent);
      transform: translateY(-3px) scale(1.05);
    }}

    /* Toast Notification */
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: var(--surface-solid);
      border: 1px solid var(--emerald-border);
      color: var(--text);
      font-weight: 600;
      font-size: 13px;
      padding: 12px 18px;
      border-radius: 12px;
      box-shadow: 0 12px 30px rgba(0, 0, 0, 0.45);
      display: flex;
      align-items: center;
      gap: 8px;
      opacity: 0;
      transform: translateY(12px) scale(0.96);
      pointer-events: none;
      transition: all 0.25s var(--spring);
      z-index: 100;
    }}
    #toast.show {{
      opacity: 1;
      transform: translateY(0) scale(1);
    }}

    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 56px 20px;
      color: var(--muted);
      background: var(--surface);
      border: 1px dashed var(--border);
      border-radius: 16px;
    }}

    /* Keyframe Animations */
    @keyframes fadeSlideDown {{
      from {{ opacity: 0; transform: translateY(-14px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes fadeSlideUp {{
      from {{ opacity: 0; transform: translateY(18px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes pulseDot {{
      0% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }}
      70% {{ box-shadow: 0 0 0 7px rgba(16, 185, 129, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }}
    }}
    @keyframes starPop {{
      0% {{ transform: scale(1); }}
      45% {{ transform: scale(1.38) rotate(12deg); }}
      100% {{ transform: scale(1); }}
    }}

    /* Mobile & Tablet Responsive Breakpoints */
    @media (max-width: 960px) {{
      .kpi-grid {{
        grid-template-columns: repeat(2, 1fr);
      }}
    }}
    @media (max-width: 680px) {{
      .container {{
        padding: 18px 14px 84px;
      }}
      header {{
        align-items: stretch;
        gap: 14px;
      }}
      .header-actions {{
        width: 100%;
      }}
      .header-actions .btn {{
        flex: 1;
      }}
      .hero-section {{
        padding: 16px;
      }}
      .hero-grid {{
        grid-template-columns: 1fr;
      }}
      .kpi-grid {{
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
      }}
      .kpi-card {{
        padding: 13px 14px;
      }}
      .controls {{
        padding: 10px 12px;
        top: 6px;
      }}
      .right-controls {{
        width: 100%;
        min-width: 100%;
      }}
      .search-wrap {{
        max-width: none;
      }}
      .kbd-hint {{
        display: none;
      }}
      .cards-grid {{
        grid-template-columns: 1fr;
        gap: 14px;
      }}
      .news-card {{
        padding: 18px;
      }}
      .compact-hide-mobile {{
        display: none;
      }}
      #toast {{
        left: 14px;
        right: 14px;
        bottom: 16px;
        justify-content: center;
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        transition-duration: 0.01ms !important;
      }}
    }}
  </style>
</head>
<body>
  <div id="scrollProgress"></div>

  <div class="container">
    <header>
      <div>
        <div class="brand-row">
          <div class="brand-badge"><span class="live-dot"></span> 🇬🇧💷 UK Finance Team Priority Edition</div>
          <span class="date-chip">{html.escape(date_str)}</span>
        </div>
        <h1>Daily AI News & CFO Intelligence</h1>
        <p class="subtitle">Curated & ranked by practical benefit for UK Finance, Accounting, Audit & FP&A teams alongside global AI breakthroughs.</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" onclick="copyTeamBriefing()">📋 Copy Team Summary</button>
        <button class="btn" onclick="toggleTheme()" aria-label="Toggle colour theme">☀️ / 🌙 Theme</button>
      </div>
    </header>

    <!-- 60-Second CFO Hero Brief -->
    <section class="hero-section" id="heroSection">
      <div class="hero-header">
        <h2 class="hero-title">⚡ 60-Second UK Finance Morning Brief — Top 3 Today</h2>
        <span class="hero-sub">Highest-priority regulatory, audit & CFO insights</span>
      </div>
      <div class="hero-grid" id="heroGrid"></div>
    </section>

    <!-- Interactive KPI Cards with Animated Count-Up -->
    <div class="kpi-grid">
      <div class="kpi-card" data-kpi="high" onclick="setFilterByName('high')">
        <div class="kpi-label">🇬🇧 High UK Finance Impact</div>
        <div class="kpi-val" style="color: var(--gold-text);" data-count="{high_impact_count}">{high_impact_count}</div>
        <div class="kpi-sub">FCA, CFO, Audit & UK Regulation</div>
      </div>
      <div class="kpi-card" data-kpi="ops" onclick="setFilterByName('ops')">
        <div class="kpi-label">⚡ Finance Ops & Security</div>
        <div class="kpi-val" style="color: var(--emerald-text);" data-count="{ops_count}">{ops_count}</div>
        <div class="kpi-sub">AI Agents, Privacy & Models</div>
      </div>
      <div class="kpi-card" data-kpi="general" onclick="setFilterByName('general')">
        <div class="kpi-label">🌐 General AI & Research</div>
        <div class="kpi-val" style="color: var(--blue-text);" data-count="{general_count}">{general_count}</div>
        <div class="kpi-sub">Global Labs, Press & ArXiv</div>
      </div>
      <div class="kpi-card active-kpi" data-kpi="all" onclick="setFilterByName('all')">
        <div class="kpi-label">📊 Total Curated Stories</div>
        <div class="kpi-val" data-count="{len(cards)}">{len(cards)}</div>
        <div class="kpi-sub">Ranked across 11 live feeds</div>
      </div>
    </div>

    <!-- Glassmorphic Sticky Filter & View Bar -->
    <div class="controls">
      <div class="tabs" role="tablist">
        <button class="tab active" data-filter="all" onclick="setFilter('all', this)">All Prioritised ({len(cards)})</button>
        <button class="tab" data-filter="high" onclick="setFilter('high', this)">🇬🇧💷 UK Finance & CFO ({high_impact_count})</button>
        <button class="tab" data-filter="ops" onclick="setFilter('ops', this)">⚡ Ops & Security ({ops_count})</button>
        <button class="tab" data-filter="general" onclick="setFilter('general', this)">🌐 General AI ({general_count})</button>
        <button class="tab" data-filter="saved" id="savedTabBtn" onclick="setFilter('saved', this)">⭐ Saved (0)</button>
      </div>
      <div class="right-controls">
        <div class="search-wrap">
          <input type="search" id="searchInput" class="search-input" placeholder="Search FCA, Deloitte, audit, OpenAI..." oninput="renderMain()" />
          <span class="kbd-hint">/</span>
        </div>
        <div class="view-toggle" role="group" aria-label="View mode">
          <button class="view-btn active" id="viewCardsBtn" onclick="setViewMode('cards')">⊞ Cards</button>
          <button class="view-btn" id="viewTableBtn" onclick="setViewMode('table')">☰ Compact</button>
        </div>
      </div>
    </div>

    <div id="mainContainer"></div>
  </div>

  <button id="backToTop" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})" aria-label="Back to top" title="Back to top">↑</button>
  <div id="toast" role="status" aria-live="polite">✓ Copied Top 5 UK Finance Briefing!</div>

  <script>
    const ITEMS = {cards_json};
    let currentFilter = 'all';
    let currentView = localStorage.getItem('ai-news-view') || 'cards';
    let savedUrls = new Set(JSON.parse(localStorage.getItem('ai-news-saved') || '[]'));
    let revealObserver = null;

    function escapeHtml(str) {{
      const d = document.createElement('div');
      d.textContent = str || '';
      return d.innerHTML;
    }}

    function showToast(msg) {{
      const t = document.getElementById('toast');
      t.textContent = msg;
      t.classList.add('show');
      clearTimeout(window._toastTimer);
      window._toastTimer = setTimeout(() => t.classList.remove('show'), 2600);
    }}

    function formatRelativeTime(pubStr) {{
      if (!pubStr || pubStr === 'Recent') return 'Recent';
      const iso = pubStr.replace(' UTC', ':00Z').replace(' ', 'T');
      const dt = new Date(iso);
      if (isNaN(dt.getTime())) return pubStr;
      const diffMs = Date.now() - dt.getTime();
      const diffHours = Math.floor(diffMs / 3600000);
      if (diffHours < 1) return 'Just now';
      if (diffHours < 24) return `${{diffHours}}h ago`;
      const diffDays = Math.floor(diffHours / 24);
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${{diffDays}}d ago`;
      return pubStr.slice(0, 10);
    }}

    function badgeClass(score) {{
      if (score >= 85) return 'badge-high';
      if (score >= 70) return 'badge-ops';
      return 'badge-gen';
    }}

    function boxClass(score) {{
      if (score >= 85) return '';
      if (score >= 70) return 'ops-box';
      return 'gen-box';
    }}

    function updateSavedTabCount() {{
      const btn = document.getElementById('savedTabBtn');
      if (btn) btn.textContent = `⭐ Saved (${{savedUrls.size}})`;
    }}

    function toggleSave(url, ev) {{
      if (ev) ev.stopPropagation();
      const adding = !savedUrls.has(url);
      if (adding) {{
        savedUrls.add(url);
        showToast('⭐ Saved story to your reading list');
      }} else {{
        savedUrls.delete(url);
        showToast('Removed from saved stories');
      }}
      localStorage.setItem('ai-news-saved', JSON.stringify(Array.from(savedUrls)));
      updateSavedTabCount();
      renderHero();
      renderMain();
    }}

    function shareStory(title, url, ev) {{
      if (ev) ev.stopPropagation();
      if (navigator.share) {{
        navigator.share({{ title, url }}).catch(() => {{}});
      }} else {{
        navigator.clipboard.writeText(`${{title}} — ${{url}}`).then(() => {{
          showToast('🔗 Story link copied to clipboard!');
        }});
      }}
    }}

    function setupScrollReveal() {{
      if (revealObserver) revealObserver.disconnect();
      const cards = document.querySelectorAll('.news-card');
      if (!('IntersectionObserver' in window)) {{
        cards.forEach(c => c.classList.add('in-view'));
        return;
      }}
      revealObserver = new IntersectionObserver((entries) => {{
        entries.forEach((entry) => {{
          if (entry.isIntersecting) {{
            entry.target.classList.add('in-view');
            revealObserver.unobserve(entry.target);
          }}
        }});
      }}, {{ threshold: 0.08, rootMargin: '0px 0px -20px 0px' }});

      cards.forEach((card, i) => {{
        card.style.transitionDelay = `${{Math.min(i % 6, 5) * 45}}ms`;
        revealObserver.observe(card);
      }});
    }}

    function attachSpotlightTracking() {{
      document.querySelectorAll('.news-card, .kpi-card').forEach(card => {{
        card.addEventListener('mousemove', (e) => {{
          const rect = card.getBoundingClientRect();
          card.style.setProperty('--mouse-x', `${{e.clientX - rect.left}}px`);
          card.style.setProperty('--mouse-y', `${{e.clientY - rect.top}}px`);
        }}, {{ passive: true }});
      }});
    }}

    function renderHero() {{
      const top3 = ITEMS.filter(i => i.score >= 85).slice(0, 3);
      const heroSec = document.getElementById('heroSection');
      const heroGrid = document.getElementById('heroGrid');
      if (!top3.length || currentFilter !== 'all') {{
        heroSec.style.display = 'none';
        return;
      }}
      heroSec.style.display = 'block';

      heroGrid.innerHTML = top3.map((item, idx) => {{
        const isSaved = savedUrls.has(item.url);
        return `
          <article class="hero-card">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="rank-pill">#${{idx + 1}} PRIORITY</span>
                  <span class="pub-pill">${{escapeHtml(item.source)}}</span>
                </div>
                <div class="card-actions">
                  <button class="icon-btn" title="Copy story link" onclick="shareStory('${{escapeHtml(item.title.replace(/'/g, "\\\\'"))}}', '${{escapeHtml(item.url)}}', event)">🔗</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" title="Save for later" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                    ${{isSaved ? '⭐' : '☆'}}
                  </button>
                </div>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              <p class="card-summary" style="margin-bottom: 12px;">${{escapeHtml(item.benefit)}}</p>
            </div>
            <div class="card-footer">
              <span>${{escapeHtml(item.func_tag)}} · <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span></span>
              <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Read <span class="arrow">→</span></a>
            </div>
          </article>
        `;
      }}).join('');
    }}

    function setFilter(filter, btn) {{
      currentFilter = filter;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      if (btn) {{
        btn.classList.add('active');
        btn.scrollIntoView({{ behavior: 'smooth', inline: 'center', block: 'nearest' }});
      }}
      document.querySelectorAll('.kpi-card').forEach(k => {{
        k.classList.toggle('active-kpi', k.getAttribute('data-kpi') === filter);
      }});
      renderHero();
      renderMain();
    }}

    function setFilterByName(filter) {{
      const btn = document.querySelector(`.tab[data-filter="${{filter}}"]`);
      setFilter(filter, btn);
    }}

    function setViewMode(mode) {{
      currentView = mode;
      localStorage.setItem('ai-news-view', mode);
      document.getElementById('viewCardsBtn').classList.toggle('active', mode === 'cards');
      document.getElementById('viewTableBtn').classList.toggle('active', mode === 'table');
      renderMain();
    }}

    function renderMain() {{
      const q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const container = document.getElementById('mainContainer');

      const filtered = ITEMS.filter(item => {{
        if (currentFilter === 'high' && item.score < 85) return false;
        if (currentFilter === 'ops' && (item.score < 70 || item.score >= 85)) return false;
        if (currentFilter === 'general' && item.score >= 70) return false;
        if (currentFilter === 'saved' && !savedUrls.has(item.url)) return false;
        if (q) {{
          const hay = (item.title + ' ' + item.summary + ' ' + item.benefit + ' ' + item.source + ' ' + item.func_tag).toLowerCase();
          if (!hay.includes(q)) return false;
        }}
        return true;
      }});

      if (!filtered.length) {{
        container.className = '';
        container.innerHTML = '<div class="empty-state">No stories match your current filter or search query.</div>';
        return;
      }}

      if (currentView === 'table') {{
        container.className = 'compact-table-wrap';
        container.innerHTML = `
          <table class="compact-table">
            <thead>
              <tr>
                <th>Save</th>
                <th>Area</th>
                <th>Story & Practical UK Finance Takeaway</th>
                <th class="compact-hide-mobile">Publisher</th>
                <th class="compact-hide-mobile">Priority</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              ${{filtered.map(item => {{
                const isSaved = savedUrls.has(item.url);
                return `
                  <tr>
                    <td>
                      <button class="icon-btn ${{isSaved ? 'saved' : ''}}" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                        ${{isSaved ? '⭐' : '☆'}}
                      </button>
                    </td>
                    <td><span class="badge ${{badgeClass(item.score)}}">${{escapeHtml(item.func_tag)}}</span></td>
                    <td>
                      <a class="compact-headline" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
                      <div class="compact-takeaway">${{escapeHtml(item.benefit)}}</div>
                    </td>
                    <td class="compact-hide-mobile"><span class="pub-pill">${{escapeHtml(item.source)}}</span></td>
                    <td class="compact-hide-mobile"><strong>${{item.score}}</strong>/100</td>
                    <td style="white-space:nowrap;" title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</td>
                  </tr>
                `;
              }}).join('')}}
            </tbody>
          </table>
        `;
        return;
      }}

      container.className = 'cards-grid';
      container.innerHTML = filtered.map(item => {{
        const isSaved = savedUrls.has(item.url);
        const summaryHtml = item.summary
          ? `<p class="card-summary">${{escapeHtml(item.summary)}}</p>`
          : '';
        return `
          <article class="news-card">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="badge ${{badgeClass(item.score)}}">${{escapeHtml(item.func_tag)}}</span>
                  <span class="pub-pill">${{escapeHtml(item.source)}}</span>
                </div>
                <div class="card-actions">
                  <button class="icon-btn" title="Share / copy link" onclick="shareStory('${{escapeHtml(item.title.replace(/'/g, "\\\\'"))}}', '${{escapeHtml(item.url)}}', event)">🔗</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" title="Save for later" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                    ${{isSaved ? '⭐' : '☆'}}
                  </button>
                </div>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              ${{summaryHtml}}
            </div>
            <div>
              <div class="benefit-box ${{boxClass(item.score)}}">
                <div class="benefit-header">
                  <span class="benefit-label">🇬🇧 UK Finance Team Takeaway</span>
                  <span class="score-meter-wrap">
                    <span>${{item.score}}/100</span>
                    <span class="score-bar"><span class="score-fill" style="width:${{item.score}}%"></span></span>
                  </span>
                </div>
                ${{escapeHtml(item.benefit)}}
              </div>
              <div class="card-footer">
                <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span>
                <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Read article <span class="arrow">→</span></a>
              </div>
            </div>
          </article>
        `;
      }}).join('');

      setupScrollReveal();
      attachSpotlightTracking();
    }}

    function animateKpiCounters() {{
      document.querySelectorAll('.kpi-val[data-count]').forEach(el => {{
        const target = parseInt(el.getAttribute('data-count'), 10) || 0;
        const duration = 650;
        const start = performance.now();
        function step(now) {{
          const p = Math.min((now - start) / duration, 1);
          const eased = 1 - Math.pow(1 - p, 3);
          el.textContent = Math.round(target * eased);
          if (p < 1) requestAnimationFrame(step);
        }}
        requestAnimationFrame(step);
      }});
    }}

    function copyTeamBriefing() {{
      const top5 = ITEMS.slice(0, 5);
      const lines = [
        `🇬🇧💷 *UK Finance & AI Morning Briefing ({html.escape(date_str)})*`,
        `📊 Live Dashboard: https://mhutt97.github.io/ai-news-daily/`,
        ``
      ];
      top5.forEach((it, idx) => {{
        lines.push(`${{idx + 1}}. *${{it.title}}* (${{it.source}} — ${{it.func_tag}})`);
        lines.push(`   ↳ ${{(it.benefit || '')}}`);
        lines.push(`   🔗 ${{it.url}}`);
        lines.push(``);
      }});
      navigator.clipboard.writeText(lines.join('\\n')).then(() => {{
        showToast('✓ Copied Top 5 UK Finance Briefing to clipboard!');
      }});
    }}

    function toggleTheme() {{
      const root = document.documentElement;
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('ai-news-theme', next);
    }}

    // Scroll Progress & Back-to-Top Listener
    window.addEventListener('scroll', () => {{
      const scrollTop = window.scrollY || document.documentElement.scrollTop;
      const docHeight = document.documentElement.scrollHeight - window.innerHeight;
      const pct = docHeight > 0 ? Math.min((scrollTop / docHeight) * 100, 100) : 0;
      document.getElementById('scrollProgress').style.width = `${{pct}}%`;
      document.getElementById('backToTop').classList.toggle('visible', scrollTop > 420);
    }}, {{ passive: true }});

    // Keyboard shortcut '/' to focus search
    window.addEventListener('keydown', (e) => {{
      if (e.key === '/' && document.activeElement !== document.getElementById('searchInput')) {{
        e.preventDefault();
        document.getElementById('searchInput').focus();
      }}
    }});

    (function init() {{
      const savedTheme = localStorage.getItem('ai-news-theme');
      if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
      document.getElementById('viewCardsBtn').classList.toggle('active', currentView === 'cards');
      document.getElementById('viewTableBtn').classList.toggle('active', currentView === 'table');
      updateSavedTabCount();
      renderHero();
      renderMain();
      animateKpiCounters();
    }})();
  </script>
</body>
</html>"""


def generate_dashboard_files(
    items: list[NewsItem], settings: Settings
) -> tuple[Path, list[dict[str, object]]]:
    """Generate docs/index.html and docs/data.json for the web dashboard."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    today_str = datetime.now().strftime("%B %d, %Y")
    cards = prepare_prioritized_cards(items, settings)
    dashboard_html = build_dashboard_html(cards, today_str)

    index_path = DOCS_DIR / "index.html"
    data_path = DOCS_DIR / "data.json"
    index_path.write_text(dashboard_html, encoding="utf-8")
    data_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    return index_path, cards
