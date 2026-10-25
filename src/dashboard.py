"""Interactive UK Finance & AI News Dashboard generator and Finance Benefit prioritization engine."""

from __future__ import annotations

from datetime import datetime
import html
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from src.config import PROJECT_ROOT, Settings
from src.sources import NewsItem

DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_DASHBOARD_URL = "https://mhutt97.github.io/ai-news-daily/"

PUBLISHER_DOMAINS: dict[str, str] = {
    "deloitte": "deloitte.com",
    "ey": "ey.com",
    "pwc": "pwc.co.uk",
    "kpmg": "kpmg.com",
    "uk finance": "ukfinance.org.uk",
    "enterprise times": "enterprisetimes.co.uk",
    "it brief uk": "itbrief.co.uk",
    "seeking alpha": "seekingalpha.com",
    "going concern": "goingconcern.com",
    "tokenpost": "tokenpost.com",
    "openai": "openai.com",
    "google": "blog.google",
    "hugging face": "huggingface.co",
    "hf daily papers": "huggingface.co",
    "techcrunch": "techcrunch.com",
    "the verge": "theverge.com",
    "ars technica": "arstechnica.com",
    "mit technology review": "technologyreview.com",
    "arxiv": "arxiv.org",
    "hacker news": "news.ycombinator.com",
    "r/machinelearning": "reddit.com",
    "r/localllama": "reddit.com",
}


def resolve_publisher_domain(source_name: str, article_url: str) -> str:
    """Resolve the best domain for a publisher favicon."""
    s_lower = source_name.lower()
    for key, dom in PUBLISHER_DOMAINS.items():
        if key in s_lower:
            return dom
    try:
        parsed = urllib.parse.urlparse(article_url)
        if parsed.netloc and "news.google.com" not in parsed.netloc:
            return parsed.netloc.lstrip("www.")
    except Exception:
        pass
    return "ukfinance.org.uk"


def build_executive_breakdown(
    item: NewsItem, score: int, func_tag: str, benefit: str
) -> dict[str, str]:
    """Build structured 3-point Executive Drawer guidance + role-specific priority weights."""
    text = f"{item.title} {item.summary}".lower()

    # Role weights (cfo, audit, fpa)
    cfo_w = score
    audit_w = score
    fpa_w = score

    if "🏛️" in func_tag or "🛡️" in func_tag or "🔒" in func_tag:
        audit_w = min(100, score + 12)
        cfo_w = min(98, score + 4)
        ssl_risk = (
            "Directly impacts regulatory compliance, internal audit scoping, and model risk governance. "
            "Ensure any AI-assisted outputs have a documented human-in-the-loop review trail."
        )
        action = (
            "Log this update in your AI Risk & Governance register and review current workspace/vendor "
            "controls against FCA and internal audit standards."
        )
    elif "📈" in func_tag or "🏦" in func_tag or "📊" in func_tag:
        cfo_w = min(100, score + 10)
        fpa_w = min(96, score + 6)
        ssl_risk = (
            "Highlights governance pressure vs. control maturity: deploying AI too quickly without "
            "reconciliation checks creates financial reporting and disclosure exposure."
        )
        action = (
            "Benchmark your finance team's current AI pilot ROI and require clear time-saved or accuracy "
            "metrics before expanding software spend."
        )
    elif "🤖" in func_tag or "⚙️" in func_tag or "💻" in func_tag or "⚡" in func_tag or "🧠" in func_tag:
        fpa_w = min(99, score + 18)
        cfo_w = min(92, score + 6)
        ssl_risk = (
            "Verify data residency, multi-tenant isolation, and zero-training guarantees before connecting "
            "new AI agents or models to ERP, FP&A, or payroll spreadsheets."
        )
        action = (
            "Evaluate whether this capability can automate repetitive month-end close, variance commentary, "
            "or data extraction workflows in a sandboxed pilot."
        )
    else:
        fpa_w = min(90, score + 8)
        ssl_risk = (
            "Low immediate regulatory impact, but tracks emerging technical capabilities and vendor viability "
            "that will influence enterprise software over the next 6–12 months."
        )
        action = (
            "Monitor during quarterly finance technology reviews; no immediate policy or control changes required."
        )

    if "fca" in text:
        ssl_risk = (
            "High UK Regulatory Relevance: FCA oversight expects senior management accountability (SM&CR), "
            "outcome testing, and clear operational resilience when AI is used in financial services."
        )
    elif "gmail" in text or "privacy" in text or "no internet" in text:
        ssl_risk = (
            "Data Leakage & Confidentiality: Unconfigured cloud consumer AI settings can expose confidential "
            "management accounts, M&A drafts, or customer PII."
        )

    return {
        "strategic": benefit,
        "risk_angle": ssl_risk,
        "action_item": action,
        "cfo_score": cfo_w,
        "audit_score": audit_w,
        "fpa_score": fpa_w,
    }


