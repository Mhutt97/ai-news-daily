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

    # Extract any percentage or statistic in the headline to make takeaways ultra-specific
    stat_match = re.search(r"(\d+%|\£\d+[a-z]*|\$\d+\s*(?:billion|million|bn|m)|\d+×)", item.title, re.IGNORECASE)
    stat_str = stat_match.group(1) if stat_match else ""

    # Default baseline
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

    # Granular, story-specific UK Finance rules so cards never repeat generic boilerplate
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
    elif re.search(r"\b(soc|attestation|certification|assurance|selective auditing|dataset-use auditing)\b", text):
        score = 96
        tier = "High UK Finance Impact"
        func_tag = "🛡️ Audit & Assurance"
        benefit = (
            f"AI Assurance & Controls ({item.source}): Practical framework for using SOC reporting, "
            f"independent attestation, and selective auditing to verify AI outputs in financial workflows."
        )
    elif re.search(r"\b(internal auditor|internal auditors|external audit|kpmg|deloitte|pwc|ey|bdo)\b", text):
        score = max(score, 94)
        tier = "High UK Finance Impact"
        func_tag = "🛡️ Audit & Big Four"
        benefit = (
            f"Audit Practice Benchmark ({item.source}): Tracks how internal audit teams and Big Four "
            f"advisors are adopting AI for risk testing, sampling, and control validation."
        )
    elif re.search(r"\b(cfo|cfos|finance leader|finance leaders|finance team|finance teams|fp&a|accountant|accounting)\b", text):
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
    elif re.search(r"\b(no internet|live internet|containment|securing|red-team|llm-attacker|privacy|gmail|data)\b", text):
        score = max(score, 84)
        tier = "Finance Ops & Governance"
        func_tag = "🔒 Data Privacy & Risk"
        benefit = (
            f"Data Governance Alert ({item.source}): Important context for finance teams evaluating "
            f"model containment, cloud privacy settings, and protecting confidential financial data."
        )
    elif re.search(r"\b(agent|agents|voice|local|macbook|harness|storage|scaling|multi-tenancy)\b", text):
        score = max(score, 78)
        tier = "Finance Ops & Productivity"
        func_tag = "🤖 AI Agents & Ops"
        benefit = (
            f"Enterprise AI Infrastructure ({item.source}): Demonstrates how production AI harnesses, "
            f"local models, and messaging agents are maturing for day-to-day business workflows."
        )
    elif re.search(r"\b(gemini|gpt|claude|grok|frontier model|openai|deepmind|trainium)\b", text):
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
    """Render an executive-grade UK Finance & General AI News Dashboard HTML."""
    high_impact_count = sum(1 for c in cards if int(c["score"]) >= 85)
    ops_count = sum(1 for c in cards if 70 <= int(c["score"]) < 85)
    general_count = sum(1 for c in cards if int(c["score"]) < 70)

    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>UK Finance & AI Daily Intelligence — {html.escape(date_str)}</title>
  <style>
    :root {{
      --bg: #090d16;
      --surface: #111827;
      --surface-elevated: #172033;
      --surface-hover: #1e293b;
      --border: #1f2937;
      --border-subtle: rgba(255, 255, 255, 0.07);
      --text: #f8fafc;
      --text-secondary: #cbd5e1;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --accent-hover: #2563eb;
      --gold-bg: rgba(245, 158, 11, 0.12);
      --gold-border: rgba(245, 158, 11, 0.4);
      --gold-text: #fbbf24;
      --emerald-bg: rgba(16, 185, 129, 0.12);
      --emerald-border: rgba(16, 185, 129, 0.35);
      --emerald-text: #34d399;
      --blue-bg: rgba(59, 130, 246, 0.12);
      --blue-border: rgba(59, 130, 246, 0.35);
      --blue-text: #60a5fa;
      --benefit-bg: rgba(15, 23, 42, 0.65);
      --hero-gradient: linear-gradient(135deg, rgba(30, 41, 59, 0.9) 0%, rgba(15, 23, 42, 0.95) 100%);
    }}
    [data-theme="light"] {{
      --bg: #f1f5f9;
      --surface: #ffffff;
      --surface-elevated: #f8fafc;
      --surface-hover: #f1f5f9;
      --border: #e2e8f0;
      --border-subtle: #e2e8f0;
      --text: #0f172a;
      --text-secondary: #334155;
      --muted: #64748b;
      --accent: #2563eb;
      --accent-hover: #1d4ed8;
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
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 1240px;
      margin: 0 auto;
      padding: 32px 24px 80px;
    }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
    }}
    .brand-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      padding: 5px 12px;
      border-radius: 999px;
      background: var(--gold-bg);
      border: 1px solid var(--gold-border);
      color: var(--gold-text);
      margin-bottom: 10px;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(24px, 2.8vw, 32px);
      letter-spacing: -0.025em;
      line-height: 1.2;
    }}
    .subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 14.5px;
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
      padding: 9px 15px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 7px;
      transition: all 0.15s ease;
    }}
    .btn:hover {{
      border-color: var(--accent);
      background: var(--surface-hover);
    }}
    .btn-primary {{
      background: var(--accent);
      border-color: var(--accent);
      color: #ffffff;
    }}
    .btn-primary:hover {{
      background: var(--accent-hover);
    }}

    /* 60-Second CFO Hero Brief */
    .hero-section {{
      margin: 26px 0 28px;
      background: var(--hero-gradient);
      border: 1px solid var(--gold-border);
      border-radius: 16px;
      padding: 22px 24px;
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
      gap: 10px;
      font-size: 16px;
      font-weight: 800;
      color: var(--gold-text);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin: 0;
    }}
    .hero-sub {{
      font-size: 13px;
      color: var(--muted);
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(310px, 1fr));
      gap: 16px;
    }}
    .hero-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: border-color 0.15s ease, transform 0.15s ease;
    }}
    .hero-card:hover {{
      border-color: var(--gold-border);
      transform: translateY(-2px);
    }}
    .rank-pill {{
      font-size: 11px;
      font-weight: 800;
      padding: 3px 9px;
      border-radius: 6px;
      background: var(--gold-bg);
      color: var(--gold-text);
      border: 1px solid var(--gold-border);
    }}

    /* KPI Strip */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
      gap: 14px;
      margin-bottom: 24px;
    }}
    .kpi-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 13px;
      padding: 15px 18px;
      cursor: pointer;
      transition: border-color 0.15s;
    }}
    .kpi-card:hover {{
      border-color: var(--accent);
    }}
    .kpi-label {{
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .kpi-val {{
      font-size: 26px;
      font-weight: 800;
      margin-top: 4px;
      line-height: 1.1;
    }}
    .kpi-sub {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 4px;
    }}

    /* Filter & View Controls */
    .controls {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 14px;
      margin-bottom: 24px;
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 12px 16px;
      border-radius: 14px;
      position: sticky;
      top: 12px;
      z-index: 20;
      box-shadow: 0 8px 20px rgba(0, 0, 0, 0.2);
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .tab {{
      cursor: pointer;
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      padding: 7px 13px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .tab:hover {{
      color: var(--text);
      background: var(--surface-hover);
    }}
    .tab.active {{
      background: var(--accent);
      color: #ffffff;
    }}
    .right-controls {{
      display: flex;
      align-items: center;
      gap: 10px;
      flex: 1;
      justify-content: flex-end;
      min-width: 260px;
    }}
    .search-input {{
      width: 100%;
      max-width: 280px;
      padding: 8px 13px;
      border-radius: 9px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      font-size: 13px;
    }}
    .view-toggle {{
      display: inline-flex;
      border: 1px solid var(--border);
      border-radius: 9px;
      overflow: hidden;
      background: var(--bg);
    }}
    .view-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      color: var(--muted);
      padding: 7px 11px;
      font-size: 12.5px;
      font-weight: 600;
    }}
    .view-btn.active {{
      background: var(--surface-elevated);
      color: var(--text);
    }}

    /* Cards Grid View */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
      gap: 18px;
    }}
    .news-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 22px 24px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transition: transform 0.15s ease, border-color 0.15s ease;
    }}
    .news-card:hover {{
      transform: translateY(-2px);
      border-color: var(--accent);
    }}
    .card-top {{
      display: flex;
      justify-content: space-between;
      align-items: center;
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
      padding: 3.5px 10px;
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
    .star-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      font-size: 16px;
      color: var(--muted);
      padding: 2px 6px;
      border-radius: 6px;
      transition: color 0.15s, transform 0.15s;
    }}
    .star-btn:hover {{
      transform: scale(1.15);
    }}
    .star-btn.saved {{
      color: #fbbf24;
    }}
    .card-title {{
      margin: 0 0 10px;
      font-size: 16.5px;
      font-weight: 700;
      line-height: 1.42;
    }}
    .card-title a {{
      color: var(--text);
      text-decoration: none;
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
      padding: 11px 14px;
      border-radius: 8px;
      font-size: 13px;
      color: var(--text-secondary);
      margin-bottom: 16px;
    }}
    .benefit-box.ops-box {{
      border-left-color: var(--emerald-text);
    }}
    .benefit-box.gen-box {{
      border-left-color: var(--blue-text);
    }}
    .benefit-label {{
      display: block;
      font-size: 10.5px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--gold-text);
      margin-bottom: 3px;
    }}
    .ops-box .benefit-label {{ color: var(--emerald-text); }}
    .gen-box .benefit-label {{ color: var(--blue-text); }}
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
    }}
    .read-link:hover {{
      text-decoration: underline;
    }}

    /* Compact Table View */
    .compact-table-wrap {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      overflow-x: auto;
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
    }}
    .compact-table tr:hover td {{
      background: var(--surface-hover);
    }}
    .compact-headline {{
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

    /* Toast Notification */
    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #10b981;
      color: #ffffff;
      font-weight: 700;
      font-size: 13.5px;
      padding: 12px 20px;
      border-radius: 10px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.35);
      opacity: 0;
      transform: translateY(10px);
      pointer-events: none;
      transition: all 0.2s ease;
      z-index: 100;
    }}
    #toast.show {{
      opacity: 1;
      transform: translateY(0);
    }}
    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 56px 20px;
      color: var(--muted);
      background: var(--surface);
      border: 1px dashed var(--border);
      border-radius: 14px;
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="brand-badge">🇬🇧💷 UK Finance Team Priority Edition</div>
        <h1>Daily AI News & CFO Intelligence Dashboard</h1>
        <p class="subtitle">Updated {html.escape(date_str)} · Curated & ranked for UK Finance, Accounting, Audit & FP&A teams</p>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" onclick="copyTeamBriefing()">📋 Copy Team Summary</button>
        <button class="btn" onclick="toggleTheme()">☀️ / 🌙 Theme</button>
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

    <!-- Interactive KPI Cards -->
    <div class="kpi-grid">
      <div class="kpi-card" onclick="setFilterByName('high')">
        <div class="kpi-label">🇬🇧 High UK Finance Impact</div>
        <div class="kpi-val" style="color: var(--gold-text);">{high_impact_count}</div>
        <div class="kpi-sub">FCA, CFO, Audit, Big Four & UK Regulation</div>
      </div>
      <div class="kpi-card" onclick="setFilterByName('ops')">
        <div class="kpi-label">⚡ Finance Ops & Data Governance</div>
        <div class="kpi-val" style="color: var(--emerald-text);">{ops_count}</div>
        <div class="kpi-sub">AI Agents, Data Privacy & Frontier Models</div>
      </div>
      <div class="kpi-card" onclick="setFilterByName('general')">
        <div class="kpi-label">🌐 General AI & Research</div>
        <div class="kpi-val" style="color: var(--blue-text);">{general_count}</div>
        <div class="kpi-sub">Global AI Labs, Tech Press, ArXiv & HN</div>
      </div>
      <div class="kpi-card" onclick="setFilterByName('all')">
        <div class="kpi-label">📊 Total Curated Stories</div>
        <div class="kpi-val">{len(cards)}</div>
        <div class="kpi-sub">Deduplicated & ranked from 11 live sources</div>
      </div>
    </div>

    <!-- Sticky Filter & View Bar -->
    <div class="controls">
      <div class="tabs">
        <button class="tab active" data-filter="all" onclick="setFilter('all', this)">All Prioritised ({len(cards)})</button>
        <button class="tab" data-filter="high" onclick="setFilter('high', this)">🇬🇧💷 UK Finance & CFO ({high_impact_count})</button>
        <button class="tab" data-filter="ops" onclick="setFilter('ops', this)">⚡ Ops & Data Security ({ops_count})</button>
        <button class="tab" data-filter="general" onclick="setFilter('general', this)">🌐 General AI & Research ({general_count})</button>
        <button class="tab" data-filter="saved" id="savedTabBtn" onclick="setFilter('saved', this)">⭐ Saved (0)</button>
      </div>
      <div class="right-controls">
        <input type="text" id="searchInput" class="search-input" placeholder="Filter by FCA, EY, Deloitte, audit, OpenAI..." oninput="renderMain()" />
        <div class="view-toggle">
          <button class="view-btn active" id="viewCardsBtn" onclick="setViewMode('cards')">⊞ Cards</button>
          <button class="view-btn" id="viewTableBtn" onclick="setViewMode('table')">☰ Compact</button>
        </div>
      </div>
    </div>

    <div id="mainContainer"></div>
  </div>

  <div id="toast">✓ Copied Top 5 UK Finance Briefing to clipboard!</div>

  <script>
    const ITEMS = {cards_json};
    let currentFilter = 'all';
    let currentView = localStorage.getItem('ai-news-view') || 'cards';
    let savedUrls = new Set(JSON.parse(localStorage.getItem('ai-news-saved') || '[]'));

    function escapeHtml(str) {{
      const d = document.createElement('div');
      d.textContent = str || '';
      return d.innerHTML;
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
      if (savedUrls.has(url)) {{
        savedUrls.delete(url);
      }} else {{
        savedUrls.add(url);
      }}
      localStorage.setItem('ai-news-saved', JSON.stringify(Array.from(savedUrls)));
      updateSavedTabCount();
      renderHero();
      renderMain();
    }}

    function renderHero() {{
      const top3 = ITEMS.filter(i => i.score >= 85).slice(0, 3);
      const heroSec = document.getElementById('heroSection');
      const heroGrid = document.getElementById('heroGrid');
      if (!top3.length || currentFilter !== 'all') {{
        heroSec.style.display = currentFilter === 'all' && top3.length ? 'block' : 'none';
        if (!top3.length) return;
      }} else {{
        heroSec.style.display = 'block';
      }}

      heroGrid.innerHTML = top3.map((item, idx) => {{
        const isSaved = savedUrls.has(item.url);
        return `
          <article class="hero-card">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="rank-pill">#${{idx + 1}} UK FINANCE PRIORITY</span>
                  <span class="pub-pill">${{escapeHtml(item.source)}}</span>
                </div>
                <button class="star-btn ${{isSaved ? 'saved' : ''}}" title="Save for later" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                  ${{isSaved ? '⭐' : '☆'}}
                </button>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              <p class="card-summary" style="margin-bottom: 12px;">${{escapeHtml(item.benefit)}}</p>
            </div>
            <div class="card-footer">
              <span>${{escapeHtml(item.func_tag)}} · <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span></span>
              <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Read →</a>
            </div>
          </article>
        `;
      }}).join('');
    }}

    function setFilter(filter, btn) {{
      currentFilter = filter;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      if (btn) btn.classList.add('active');
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
                <th>Publisher</th>
                <th>Priority</th>
                <th>Published</th>
              </tr>
            </thead>
            <tbody>
              ${{filtered.map(item => {{
                const isSaved = savedUrls.has(item.url);
                return `
                  <tr>
                    <td>
                      <button class="star-btn ${{isSaved ? 'saved' : ''}}" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                        ${{isSaved ? '⭐' : '☆'}}
                      </button>
                    </td>
                    <td><span class="badge ${{badgeClass(item.score)}}">${{escapeHtml(item.func_tag)}}</span></td>
                    <td>
                      <a class="compact-headline" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
                      <div class="compact-takeaway">${{escapeHtml(item.benefit)}}</div>
                    </td>
                    <td><span class="pub-pill">${{escapeHtml(item.source)}}</span></td>
                    <td><strong>${{item.score}}</strong>/100</td>
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
                <button class="star-btn ${{isSaved ? 'saved' : ''}}" title="Save for later" onclick="toggleSave('${{escapeHtml(item.url)}}', event)">
                  ${{isSaved ? '⭐' : '☆'}}
                </button>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              ${{summaryHtml}}
            </div>
            <div>
              <div class="benefit-box ${{boxClass(item.score)}}">
                <span class="benefit-label">🇬🇧 UK Finance Team Takeaway · Priority ${{item.score}}/100</span>
                ${{escapeHtml(item.benefit)}}
              </div>
              <div class="card-footer">
                <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span>
                <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Read full article →</a>
              </div>
            </div>
          </article>
        `;
      }}).join('');
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
        const t = document.getElementById('toast');
        t.classList.add('show');
        setTimeout(() => t.classList.remove('show'), 2800);
      }});
    }}

    function toggleTheme() {{
      const root = document.documentElement;
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('ai-news-theme', next);
    }}

    (function init() {{
      const savedTheme = localStorage.getItem('ai-news-theme');
      if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
      document.getElementById('viewCardsBtn').classList.toggle('active', currentView === 'cards');
      document.getElementById('viewTableBtn').classList.toggle('active', currentView === 'table');
      updateSavedTabCount();
      renderHero();
      renderMain();
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