def analyze_uk_finance_benefit(item: NewsItem) -> tuple[int, str, str, str, str]:
    """
    Evaluate a news item for UK Finance Team priority.
    Returns (priority_score_0_to_100, priority_tier, func_tag, concise_summary, uk_finance_benefit).
    """
    title_l = item.title.lower()
    text = f"{item.title} {item.summary}".lower()

    clean_summary = (item.summary or "").strip()
    if clean_summary and clean_summary.lower().startswith(title_l[:32]):
        clean_summary = ""

    stat_match = re.search(
        r"(\d+%|\£\d+[a-z]*|\$\d+\s*(?:billion|million|bn|m)|\d+×)",
        item.title,
        re.IGNORECASE,
    )
    stat_str = stat_match.group(1) if stat_match else ""

    # 1. Research Papers & Community Discussions stay in the General AI & Research (<70) tier
    if item.category == "Research Papers":
        if "audit" in text or "privacy" in text or "trust" in text:
            return (
                66,
                "General AI & Research",
                "🔬 AI Governance Research",
                clean_summary,
                f"Academic Research ({item.source}): Proposes mathematical methods for auditing AI outputs, confidence scoring, and dataset verification.",
            )
        if "quantization" in text or "diffusion" in text or "speed" in text:
            return (
                60,
                "General AI & Research",
                "🔬 Model Efficiency Paper",
                clean_summary,
                f"Inference Efficiency ({item.source}): Explores quantization and token-generation speed to reduce enterprise LLM compute costs.",
            )
        if "reasoning" in text or "pass@" in text or "self-improvement" in text:
            return (
                62,
                "General AI & Research",
                "🔬 Reasoning & Eval Paper",
                clean_summary,
                f"Reasoning Benchmark ({item.source}): Investigates test-time reasoning quality and automated benchmark evaluation for complex tasks.",
            )
        return (
            56,
            "General AI & Research",
            "🔬 Research Paper",
            clean_summary,
            f"Technical Research ({item.source}): Early-stage academic research into foundation model architecture and alignment.",
        )

    if item.category == "Hacker News & Reddit":
        if "memory" in text or "forget" in text:
            return (
                54,
                "General AI & Research",
                "💬 Practitioner Debate",
                clean_summary,
                f"Architecture Discussion ({item.source}): Examines how enterprise LLMs manage long-term context retention versus selective forgetting.",
            )
        return (
            50,
            "General AI & Research",
            "💬 Community Pulse",
            clean_summary,
            f"Practitioner Discussion ({item.source}): Highlights community engineering insights and practical experimentation.",
        )

    # 2. High-Priority UK Finance, Regulatory, Audit & CFO Rules (85–99)
    if re.search(r"\b(fca|financial conduct authority|bank of england|pra)\b", text):
        if "crypto" in text or "tracing" in text:
            return (
                96,
                "High UK Finance Impact",
                "🏛️ FCA & Compliance",
                clean_summary,
                f"FCA Digital Asset Rules ({item.source}): Flags where automated transaction tracing must be paired with proportionate risk-based compliance controls.",
            )
        return (
            99,
            "High UK Finance Impact",
            "🏛️ FCA & Regulation",
            clean_summary,
            f"FCA AI Governance ({item.source}): Key briefing for UK finance and risk leaders aligning AI model oversight and senior accountability with FCA expectations.",
        )

    if re.search(r"\b(cci|disclosure|consumer duty|frc|icaew|acca|hmrc)\b", text):
        return (
            97,
            "High UK Finance Impact",
            "📊 UK Disclosure & Reporting",
            clean_summary,
            f"UK Regulatory Reporting ({item.source}): Shows how UK finance teams can turn mandatory Consumer Composite Investments (CCI) and disclosure rules into clearer investor communication.",
        )

    if re.search(r"\b(soc|attestation|certification|assurance)\b", text):
        return (
            97,
            "High UK Finance Impact",
            "🛡️ Audit & Assurance",
            clean_summary,
            f"AI Assurance & SOC Controls ({item.source}): Outlines how independent SOC reporting, attestation, and certification build board and auditor confidence in AI systems.",
        )

    if "ethics" in text or "compliance officer" in text:
        return (
            95,
            "High UK Finance Impact",
            "🛡️ Governance & Ethics",
            clean_summary,
            f"2026 Compliance Benchmark ({item.source}): Benchmarks how chief compliance and audit leaders are updating governance controls for generative AI.",
        )

    if re.search(
        r"\b(internal auditor|internal auditors|external audit|kpmg|deloitte|pwc|ey|bdo)\b",
        text,
    ):
        return (
            94,
            "High UK Finance Impact",
            "🛡️ Internal Audit & Big Four",
            clean_summary,
            f"Internal Audit Trend ({item.source}): Tracks how internal audit teams are moving from AI scepticism to active deployment for continuous control testing.",
        )

    if "prove value" in text or "roi" in text or "struggle" in text:
        return (
            96,
            "High UK Finance Impact",
            "📈 CFO ROI & Value",
            clean_summary,
            f"UK CFO Value Benchmark ({item.source}): Addresses the #1 hurdle for UK finance directors—moving AI projects from pilot enthusiasm to measurable P&L and time-saving ROI.",
        )

    if "barclays" in text or "bank tax" in text or "job cuts" in text:
        return (
            93,
            "High UK Finance Impact",
            "🏦 UK Banking & Workforce",
            clean_summary,
            f"UK Banking Sector Analysis ({item.source}): Evaluates how major UK banks are balancing AI-driven cost efficiencies, headcount restructuring, and UK tax policy.",
        )

    if "banking" in text or "uk finance" in text:
        return (
            95,
            "High UK Finance Impact",
            "🏦 UK Banking & Strategy",
            clean_summary,
            f"Sector Leadership View ({item.source}): Highlights why data quality, staff capability, and change management matter as much as model selection in UK financial services.",
        )

    if re.search(
        r"\b(cfo|cfos|finance leader|finance leaders|finance team|finance teams|fp&a|accountant|accounting)\b",
        text,
    ):
        if stat_str:
            return (
                97,
                "High UK Finance Impact",
                "📈 CFO Survey Benchmark",
                clean_summary,
                f"UK & Ireland CFO Pulse ({stat_str} stat via {item.source}): Quantifies boardroom pressure on finance leaders to accelerate AI adoption without compromising financial accuracy.",
            )
        return (
            94,
            "High UK Finance Impact",
            "📈 CFO & Finance Ops",
            clean_summary,
            f"Finance Leadership ({item.source}): Practical perspective on deploying AI across UK forecasting, reconciliation, and month-end reporting.",
        )

    if item.category == "UK Finance & CFO AI":
        return (
            90,
            "High UK Finance Impact",
            "🇬🇧 UK Finance",
            clean_summary,
            f"UK Finance Update ({item.source}): Covers AI governance, productivity, and operational trends across UK financial services.",
        )

    # 3. Finance Ops, Data Governance & Enterprise AI Productivity (70–84)
    if "gmail" in text or "photos" in text or "personal intelligence" in text:
        return (
            84,
            "Finance Ops & Governance",
            "🔒 Workspace Data Privacy",
            clean_summary,
            f"Cloud Privacy Alert ({item.source}): Reminder for finance teams to verify enterprise workspace opt-outs so corporate email and documents are never used for ad targeting or model training.",
        )

    if (
        "no internet" in text
        or "live internet" in text
        or "containment" in text
        or "securing" in text
    ):
        return (
            83,
            "Finance Ops & Governance",
            "🔒 AI Security & Containment",
            clean_summary,
            f"Model Security Posture ({item.source}): Shows how frontier labs are air-gapping training environments and red-teaming models to reduce enterprise security risks.",
        )

    if "scalable ai" in text or "serving harness" in text or "foundation" in text:
        return (
            81,
            "Finance Ops & Productivity",
            "⚙️ Enterprise AI Architecture",
            clean_summary,
            f"Enterprise Deployment ({item.source}): Explains why wrapping AI models in reliable data governance, audit logging, and workflow harnesses matters more than raw model size.",
        )

    if "text messages" in text or "agents" in text:
        return (
            78,
            "Finance Ops & Productivity",
            "🤖 AI Agents & Workflows",
            clean_summary,
            f"Agentic Workflows ({item.source}): Illustrates how lightweight AI agents are moving into everyday communication channels for rapid task execution.",
        )

    if "voice" in text or "local" in text or "macbook" in text:
        return (
            76,
            "Finance Ops & Productivity",
            "💻 Local & On-Device AI",
            clean_summary,
            f"On-Device Privacy ({item.source}): Running capable AI models locally on corporate hardware keeps sensitive financial discussions entirely off third-party clouds.",
        )

    if "storage" in text or "scaling" in text or "cosmos db" in text:
        return (
            75,
            "Finance Ops & Productivity",
            "⚡ Cloud Infrastructure",
            clean_summary,
            f"Infrastructure Reliability ({item.source}): Engineering look at how high-throughput enterprise AI platforms maintain low latency and multi-tenant data isolation at scale.",
        )

    if re.search(
        r"\b(gemini|gpt|claude|grok|frontier model|openai|deepmind|trainium)\b", text
    ):
        if "economy" in text or "$368 billion" in text:
            return (
                72,
                "Finance Ops & Productivity",
                "🌍 Macro AI Economics",
                clean_summary,
                f"Macroeconomic Forecast ({item.source}): Quantifies regional digital-economy growth driven by enterprise AI investment.",
            )
        return (
            74,
            "Finance Ops & Productivity",
            "🧠 Frontier Models",
            clean_summary,
            f"Model Capability & Compute ({item.source}): Tracks new frontier model releases and cloud hardware support that power enterprise analytics and copilot tools.",
        )

    if "graveyard" in text or "shut down" in text:
        return (
            68,
            "General AI & Research",
            "📉 AI Market Consolidation",
            clean_summary,
            f"Vendor Risk Lesson ({item.source}): Useful cautionary tracker when conducting due diligence on startup AI vendors before signing multi-year finance software contracts.",
        )

    if "labels on ai" in text or "advertising act" in text:
        return (
            65,
            "General AI & Research",
            "⚖️ AI Transparency Law",
            clean_summary,
            f"Global AI Regulation ({item.source}): Tracks mandatory disclosure and watermarking laws for AI-generated commercial communications.",
        )

    return (
        48,
        "General AI & Research",
        "🌐 Tech & AI News",
        clean_summary,
        f"General Industry Coverage ({item.source}): Keeps teams aware of broader consumer and technology developments.",
    )


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

        breakdown = build_executive_breakdown(item, score, func_tag, benefit)
        pub_domain = resolve_publisher_domain(item.source, item.url)

        cards.append(
            {
                "id": f"item-{idx}",
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "pub_domain": pub_domain,
                "category": item.category,
                "published_at": item.published_at,
                "score": score,
                "cfo_score": breakdown["cfo_score"],
                "audit_score": breakdown["audit_score"],
                "fpa_score": breakdown["fpa_score"],
                "tier": tier,
                "func_tag": func_tag,
                "summary": summary,
                "benefit": benefit,
                "risk_angle": breakdown["risk_angle"],
                "action_item": breakdown["action_item"],
            }
        )

    cards.sort(key=lambda c: int(c["score"]), reverse=True)
    return cards


def build_dashboard_html(cards: list[dict[str, object]], date_str: str) -> str:
    """Render a modern, mobile-first, animated UK Finance & AI Intelligence Dashboard."""
    total = max(len(cards), 1)
    high_impact_count = sum(1 for c in cards if int(c["score"]) >= 85)
    ops_count = sum(1 for c in cards if 70 <= int(c["score"]) < 85)
    general_count = sum(1 for c in cards if int(c["score"]) < 70)

    high_pct = round((high_impact_count / total) * 100, 1)
    ops_pct = round((ops_count / total) * 100, 1)
    gen_pct = max(0.0, round(100.0 - high_pct - ops_pct, 1))

    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#070b14" />
  <meta name="description" content="Daily AI News & UK CFO Intelligence Dashboard — ranked by practical impact for UK Finance, Accounting, Audit & FP&A teams." />
  <title>UK Finance & AI Daily Intelligence — {html.escape(date_str)}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --font-sans: "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --bg: #070b14;
      --bg-mesh-1: rgba(59, 130, 246, 0.11);
      --bg-mesh-2: rgba(245, 158, 11, 0.08);
      --surface: rgba(17, 24, 39, 0.86);
      --surface-solid: #111827;
      --surface-elevated: #192338;
      --surface-hover: #1e293b;
      --glass-bg: rgba(15, 23, 42, 0.82);
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
      /* Motion system: one easing family, three durations */
      --spring: cubic-bezier(0.16, 1, 0.3, 1);
      --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
      --drawer-ease: cubic-bezier(0.32, 0.72, 0, 1);
      --dur-fast: 160ms;
      --dur: 260ms;
      --dur-slow: 520ms;
    }}
    [data-theme="light"] {{
      --bg: #f4f7fb;
      --bg-mesh-1: rgba(37, 99, 235, 0.07);
      --bg-mesh-2: rgba(245, 158, 11, 0.07);
      --surface: rgba(255, 255, 255, 0.95);
      --surface-solid: #ffffff;
      --surface-elevated: #f1f5f9;
      --surface-hover: #f8fafc;
      --glass-bg: rgba(255, 255, 255, 0.88);
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

    /* Strict Font Consistency Across 100% of Elements */
    *, *::before, *::after {{
      box-sizing: border-box;
      font-family: var(--font-sans);
      font-variant-numeric: tabular-nums;
      -webkit-tap-highlight-color: transparent;
    }}
    button, input, select, textarea, table, th, td, code, kbd, span, div, p, a, h1, h2, h3, h4 {{
      font-family: var(--font-sans);
    }}

    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
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

    #scrollProgress {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 2px;
      transform-origin: 0 50%;
      transform: scaleX(0);
      background: linear-gradient(90deg, #f59e0b 0%, #3b82f6 55%, #10b981 100%);
      z-index: 999;
      will-change: transform;
    }}

    /* Accessible, understated focus rings */
    :focus-visible {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
      border-radius: 8px;
    }}
    :focus:not(:focus-visible) {{ outline: none; }}

    /* Smooth theme cross-fade (fallback when View Transitions unsupported) */
    html.theme-anim, html.theme-anim *, html.theme-anim *::before, html.theme-anim *::after {{
      transition: background-color var(--dur) var(--ease-in-out), border-color var(--dur) var(--ease-in-out), color var(--dur) var(--ease-in-out) !important;
    }}

    /* Content swap fade used when filters, lenses, or views change */
    .swap-target {{
      transition: opacity var(--dur-fast) var(--ease-in-out), transform var(--dur-fast) var(--ease-in-out);
    }}
    .swap-target.is-swapping {{
      opacity: 0;
      transform: translateY(6px);
    }}

    .svg-icon {{
      width: 16px;
      height: 16px;
      flex-shrink: 0;
      stroke: currentColor;
      fill: none;
      stroke-width: 1.8;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    .container {{
      max-width: 1260px;
      margin: 0 auto;
      padding: 28px 20px 96px;
    }}

    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-end;
      gap: 20px;
      padding-bottom: 22px;
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
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
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
      font-size: 11.5px;
      font-weight: 600;
      color: var(--muted);
      padding: 4px 11px;
      border-radius: 999px;
      border: 1px solid var(--border);
      background: var(--surface);
    }}
    h1 {{
      margin: 0;
      font-size: clamp(23px, 3.2vw, 34px);
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.18;
    }}
    .subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: clamp(13.5px, 1.5vw, 15px);
      font-weight: 400;
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
      padding: 10px 15px;
      min-height: 42px;
      border-radius: 11px;
      font-size: 13px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      transition: transform var(--dur) var(--spring), border-color var(--dur-fast) ease, background-color var(--dur-fast) ease, box-shadow var(--dur) var(--spring);
      user-select: none;
      text-decoration: none;
    }}
    .btn:hover {{
      transform: translateY(-1px);
      border-color: color-mix(in srgb, var(--accent) 55%, var(--border));
      background: var(--surface-hover);
      box-shadow: 0 6px 16px -8px var(--accent-glow);
    }}
    .btn:active {{
      transform: translateY(0) scale(0.98);
      transition-duration: 80ms;
    }}
    .btn-icon-only {{
      padding: 10px 12px;
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

    /* UK Finance Role Lens Switcher */
    .lens-bar {{
      margin: 20px 0 18px;
      padding: 12px 16px;
      border-radius: 14px;
      background: var(--surface);
      border: 1px solid var(--border);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      animation: fadeSlideUp 0.6s 0.05s var(--spring) both;
    }}
    .lens-label {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
      font-weight: 700;
      color: var(--text-secondary);
    }}
    .lens-pills {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
    }}
    .lens-btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--muted);
      padding: 7px 13px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      transition: color var(--dur-fast) ease, background-color var(--dur) var(--spring), border-color var(--dur) var(--spring), transform var(--dur) var(--spring);
    }}
    .lens-btn:active {{ transform: scale(0.97); }}
    .lens-btn:hover {{
      color: var(--text);
      border-color: var(--accent);
    }}
    .lens-btn.active {{
      background: var(--gold-bg);
      border-color: var(--gold-border);
      color: var(--gold-text);
      font-weight: 700;
    }}

    /* 60-Second CFO Hero Brief */
    .hero-section {{
      margin: 0 0 22px;
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
      font-size: clamp(13.5px, 1.8vw, 15.5px);
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
      cursor: pointer;
      transition: transform var(--dur-slow) var(--spring), border-color var(--dur) ease, box-shadow var(--dur-slow) var(--spring);
    }}
    .hero-card:hover {{
      border-color: var(--gold-border);
      transform: translateY(-2px);
      box-shadow: 0 16px 32px -16px rgba(245, 158, 11, 0.22);
    }}
    .rank-pill {{
      font-size: 10.5px;
      font-weight: 800;
      letter-spacing: 0.04em;
      padding: 3px 9px;
      border-radius: 6px;
      background: var(--gold-bg);
      color: var(--gold-text);
      border: 1px solid var(--gold-border);
    }}

    /* KPI Strip & Signal Mix Bar */
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 14px;
      margin-bottom: 14px;
      animation: fadeSlideUp 0.65s 0.14s var(--spring) both;
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
      transition: transform var(--dur-slow) var(--spring), border-color var(--dur) ease, box-shadow var(--dur-slow) var(--spring);
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
      transform: translateY(-2px);
      border-color: var(--accent);
      box-shadow: var(--card-shadow);
    }}
    .kpi-card:hover::after {{ opacity: 1; }}
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

    /* Segmented Signal Mix Bar */
    .signal-mix-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 12px 16px;
      margin-bottom: 22px;
      display: flex;
      flex-direction: column;
      gap: 8px;
      animation: fadeSlideUp 0.65s 0.18s var(--spring) both;
    }}
    .signal-mix-top {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      font-size: 11.5px;
      font-weight: 600;
      color: var(--muted);
    }}
    .signal-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 14px;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .legend-dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
    }}
    .signal-track {{
      width: 100%;
      height: 7px;
      border-radius: 999px;
      overflow: hidden;
      display: flex;
      background: var(--border);
      gap: 2px;
    }}
    .signal-seg {{
      height: 100%;
      transform-origin: 0 50%;
      animation: segGrow 1s var(--spring) backwards;
    }}
    .signal-seg:nth-child(2) {{ animation-delay: 90ms; }}
    .signal-seg:nth-child(3) {{ animation-delay: 180ms; }}

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
    }}
    .tabs {{
      position: relative;
      display: flex;
      align-items: center;
      gap: 6px;
      overflow-x: auto;
      max-width: 100%;
      scrollbar-width: none;
      -ms-overflow-style: none;
      padding-bottom: 2px;
    }}
    .tabs::-webkit-scrollbar {{ display: none; }}
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
      position: relative;
      z-index: 1;
      transition: color var(--dur) var(--spring), background-color var(--dur-fast) ease;
    }}
    .tab:hover {{
      color: var(--text);
      background: var(--surface-hover);
    }}
    .tab.active, .tab.active:hover {{
      background: transparent;
      color: #ffffff;
    }}
    /* Sliding active indicator shared by tabs and view toggle */
    .seg-indicator {{
      position: absolute;
      top: 0;
      left: 0;
      height: 0;
      width: 0;
      z-index: 0;
      border-radius: 9px;
      background: var(--accent);
      box-shadow: 0 4px 14px -4px var(--accent-glow);
      transition: transform var(--dur-slow) var(--spring), width var(--dur-slow) var(--spring), height var(--dur-slow) var(--spring), opacity var(--dur) ease;
      pointer-events: none;
      opacity: 0;
    }}
    .seg-indicator.ready {{ opacity: 1; }}
    .seg-indicator.no-anim {{ transition: none; }}
    .view-toggle .seg-indicator {{
      background: var(--surface-elevated);
      box-shadow: none;
      border-radius: 7px;
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
      font-weight: 500;
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
      font-size: 10.5px;
      font-weight: 700;
      color: var(--muted);
      border: 1px solid var(--border);
      padding: 1px 6px;
      border-radius: 4px;
      pointer-events: none;
    }}
    .view-toggle {{
      position: relative;
      display: inline-flex;
      padding: 2px;
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
      min-height: 32px;
      font-size: 12px;
      font-weight: 600;
      position: relative;
      z-index: 1;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 7px;
      transition: color var(--dur) var(--spring);
    }}
    .view-btn:hover {{ color: var(--text); }}
    .view-btn.active {{
      color: var(--text);
    }}
    .view-btn .svg-icon {{ width: 14px; height: 14px; }}

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
      cursor: pointer;
      box-shadow: var(--card-shadow);
      /* Hover transitions only — entry uses a separate animation so hover is never delayed */
      transition:
        transform var(--dur-slow) var(--spring),
        border-color var(--dur) ease,
        box-shadow var(--dur-slow) var(--spring);
    }}
    .news-card.pre-reveal {{
      opacity: 0;
    }}
    .news-card.in-view {{
      animation: cardIn 0.7s var(--spring) backwards;
      animation-delay: var(--reveal-delay, 0ms);
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
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--accent) 50%, var(--border));
      box-shadow: 0 20px 40px -20px rgba(0, 0, 0, 0.55), 0 0 0 1px var(--accent-glow);
    }}
    .news-card:active {{
      transform: translateY(0) scale(0.995);
      transition-duration: 120ms;
    }}
    .news-card:hover::before {{ opacity: 1; }}
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
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .pub-favicon {{
      width: 14px;
      height: 14px;
      border-radius: 3px;
      object-fit: contain;
      flex-shrink: 0;
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
      transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease, transform var(--dur) var(--spring);
    }}
    .icon-btn:hover {{
      background: var(--surface-elevated);
      color: var(--text);
    }}
    .icon-btn:active {{
      transform: scale(0.9);
    }}
    .icon-btn.saved {{
      color: var(--gold-text);
    }}
    .icon-btn.saved .svg-icon {{
      fill: currentColor;
    }}
    .icon-btn.just-saved .svg-icon {{
      animation: savePop 0.45s var(--spring);
    }}
    .card-title {{
      margin: 0 0 10px;
      font-size: 16.5px;
      font-weight: 700;
      line-height: 1.4;
      letter-spacing: -0.01em;
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
      font-size: 11px;
      font-weight: 700;
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
      font-weight: 500;
      color: var(--muted);
      padding-top: 12px;
      border-top: 1px solid var(--border-subtle);
    }}
    .footer-links {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
    }}
    .quick-brief-btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--surface-elevated);
      color: var(--text-secondary);
      font-size: 11.5px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 7px;
      transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease, background-color var(--dur-fast) ease;
    }}
    .quick-brief-btn:hover {{
      border-color: var(--accent);
      color: var(--text);
    }}
    .read-link {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .read-link span.arrow {{
      display: inline-block;
      transition: transform var(--dur) var(--spring);
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
      font-weight: 700;
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
      transition: background-color var(--dur-fast) ease;
    }}
    .compact-table tr {{ cursor: pointer; }}
    .compact-table tbody tr.row-in {{
      animation: rowIn 0.45s var(--spring) backwards;
      animation-delay: calc(var(--i, 0) * 18ms);
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

    /* Slide-Over Executive Quick-Brief Drawer */
    .drawer-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(3, 7, 18, 0.55);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 200;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--dur-slow) var(--drawer-ease);
    }}
    body.drawer-open {{
      overflow: hidden;
    }}
    .drawer-backdrop.open {{
      opacity: 1;
      pointer-events: auto;
    }}
    .drawer-panel {{
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(520px, 100vw);
      background: var(--surface-solid);
      border-left: 1px solid var(--border);
      box-shadow: -24px 0 60px rgba(0, 0, 0, 0.45);
      z-index: 210;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transform: translateX(104%);
      visibility: hidden;
      transition: transform 0.5s var(--drawer-ease), visibility 0s linear 0.5s;
      overflow-y: auto;
      overscroll-behavior: contain;
    }}
    .drawer-panel.open {{
      transform: translateX(0);
      visibility: visible;
      transition: transform 0.5s var(--drawer-ease), visibility 0s;
    }}
    .drawer-body {{
      transition: opacity var(--dur-fast) var(--ease-in-out), transform var(--dur-fast) var(--ease-in-out);
    }}
    .drawer-body.swap-next {{ opacity: 0; transform: translateX(-10px); }}
    .drawer-body.swap-prev {{ opacity: 0; transform: translateX(10px); }}
    .drawer-panel.open .drawer-body > * {{
      animation: fadeSlideUp 0.5s var(--spring) backwards;
    }}
    .drawer-panel.open .drawer-body > *:nth-child(2) {{ animation-delay: 40ms; }}
    .drawer-panel.open .drawer-body > *:nth-child(3) {{ animation-delay: 80ms; }}
    .drawer-panel.open .drawer-body > *:nth-child(4) {{ animation-delay: 120ms; }}
    .drawer-panel.open .drawer-body > *:nth-child(5) {{ animation-delay: 160ms; }}
    .drawer-panel.open .drawer-body > *:nth-child(6) {{ animation-delay: 200ms; }}
    .drawer-panel.open .drawer-body > *:nth-child(n+7) {{ animation-delay: 240ms; }}
    .drawer-header {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      background: var(--surface-solid);
      z-index: 5;
    }}
    .drawer-body {{
      padding: 24px;
      flex: 1;
    }}
    .drawer-progress {{
      font-size: 11.5px;
      font-weight: 600;
      color: var(--muted);
      letter-spacing: 0.02em;
    }}
    .drawer-title {{
      font-size: 20px;
      font-weight: 800;
      line-height: 1.35;
      margin: 14px 0 12px;
      letter-spacing: -0.02em;
    }}
    .drawer-meta {{
      font-size: 12.5px;
      color: var(--muted);
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-subtle);
    }}
    .drawer-section {{
      background: var(--surface-elevated);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 15px 16px;
      margin-bottom: 14px;
    }}
    .drawer-sec-title {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .drawer-sec-text {{
      font-size: 13.5px;
      color: var(--text-secondary);
      line-height: 1.55;
      margin: 0;
    }}
    .drawer-footer {{
      padding: 16px 24px;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      position: sticky;
      bottom: 0;
      background: var(--surface-solid);
    }}
    .drawer-nav {{
      display: inline-flex;
      gap: 6px;
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
      font-weight: 700;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 8px 25px rgba(0, 0, 0, 0.35);
      opacity: 0;
      transform: translateY(14px) scale(0.92);
      pointer-events: none;
      transition: opacity var(--dur) ease, transform var(--dur-slow) var(--spring), border-color var(--dur-fast) ease;
      z-index: 90;
    }}
    #backToTop.visible {{
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: auto;
    }}
    #backToTop:hover {{
      border-color: var(--accent);
      transform: translateY(-2px);
    }}

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
      transform: translateY(12px) scale(0.97);
      pointer-events: none;
      transition: opacity var(--dur) ease, transform var(--dur-slow) var(--spring);
      z-index: 250;
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
    @keyframes savePop {{
      0% {{ transform: scale(1); }}
      40% {{ transform: scale(1.22); }}
      100% {{ transform: scale(1); }}
    }}
    @keyframes cardIn {{
      from {{ opacity: 0; transform: translateY(16px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes rowIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes segGrow {{
      from {{ transform: scaleX(0); }}
      to {{ transform: scaleX(1); }}
    }}

    /* View Transitions API: soft cross-fade for theme switching */
    ::view-transition-old(root), ::view-transition-new(root) {{
      animation-duration: 320ms;
      animation-timing-function: var(--ease-in-out);
    }}

    @media (max-width: 960px) {{
      .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
    }}
    @media (max-width: 680px) {{
      .container {{ padding: 18px 14px 84px; }}
      header {{ align-items: stretch; gap: 14px; }}
      .header-actions {{ width: 100%; }}
      .header-actions .btn {{ flex: 1; padding: 9px 10px; font-size: 12px; }}
      .hero-section {{ padding: 16px; }}
      .hero-grid {{ grid-template-columns: 1fr; }}
      .kpi-grid {{ grid-template-columns: repeat(2, 1fr); gap: 10px; }}
      .kpi-card {{ padding: 13px 14px; }}
      .controls {{ padding: 10px 12px; top: 6px; }}
      .right-controls {{ width: 100%; min-width: 100%; }}
      .search-wrap {{ max-width: none; }}
      .kbd-hint {{ display: none; }}
      .cards-grid {{ grid-template-columns: 1fr; gap: 14px; }}
      .news-card {{ padding: 18px; }}
      .compact-hide-mobile {{ display: none; }}
      #toast {{ left: 14px; right: 14px; bottom: 16px; justify-content: center; }}
    }}

    /* Boardroom A4 Print / PDF Stylesheet */
    @media print {{
      body {{
        background: #ffffff !important;
        color: #0f172a !important;
        font-size: 11pt;
      }}
      #scrollProgress, .header-actions, .lens-bar, .controls, .card-actions,
      .quick-brief-btn, #backToTop, #toast, .drawer-backdrop, .drawer-panel {{
        display: none !important;
      }}
      .container {{
        max-width: 100% !important;
        padding: 0 !important;
      }}
      .hero-section, .news-card, .kpi-card, .signal-mix-card {{
        background: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        box-shadow: none !important;
        opacity: 1 !important;
        transform: none !important;
        break-inside: avoid;
      }}
      .cards-grid {{
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 12px !important;
      }}
      .benefit-box {{
        background: #f8fafc !important;
        color: #1e293b !important;
        border-left: 3px solid #0f172a !important;
      }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-delay: 0ms !important;
        transition-duration: 0.01ms !important;
      }}
      html {{ scroll-behavior: auto; }}
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
        <button class="btn btn-primary" onclick="copyTeamBriefing()">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/></svg>
          Copy Team Summary
        </button>
        <button class="btn" onclick="window.print()" title="Print or save as Boardroom PDF">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/></svg>
          Export PDF
        </button>
        <button class="btn btn-icon-only" onclick="toggleTheme()" aria-label="Toggle colour theme" title="Toggle light / dark theme">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        </button>
      </div>
    </header>

    <!-- UK Finance Role Lens Switcher -->
    <div class="lens-bar">
      <div class="lens-label">👔 Prioritise Feed for UK Finance Role:</div>
      <div class="lens-pills" role="group" aria-label="Finance Role Lens">
        <button class="lens-btn active" data-lens="default" onclick="setRoleLens('default', this)">🎯 All Finance Roles</button>
        <button class="lens-btn" data-lens="cfo" onclick="setRoleLens('cfo', this)">👔 CFO & Strategy</button>
        <button class="lens-btn" data-lens="audit" onclick="setRoleLens('audit', this)">🛡️ Audit, Risk & FCA</button>
        <button class="lens-btn" data-lens="fpa" onclick="setRoleLens('fpa', this)">📊 FP&A & Systems</button>
      </div>
    </div>

    <!-- 60-Second CFO Hero Brief -->
    <section class="hero-section swap-target" id="heroSection">
      <div class="hero-header">
        <h2 class="hero-title" id="heroTitle">⚡ 60-Second UK Finance Morning Brief — Top 3 Today</h2>
        <span class="hero-sub">Click any card to open the Executive Quick-Brief Drawer</span>
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
        <div class="kpi-sub">Deduplicated across 11 feeds</div>
      </div>
    </div>

    <!-- Segmented Signal Mix Visual Bar -->
    <div class="signal-mix-card">
      <div class="signal-mix-top">
        <span>TODAY'S INTELLIGENCE SIGNAL MIX</span>
        <div class="signal-legend">
          <span class="legend-item"><span class="legend-dot" style="background:var(--gold-text);"></span> UK Finance & FCA ({high_pct}%)</span>
          <span class="legend-item"><span class="legend-dot" style="background:var(--emerald-text);"></span> Ops & Data Security ({ops_pct}%)</span>
          <span class="legend-item"><span class="legend-dot" style="background:var(--blue-text);"></span> Global AI & Research ({gen_pct}%)</span>
        </div>
      </div>
      <div class="signal-track">
        <div class="signal-seg" style="width:{high_pct}%;background:var(--gold-text);"></div>
        <div class="signal-seg" style="width:{ops_pct}%;background:var(--emerald-text);"></div>
        <div class="signal-seg" style="width:{gen_pct}%;background:var(--blue-text);"></div>
      </div>
    </div>

    <!-- Glassmorphic Sticky Filter & View Bar -->
    <div class="controls">
      <div class="tabs" role="tablist" id="filterTabs">
        <span class="seg-indicator" aria-hidden="true"></span>
        <button class="tab active" data-filter="all" onclick="setFilter('all', this)">All Prioritised ({len(cards)})</button>
        <button class="tab" data-filter="high" onclick="setFilter('high', this)">🇬🇧💷 UK Finance & CFO ({high_impact_count})</button>
        <button class="tab" data-filter="ops" onclick="setFilter('ops', this)">⚡ Ops & Security ({ops_count})</button>
        <button class="tab" data-filter="general" onclick="setFilter('general', this)">🌐 General AI ({general_count})</button>
        <button class="tab" data-filter="saved" id="savedTabBtn" onclick="setFilter('saved', this)">⭐ Saved (0)</button>
      </div>
      <div class="right-controls">
        <div class="search-wrap">
          <input type="search" id="searchInput" class="search-input" placeholder="Search FCA, Deloitte, audit, OpenAI..." oninput="onSearchInput()" />
          <span class="kbd-hint">/</span>
        </div>
        <div class="view-toggle" role="group" aria-label="View mode" id="viewToggle">
          <span class="seg-indicator" aria-hidden="true"></span>
          <button class="view-btn active" id="viewCardsBtn" onclick="setViewMode('cards')">
            <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
            Cards
          </button>
          <button class="view-btn" id="viewTableBtn" onclick="setViewMode('table')">
            <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
            Compact
          </button>
        </div>
      </div>
    </div>

    <div id="mainContainer" class="swap-target"></div>
  </div>

  <!-- Slide-Over Executive Quick-Brief Drawer -->
  <div class="drawer-backdrop" id="drawerBackdrop" onclick="closeDrawer()"></div>
  <aside class="drawer-panel" id="drawerPanel" aria-label="Executive Quick-Brief Drawer">
    <div class="drawer-header">
      <span class="brand-badge" id="drawerBadge">⚡ Executive Quick-Brief</span>
      <button class="icon-btn" onclick="closeDrawer()" aria-label="Close drawer" title="Close (Esc)">
        <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
      </button>
    </div>
    <div class="drawer-body" id="drawerBody"></div>
    <div class="drawer-footer">
      <div class="drawer-nav">
        <button class="btn" onclick="stepDrawer(-1)" title="Previous story (←)" aria-label="Previous story">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
        <button class="btn" onclick="stepDrawer(1)" title="Next story (→)" aria-label="Next story">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>
        </button>
        <span class="drawer-progress" id="drawerProgress" style="align-self:center;margin-left:6px;"></span>
      </div>
      <a class="btn btn-primary" id="drawerReadLink" href="#" target="_blank" rel="noopener noreferrer">
        Open article
        <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 17L17 7M8 7h9v9"/></svg>
      </a>
    </div>
  </aside>

  <button id="backToTop" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})" aria-label="Back to top" title="Back to top">
    <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 15l-6-6-6 6"/></svg>
  </button>
  <div id="toast" role="status" aria-live="polite">✓ Copied Top 5 UK Finance Briefing!</div>

  <script>
    const ITEMS = {cards_json};
    const ITEM_MAP = new Map(ITEMS.map(it => [it.id, it]));
    let currentFilter = 'all';
    let currentLens = 'default';
    let currentView = localStorage.getItem('ai-news-view') || 'cards';
    let savedUrls = new Set(JSON.parse(localStorage.getItem('ai-news-saved') || '[]'));
    let activeDrawerId = null;
    let currentDisplayedIds = [];
    let revealObserver = null;
    let lastFocusedEl = null;
    let searchTimer = null;
    const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const ICON_LINK = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>';
    const ICON_BOOKMARK = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>';

    /* Slide the shared pill indicator under the active tab / view button */
    function moveIndicator(container, animate = true) {{
      if (!container) return;
      const ind = container.querySelector('.seg-indicator');
      const active = container.querySelector('.active');
      if (!ind || !active) return;
      ind.classList.toggle('no-anim', !animate);
      ind.style.width = `${{active.offsetWidth}}px`;
      ind.style.height = `${{active.offsetHeight}}px`;
      ind.style.transform = `translate(${{active.offsetLeft}}px, ${{active.offsetTop}}px)`;
      ind.classList.add('ready');
    }}
    function moveAllIndicators(animate = true) {{
      moveIndicator(document.getElementById('filterTabs'), animate);
      moveIndicator(document.getElementById('viewToggle'), animate);
    }}

    /* Fade content out, swap it, fade it back in — avoids hard jumps on filter changes */
    function swapContent(renderFn) {{
      const targets = document.querySelectorAll('.swap-target');
      if (REDUCED_MOTION) {{ renderFn(); return; }}
      targets.forEach(t => t.classList.add('is-swapping'));
      clearTimeout(window._swapTimer);
      window._swapTimer = setTimeout(() => {{
        renderFn();
        requestAnimationFrame(() => targets.forEach(t => t.classList.remove('is-swapping')));
      }}, 150);
    }}

    function onSearchInput() {{
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => renderMain({{ animate: false }}), 120);
    }}

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

    function getActiveScore(item) {{
      if (currentLens === 'cfo') return item.cfo_score || item.score;
      if (currentLens === 'audit') return item.audit_score || item.score;
      if (currentLens === 'fpa') return item.fpa_score || item.score;
      return item.score;
    }}

    function getSortedItems() {{
      return [...ITEMS].sort((a, b) => getActiveScore(b) - getActiveScore(a));
    }}

    function faviconUrl(domain) {{
      return `https://www.google.com/s2/favicons?domain=${{encodeURIComponent(domain || 'ukfinance.org.uk')}}&sz=32`;
    }}

    function formatRelativeTime(pubStr) {{
      if (!pubStr || pubStr === 'Recent') return 'Recent';
      const iso = pubStr.includes(' UTC')
        ? pubStr.replace(' UTC', ':00Z').replace(' ', 'T')
        : pubStr + 'T00:00:00Z';
      const dt = new Date(iso);
      if (isNaN(dt.getTime())) return pubStr;
      const diffMs = Math.max(0, Date.now() - dt.getTime());
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
      moveIndicator(document.getElementById('filterTabs'));
    }}

    function toggleSaveById(id, ev) {{
      if (ev) ev.stopPropagation();
      const item = ITEM_MAP.get(id);
      if (!item) return;
      const url = item.url;
      const nowSaved = !savedUrls.has(url);
      if (nowSaved) {{
        savedUrls.add(url);
        showToast('Saved to your reading list');
      }} else {{
        savedUrls.delete(url);
        showToast('Removed from saved stories');
      }}
      localStorage.setItem('ai-news-saved', JSON.stringify(Array.from(savedUrls)));
      updateSavedTabCount();

      if (currentFilter === 'saved') {{
        swapContent(() => {{ renderHero(); renderMain(); }});
        return;
      }}
      /* Update in place so the page never flickers or re-animates */
      document.querySelectorAll(`[data-save-id="${{id}}"]`).forEach(b => {{
        b.classList.toggle('saved', nowSaved);
        b.setAttribute('aria-pressed', String(nowSaved));
        b.classList.remove('just-saved');
        if (nowSaved) {{ void b.offsetWidth; b.classList.add('just-saved'); }}
      }});
    }}

    function shareById(id, ev) {{
      if (ev) ev.stopPropagation();
      const item = ITEM_MAP.get(id);
      if (!item) return;
      if (navigator.share) {{
        navigator.share({{ title: item.title, url: item.url }}).catch(() => {{}});
      }} else {{
        navigator.clipboard.writeText(`${{item.title}} — ${{item.url}}`).then(() => {{
          showToast('Link copied to clipboard');
        }});
      }}
    }}

    function openDrawer(id, ev, direction) {{
      if (ev && (ev.target.closest('a') || ev.target.closest('button.icon-btn'))) return;
      const item = ITEM_MAP.get(id);
      if (!item) return;
      const panel = document.getElementById('drawerPanel');
      const body = document.getElementById('drawerBody');
      const alreadyOpen = panel.classList.contains('open');
      if (!alreadyOpen) lastFocusedEl = document.activeElement;
      activeDrawerId = id;

      const paint = () => {{
        fillDrawer(item);
        body.classList.remove('swap-next', 'swap-prev');
        panel.scrollTop = 0;
      }};

      if (alreadyOpen && direction && !REDUCED_MOTION) {{
        body.classList.add(direction > 0 ? 'swap-next' : 'swap-prev');
        setTimeout(paint, 150);
      }} else {{
        paint();
      }}

      document.body.classList.add('drawer-open');
      document.getElementById('drawerBackdrop').classList.add('open');
      panel.classList.add('open');
      if (!alreadyOpen) setTimeout(() => {{
        const closeBtn = panel.querySelector('.drawer-header .icon-btn');
        if (closeBtn) closeBtn.focus({{ preventScroll: true }});
      }}, 60);
    }}

    function fillDrawer(item) {{
      const effScore = getActiveScore(item);
      document.getElementById('drawerBadge').textContent = `${{item.func_tag}} · Priority ${{effScore}}/100`;
      document.getElementById('drawerReadLink').href = item.url;
      const pos = currentDisplayedIds.indexOf(item.id);
      document.getElementById('drawerProgress').textContent =
        pos > -1 ? `${{pos + 1}} of ${{currentDisplayedIds.length}}` : '';

      const summaryBlock = item.summary
        ? `<div class="drawer-section"><div class="drawer-sec-title" style="color:var(--blue-text);">📰 Article Summary</div><p class="drawer-sec-text">${{escapeHtml(item.summary)}}</p></div>`
        : '';

      document.getElementById('drawerBody').innerHTML = `
        <div class="tag-group">
          <span class="pub-pill">
            <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
            ${{escapeHtml(item.source)}}
          </span>
          <span class="pub-pill">${{escapeHtml(item.category)}}</span>
        </div>
        <h2 class="drawer-title">${{escapeHtml(item.title)}}</h2>
        <div class="drawer-meta">Published ${{escapeHtml(formatRelativeTime(item.published_at))}} (${{escapeHtml(item.published_at)}})</div>
        ${{summaryBlock}}
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--gold-text);">🎯 UK CFO & Strategic Impact</div>
          <p class="drawer-sec-text">${{escapeHtml(item.benefit)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--emerald-text);">🛡️ Audit, Risk & FCA Governance Angle</div>
          <p class="drawer-sec-text">${{escapeHtml(item.risk_angle)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--blue-text);">✅ Recommended Action for UK Finance Team</div>
          <p class="drawer-sec-text">${{escapeHtml(item.action_item)}}</p>
        </div>
      `;
    }}

    function closeDrawer() {{
      activeDrawerId = null;
      document.body.classList.remove('drawer-open');
      document.getElementById('drawerBackdrop').classList.remove('open');
      document.getElementById('drawerPanel').classList.remove('open');
      if (lastFocusedEl && document.contains(lastFocusedEl)) {{
        lastFocusedEl.focus({{ preventScroll: true }});
      }}
    }}

    function stepDrawer(delta) {{
      if (!activeDrawerId || !currentDisplayedIds.length) return;
      const idx = currentDisplayedIds.indexOf(activeDrawerId);
      if (idx === -1) return;
      const nextIdx = (idx + delta + currentDisplayedIds.length) % currentDisplayedIds.length;
      openDrawer(currentDisplayedIds[nextIdx], null, delta);
    }}

    function setRoleLens(lens, btn) {{
      if (lens === currentLens) return;
      currentLens = lens;
      document.querySelectorAll('.lens-btn').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      const labels = {{
        default: '⚡ 60-Second UK Finance Morning Brief — Top 3 Today',
        cfo: '👔 CFO & Strategy Lens — Top 3 Strategic Priorities',
        audit: '🛡️ Audit, Risk & FCA Lens — Top 3 Governance Priorities',
        fpa: '📊 FP&A & Systems Lens — Top 3 Automation & Model Priorities'
      }};
      swapContent(() => {{
        document.getElementById('heroTitle').textContent = labels[lens] || labels.default;
        renderHero();
        renderMain();
      }});
    }}

    function setupScrollReveal() {{
      if (revealObserver) revealObserver.disconnect();
      const cards = document.querySelectorAll('.news-card.pre-reveal');
      if (!('IntersectionObserver' in window) || REDUCED_MOTION) {{
        cards.forEach(c => c.classList.remove('pre-reveal'));
        return;
      }}
      revealObserver = new IntersectionObserver((entries) => {{
        const visible = entries.filter(e => e.isIntersecting);
        visible.forEach((entry, i) => {{
          const el = entry.target;
          el.style.setProperty('--reveal-delay', `${{Math.min(i, 5) * 55}}ms`);
          el.classList.remove('pre-reveal');
          el.classList.add('in-view');
          el.addEventListener('animationend', () => el.classList.remove('in-view'), {{ once: true }});
          revealObserver.unobserve(el);
        }});
      }}, {{ threshold: 0.06, rootMargin: '0px 0px -24px 0px' }});

      cards.forEach(card => revealObserver.observe(card));
    }}

    function attachSpotlightTracking() {{
      document.querySelectorAll('.news-card, .kpi-card').forEach(card => {{
        if (card.dataset.spot) return;
        card.dataset.spot = '1';
        let raf = null;
        card.addEventListener('mousemove', (e) => {{
          if (raf) return;
          raf = requestAnimationFrame(() => {{
            const rect = card.getBoundingClientRect();
            card.style.setProperty('--mouse-x', `${{e.clientX - rect.left}}px`);
            card.style.setProperty('--mouse-y', `${{e.clientY - rect.top}}px`);
            raf = null;
          }});
        }}, {{ passive: true }});
      }});
    }}

    function renderHero() {{
      const sorted = getSortedItems();
      const top3 = sorted.slice(0, 3);
      const heroSec = document.getElementById('heroSection');
      const heroGrid = document.getElementById('heroGrid');
      if (!top3.length || currentFilter !== 'all') {{
        heroSec.style.display = 'none';
        return;
      }}
      heroSec.style.display = 'block';

      heroGrid.innerHTML = top3.map((item, idx) => {{
        const isSaved = savedUrls.has(item.url);
        const effScore = getActiveScore(item);
        return `
          <article class="hero-card" onclick="openDrawer('${{item.id}}', event)">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="rank-pill">#${{idx + 1}} · ${{effScore}}/100</span>
                  <span class="pub-pill">
                    <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                    ${{escapeHtml(item.source)}}
                  </span>
                </div>
                <div class="card-actions">
                  <button class="icon-btn" title="Copy story link" aria-label="Copy story link" onclick="shareById('${{item.id}}', event)">${{ICON_LINK}}</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" title="Save for later" aria-label="Save for later" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                </div>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              <p class="card-summary" style="margin-bottom: 12px;">${{escapeHtml(item.benefit)}}</p>
            </div>
            <div class="card-footer">
              <span>${{escapeHtml(item.func_tag)}} · <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span></span>
              <span class="read-link">Quick Brief <span class="arrow">→</span></span>
            </div>
          </article>
        `;
      }}).join('');
    }}

    function setFilter(filter, btn) {{
      if (filter === currentFilter) return;
      currentFilter = filter;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      if (btn) {{
        btn.classList.add('active');
        btn.scrollIntoView({{ behavior: 'smooth', inline: 'center', block: 'nearest' }});
      }}
      moveIndicator(document.getElementById('filterTabs'));
      document.querySelectorAll('.kpi-card').forEach(k => {{
        k.classList.toggle('active-kpi', k.getAttribute('data-kpi') === filter);
      }});
      swapContent(() => {{ renderHero(); renderMain(); }});
    }}

    function setFilterByName(filter) {{
      const btn = document.querySelector(`.tab[data-filter="${{filter}}"]`);
      setFilter(filter, btn);
    }}

    function setViewMode(mode) {{
      if (mode === currentView) return;
      currentView = mode;
      localStorage.setItem('ai-news-view', mode);
      document.getElementById('viewCardsBtn').classList.toggle('active', mode === 'cards');
      document.getElementById('viewTableBtn').classList.toggle('active', mode === 'table');
      moveIndicator(document.getElementById('viewToggle'));
      swapContent(() => renderMain());
    }}

    function renderMain(opts = {{}}) {{
      const animate = opts.animate !== false;
      const q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const container = document.getElementById('mainContainer');
      const sorted = getSortedItems();

      const filtered = sorted.filter(item => {{
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

      currentDisplayedIds = filtered.map(i => i.id);

      if (!filtered.length) {{
        container.className = 'swap-target';
        container.innerHTML = '<div class="empty-state">No stories match your current filter or search query.</div>';
        return;
      }}

      if (currentView === 'table') {{
        container.className = 'compact-table-wrap swap-target';
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
              ${{filtered.map((item, rowIdx) => {{
                const isSaved = savedUrls.has(item.url);
                const effScore = getActiveScore(item);
                return `
                  <tr class="${{animate ? 'row-in' : ''}}" style="--i:${{Math.min(rowIdx, 20)}}" onclick="openDrawer('${{item.id}}', event)">
                    <td>
                      <button class="icon-btn ${{isSaved ? 'saved' : ''}}" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" aria-label="Save for later" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                    </td>
                    <td><span class="badge ${{badgeClass(effScore)}}">${{escapeHtml(item.func_tag)}}</span></td>
                    <td>
                      <a class="compact-headline" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
                      <div class="compact-takeaway">${{escapeHtml(item.benefit)}}</div>
                    </td>
                    <td class="compact-hide-mobile">
                      <span class="pub-pill">
                        <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                        ${{escapeHtml(item.source)}}
                      </span>
                    </td>
                    <td class="compact-hide-mobile"><strong>${{effScore}}</strong>/100</td>
                    <td style="white-space:nowrap;" title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</td>
                  </tr>
                `;
              }}).join('')}}
            </tbody>
          </table>
        `;
        return;
      }}

      container.className = 'cards-grid swap-target';
      container.innerHTML = filtered.map(item => {{
        const isSaved = savedUrls.has(item.url);
        const effScore = getActiveScore(item);
        const summaryHtml = item.summary
          ? `<p class="card-summary">${{escapeHtml(item.summary)}}</p>`
          : '';
        return `
          <article class="news-card ${{animate ? 'pre-reveal' : ''}}" onclick="openDrawer('${{item.id}}', event)">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="badge ${{badgeClass(effScore)}}">${{escapeHtml(item.func_tag)}}</span>
                  <span class="pub-pill">
                    <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                    ${{escapeHtml(item.source)}}
                  </span>
                </div>
                <div class="card-actions">
                  <button class="icon-btn" title="Share / copy link" aria-label="Share or copy link" onclick="shareById('${{item.id}}', event)">${{ICON_LINK}}</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" title="Save for later" aria-label="Save for later" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                </div>
              </div>
              <h3 class="card-title">
                <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              ${{summaryHtml}}
            </div>
            <div>
              <div class="benefit-box ${{boxClass(effScore)}}">
                <div class="benefit-header">
                  <span class="benefit-label">🇬🇧 UK Finance Team Takeaway</span>
                  <span class="score-meter-wrap">
                    <span>${{effScore}}/100</span>
                    <span class="score-bar"><span class="score-fill" style="width:${{effScore}}%"></span></span>
                  </span>
                </div>
                ${{escapeHtml(item.benefit)}}
              </div>
              <div class="card-footer">
                <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span>
                <div class="footer-links">
                  <button class="quick-brief-btn" onclick="openDrawer('${{item.id}}', event)">⚡ Quick Brief</button>
                  <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Source <span class="arrow">↗</span></a>
                </div>
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
      const top5 = getSortedItems().slice(0, 5);
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
      const apply = () => {{
        root.setAttribute('data-theme', next);
        localStorage.setItem('ai-news-theme', next);
      }};
      if (REDUCED_MOTION) {{ apply(); return; }}
      if (document.startViewTransition) {{
        document.startViewTransition(apply);
        return;
      }}
      root.classList.add('theme-anim');
      apply();
      setTimeout(() => root.classList.remove('theme-anim'), 320);
    }}

    let scrollTicking = false;
    window.addEventListener('scroll', () => {{
      if (scrollTicking) return;
      scrollTicking = true;
      requestAnimationFrame(() => {{
        const scrollTop = window.scrollY || document.documentElement.scrollTop;
        const docHeight = document.documentElement.scrollHeight - window.innerHeight;
        const ratio = docHeight > 0 ? Math.min(scrollTop / docHeight, 1) : 0;
        document.getElementById('scrollProgress').style.transform = `scaleX(${{ratio}})`;
        document.getElementById('backToTop').classList.toggle('visible', scrollTop > 420);
        scrollTicking = false;
      }});
    }}, {{ passive: true }});

    let resizeTimer = null;
    window.addEventListener('resize', () => {{
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => moveAllIndicators(false), 100);
    }});

    window.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape' && activeDrawerId) {{
        closeDrawer();
        return;
      }}
      if (activeDrawerId && e.key === 'ArrowRight') {{
        stepDrawer(1);
        return;
      }}
      if (activeDrawerId && e.key === 'ArrowLeft') {{
        stepDrawer(-1);
        return;
      }}
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
      requestAnimationFrame(() => moveAllIndicators(false));
      if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => moveAllIndicators(false));
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
