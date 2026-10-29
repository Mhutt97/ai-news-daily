"""Interactive UK Finance & AI News Dashboard generator and Finance Benefit prioritization engine."""

from __future__ import annotations

from datetime import datetime, timezone
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
            "💷 UK Finance",
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

    previous_urls: set[str] = set()
    prev_data_path = DOCS_DIR / "data.json"
    if prev_data_path.exists():
        try:
            prev_data = json.loads(prev_data_path.read_text(encoding="utf-8"))
            if isinstance(prev_data, list):
                previous_urls = {
                    str(r.get("url")) for r in prev_data if isinstance(r, dict) and r.get("url")
                }
        except Exception:
            pass

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
        is_new = bool(previous_urls and item.url not in previous_urls)

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
                "is_new": is_new,
            }
        )

    cards.sort(key=lambda c: int(c["score"]), reverse=True)
    return cards


def build_dashboard_html(
    cards: list[dict[str, object]], date_str: str, updated_at: str = ""
) -> str:
    """Render an editorial UK Finance & AI Intelligence Dashboard."""
    total = max(len(cards), 1)
    high_impact_count = sum(1 for c in cards if int(c["score"]) >= 85)
    ops_count = sum(1 for c in cards if 70 <= int(c["score"]) < 85)
    general_count = sum(1 for c in cards if int(c["score"]) < 70)

    high_pct = round((high_impact_count / total) * 100, 1)
    ops_pct = round((ops_count / total) * 100, 1)
    gen_pct = max(0.0, round(100.0 - high_pct - ops_pct, 1))
    sources_count = len({str(c.get("source", "")) for c in cards if c.get("source")})
    updated_str = updated_at or datetime.now(timezone.utc).strftime("%d %b %Y · %H:%M UTC")

    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en-GB" data-theme="light">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#171717" />
  <meta name="description" content="UK Finance & AI News in 5 Minutes a Day — curated & ranked daily for UK CFOs, Accounting, Audit, FCA Compliance & FP&A teams." />
  <meta property="og:title" content="UK Finance & AI Daily Intelligence — {html.escape(date_str)}" />
  <meta property="og:description" content="Get the latest AI news, understand why it matters for UK Finance & CFO teams, and apply it in 5 minutes a day." />
  <meta property="og:type" content="website" />
  <meta property="og:url" content="https://mhutt97.github.io/ai-news-daily/" />
  <meta name="robots" content="index, follow" />
  <title>UK Finance & AI Daily Intelligence — {html.escape(date_str)}</title>
  <link rel="preconnect" href="https://api.fontshare.com" crossorigin />
  <link href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,700,900&display=swap" rel="stylesheet" />
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --font-sans: "Satoshi", "Satoshi Variable", "Plus Jakarta Sans", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;

      /* Core Editorial Palette (Light Paper Default + Obsidian Masthead) */
      --stage-bg: #171717;
      --paper: #ffffff;
      --card-bg: #ffffff;
      --mist: #f5f5f5;
      --mist-soft: #fafafa;
      --ink: #171717;
      --ink-soft: #262626;
      --mute: #737373;
      --line: #e5e5e5;
      --line-subtle: #efefef;
      --glass-sheet: rgba(255, 255, 255, 0.9);

      /* Editorial Tri-Tone Accents */
      --brand-pink: #cd408f;
      --brand-violet: #8b4cd4;
      --brand-violet-bg: rgba(139, 76, 212, 0.09);
      --brand-violet-border: rgba(139, 76, 212, 0.28);
      --brand-blue: #6254ff;
      --brand-blue-bg: rgba(98, 84, 255, 0.09);
      --brand-blue-border: rgba(98, 84, 255, 0.25);
      --emerald: #009767;
      --emerald-bg: rgba(0, 151, 103, 0.09);
      --emerald-border: rgba(0, 151, 103, 0.26);
      --green-live: #00c758;
      --danger: #e40014;
      --danger-bg: rgba(228, 0, 20, 0.08);
      --danger-border: rgba(228, 0, 20, 0.28);

      --heading-grad: linear-gradient(91.69deg, #000000 0.85%, #4c4c4c 96.98%);
      --card-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
      --card-hover-shadow: 0 20px 44px -18px rgba(23, 23, 23, 0.13);

      --spring: cubic-bezier(0.16, 1, 0.3, 1);
      --ease-in-out: cubic-bezier(0.65, 0, 0.35, 1);
      --drawer-ease: cubic-bezier(0.32, 0.72, 0, 1);
      --dur-fast: 150ms;
      --dur: 240ms;
      --dur-slow: 460ms;
    }}

    [data-theme="dark"] {{
      --stage-bg: #0c0c0c;
      --paper: #141414;
      --card-bg: #1c1c1c;
      --mist: #232323;
      --mist-soft: #191919;
      --ink: #ffffff;
      --ink-soft: #e5e5e5;
      --mute: #a1a1aa;
      --line: #2e2e2e;
      --line-subtle: #242424;
      --glass-sheet: rgba(20, 20, 20, 0.9);

      --brand-violet: #b380ff;
      --brand-violet-bg: rgba(179, 128, 255, 0.13);
      --brand-violet-border: rgba(179, 128, 255, 0.35);
      --brand-blue: #8c82ff;
      --brand-blue-bg: rgba(140, 130, 255, 0.13);
      --brand-blue-border: rgba(140, 130, 255, 0.32);
      --emerald: #34d399;
      --emerald-bg: rgba(52, 211, 153, 0.12);
      --emerald-border: rgba(52, 211, 153, 0.32);
      --danger: #ff6470;
      --danger-bg: rgba(255, 100, 112, 0.14);
      --danger-border: rgba(255, 100, 112, 0.36);

      --heading-grad: linear-gradient(91.69deg, #ffffff 0.85%, #a3a3a3 96.98%);
      --card-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      --card-hover-shadow: 0 22px 48px -18px rgba(0, 0, 0, 0.65);
    }}

    *, *::before, *::after {{
      box-sizing: border-box;
      font-family: var(--font-sans);
      font-variant-numeric: tabular-nums;
      -webkit-tap-highlight-color: transparent;
    }}
    button, input, select, textarea, table, th, td, span, div, p, a, h1, h2, h3, h4 {{
      font-family: var(--font-sans);
    }}
    code, kbd {{
      font-family: var(--font-sans);
    }}

    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      background-color: var(--stage-bg);
      color: var(--ink);
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
      -moz-osx-font-smoothing: grayscale;
      overflow-x: hidden;
    }}

    /* Tri-Tone Top Reading Progress */
    #scrollProgress {{
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      height: 2.5px;
      transform-origin: 0 50%;
      transform: scaleX(0);
      background: linear-gradient(90deg, var(--brand-pink) 0%, var(--brand-violet) 50%, var(--brand-blue) 100%);
      z-index: 1000;
      will-change: transform;
    }}

    :focus-visible {{
      outline: 2px solid var(--brand-violet);
      outline-offset: 2px;
      border-radius: 8px;
    }}
    :focus:not(:focus-visible) {{ outline: none; }}

    html.theme-anim, html.theme-anim *, html.theme-anim *::before, html.theme-anim *::after {{
      transition: background-color var(--dur) var(--ease-in-out), border-color var(--dur) var(--ease-in-out), color var(--dur) var(--ease-in-out) !important;
    }}

    .swap-target {{
      transition: opacity var(--dur-fast) var(--ease-in-out), transform var(--dur-fast) var(--ease-in-out);
    }}
    .swap-target.is-swapping {{
      opacity: 0;
      transform: translateY(5px);
    }}

    .svg-icon {{
      width: 16px;
      height: 16px;
      flex-shrink: 0;
      stroke: currentColor;
      fill: none;
      stroke-width: 1.85;
      stroke-linecap: round;
      stroke-linejoin: round;
    }}

    .uk-flag {{
      width: 15px;
      height: 10px;
      border-radius: 2px;
      vertical-align: -1px;
      display: inline-block;
      box-shadow: 0 0 0 1px rgba(128, 128, 128, 0.25);
      flex-shrink: 0;
    }}

    /* Editorial Text Gradients */
    .text-gradient {{
      background-image: linear-gradient(45deg, var(--brand-pink), var(--brand-violet) 50%, var(--brand-blue));
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
    }}
    .text-gradient-heading {{
      background-image: var(--heading-grad);
      -webkit-background-clip: text;
      background-clip: text;
      color: transparent;
      padding-bottom: 0.08em;
      margin-bottom: -0.08em;
    }}

    /* =========================================================
       1. TOP STICKY OBSIDIAN MASTHEAD
       ========================================================= */
    .site-nav {{
      position: sticky;
      top: 0;
      z-index: 80;
      background: rgba(23, 23, 23, 0.92);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border-bottom: 1px solid rgba(255, 255, 255, 0.09);
      color: #ffffff;
    }}
    .site-nav-inner {{
      max-width: 1280px;
      margin: 0 auto;
      height: 68px;
      padding: 0 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
    }}
    .brand-lockup {{
      display: inline-flex;
      align-items: center;
      gap: 11px;
      text-decoration: none;
      color: #ffffff;
      flex-shrink: 0;
    }}
    .brand-monogram {{
      width: 35px;
      height: 35px;
      border-radius: 8px;
      background: #ffffff;
      color: #171717;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      font-weight: 900;
      font-size: 14.5px;
      letter-spacing: -0.04em;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
      flex-shrink: 0;
    }}
    .brand-wordmark {{
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.035em;
      color: #ffffff;
      line-height: 1;
    }}
    .brand-edition-pill {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 10.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      padding: 4px 9px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.14);
      color: rgba(255, 255, 255, 0.88);
    }}

    .nav-links {{
      display: flex;
      align-items: center;
      gap: 22px;
    }}
    .nav-link {{
      background: transparent;
      border: none;
      padding: 6px 2px;
      color: rgba(255, 255, 255, 0.75);
      font-size: 14px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      transition: color var(--dur-fast) ease;
      white-space: nowrap;
    }}
    .nav-link:hover {{
      color: #ffffff;
    }}

    .nav-actions {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-shrink: 0;
    }}
    .nav-btn {{
      cursor: pointer;
      border: 1px solid rgba(255, 255, 255, 0.16);
      background: rgba(255, 255, 255, 0.06);
      color: #ffffff;
      padding: 7px 13px;
      height: 36px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
      transition: background-color var(--dur-fast) ease, border-color var(--dur-fast) ease, transform var(--dur-fast) ease;
      white-space: nowrap;
    }}
    .nav-btn:hover {{
      background: rgba(255, 255, 255, 0.14);
      border-color: rgba(255, 255, 255, 0.32);
    }}
    .nav-btn:active {{ transform: scale(0.97); }}
    .nav-btn-primary {{
      background: #ffffff;
      color: #171717;
      border-color: #ffffff;
      font-weight: 700;
    }}
    .nav-btn-primary:hover {{
      background: #f0f0f0;
      border-color: #f0f0f0;
    }}
    .nav-btn-icon {{
      width: 36px;
      padding: 0;
    }}

    /* =========================================================
       2. EDITORIAL HERO STAGE
       ========================================================= */
    .editorial-hero {{
      background:
        radial-gradient(680px circle at 50% 0%, rgba(139, 76, 212, 0.18), transparent 68%),
        var(--stage-bg);
      color: #ffffff;
      padding: 54px 20px 64px;
      text-align: center;
      animation: fadeSlideDown 0.55s var(--spring) both;
    }}
    .hero-eyebrow-pill {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 6px 14px;
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.13);
      font-size: 11.5px;
      font-weight: 700;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: rgba(255, 255, 255, 0.86);
      margin-bottom: 22px;
    }}
    .live-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--green-live);
      box-shadow: 0 0 0 0 rgba(0, 199, 88, 0.7);
      animation: pulseDot 2s infinite;
      flex-shrink: 0;
    }}
    .editorial-hero h1 {{
      margin: 0 auto;
      max-width: 820px;
      font-size: clamp(2.25rem, 5.3vw, 4.35rem);
      font-weight: 800;
      letter-spacing: -0.04em;
      line-height: 1.07;
      color: #ffffff;
    }}
    .hero-subtitle {{
      margin: 22px auto 0;
      max-width: 540px;
      font-size: clamp(15.5px, 1.6vw, 18px);
      line-height: 1.55;
      color: rgba(255, 255, 255, 0.76);
      font-weight: 400;
    }}

    /* White Pill Search Bar in Hero */
    .hero-search-form {{
      margin: 30px auto 0;
      max-width: 530px;
      display: flex;
      align-items: center;
      gap: 6px;
      background: #ffffff;
      padding: 6px 6px 6px 15px;
      border-radius: 14px;
      box-shadow: 0 18px 50px rgba(0, 0, 0, 0.34);
      border: 1px solid rgba(255, 255, 255, 0.2);
    }}
    .hero-search-form .svg-icon {{
      color: #737373;
      width: 18px;
      height: 18px;
    }}
    .hero-search-input {{
      flex: 1;
      min-width: 0;
      border: none;
      background: transparent;
      color: #171717;
      font-size: 15px;
      font-weight: 500;
      padding: 9px 6px;
      outline: none;
    }}
    .hero-search-input::placeholder {{
      color: #737373;
    }}
    .hero-kbd {{
      font-size: 11px;
      font-weight: 700;
      color: #737373;
      background: #f5f5f5;
      border: 1px solid #e5e5e5;
      padding: 2px 7px;
      border-radius: 6px;
      pointer-events: none;
    }}
    .hero-search-submit {{
      cursor: pointer;
      border: none;
      background: #171717;
      color: #ffffff;
      font-size: 14px;
      font-weight: 700;
      padding: 10px 18px;
      border-radius: 10px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background-color var(--dur-fast) ease, transform var(--dur-fast) ease;
      flex-shrink: 0;
    }}
    .hero-search-submit:hover {{
      background: #000000;
    }}

    /* Trusted Sources Social Proof Strip */
    .hero-proof {{
      margin: 36px auto 0;
      max-width: 880px;
    }}
    .hero-proof-label {{
      font-size: 13px;
      color: rgba(255, 255, 255, 0.65);
      margin: 0 0 14px;
    }}
    .hero-proof-label strong {{
      color: #ffffff;
      font-weight: 700;
    }}
    .hero-proof-logos {{
      display: flex;
      flex-wrap: wrap;
      justify-content: center;
      align-items: center;
      gap: 10px 24px;
    }}
    .proof-source {{
      font-size: 13.5px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: rgba(255, 255, 255, 0.56);
      transition: color var(--dur-fast) ease;
      cursor: pointer;
      background: none;
      border: none;
      padding: 2px 4px;
    }}
    .proof-source:hover {{
      color: #ffffff;
    }}

    /* =========================================================
       3. ROUNDED .sheet EDITORIAL PAPER BODY
       ========================================================= */
    .main-sheet-wrap {{
      padding: 0 10px 12px;
    }}
    .main-sheet {{
      background-color: var(--paper);
      color: var(--ink);
      border-radius: 28px;
      max-width: 1380px;
      margin: 0 auto;
      padding: 36px 28px 68px;
      box-shadow: 0 -4px 30px rgba(0, 0, 0, 0.14);
    }}
    .sheet-container {{
      max-width: 1220px;
      margin: 0 auto;
    }}

    /* Role Lens & Signal Snapshot Bar */
    .executive-strip {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding-bottom: 26px;
      border-bottom: 1px solid var(--line);
      margin-bottom: 34px;
    }}
    .lens-group-wrap {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }}
    .strip-micro-label {{
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--mute);
    }}
    /* Segmented Role Lens Switcher */
    .segmented-box {{
      display: inline-flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 4px;
      padding: 4px;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: var(--mist);
    }}
    .lens-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      color: var(--ink);
      padding: 7px 13px;
      border-radius: 8px;
      font-size: 13px;
      font-weight: 600;
      transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease, transform var(--dur-fast) ease;
      white-space: nowrap;
    }}
    .lens-btn:hover {{
      background: var(--paper);
    }}
    .lens-btn.active {{
      background: var(--ink);
      color: var(--paper);
      font-weight: 700;
    }}

    /* Sleek Editorial KPI Chips + Signal Mix */
    .signal-cluster {{
      display: flex;
      flex-direction: column;
      gap: 8px;
      min-width: min(100%, 460px);
    }}
    .kpi-strip {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
    }}
    .kpi-card {{
      cursor: pointer;
      background: var(--mist-soft);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 8px 11px;
      text-align: left;
      transition: border-color var(--dur-fast) ease, transform var(--dur-fast) ease, background-color var(--dur-fast) ease;
    }}
    .kpi-card:hover {{
      border-color: var(--brand-violet);
      transform: translateY(-1px);
    }}
    .kpi-card.active-kpi {{
      border-color: var(--ink);
      background: var(--mist);
    }}
    .kpi-val {{
      font-size: 19px;
      font-weight: 800;
      letter-spacing: -0.03em;
      line-height: 1.1;
      color: var(--ink);
    }}
    .kpi-label {{
      font-size: 10.5px;
      font-weight: 600;
      color: var(--mute);
      margin-top: 2px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      display: flex;
      align-items: center;
      gap: 4px;
    }}
    .signal-bar-row {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .signal-track {{
      flex: 1;
      height: 5px;
      border-radius: 999px;
      overflow: hidden;
      display: flex;
      background: var(--line);
      gap: 2px;
    }}
    .signal-seg {{
      height: 100%;
      transition: width var(--dur-slow) var(--spring);
    }}
    .signal-legend-inline {{
      display: flex;
      gap: 10px;
      font-size: 10.5px;
      font-weight: 600;
      color: var(--mute);
      white-space: nowrap;
    }}

    /* =========================================================
       4. TODAY'S EXECUTIVE BRIEFING — FEATURED #1 + TOP STACK
       ========================================================= */
    .editorial-showcase {{
      margin-bottom: 48px;
    }}
    .section-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-end;
      gap: 12px;
      margin-bottom: 22px;
    }}
    .eyebrow {{
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.18em;
      color: var(--brand-violet);
      margin: 0 0 6px;
      display: flex;
      align-items: center;
      gap: 7px;
    }}
    .eyebrow-dot {{
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--brand-violet);
      display: inline-block;
    }}
    .section-h2 {{
      margin: 0;
      font-size: clamp(1.65rem, 3vw, 2.35rem);
      font-weight: 800;
      letter-spacing: -0.035em;
      line-height: 1.1;
    }}
    .section-sub {{
      margin: 6px 0 0;
      font-size: 14px;
      color: var(--mute);
    }}

    .showcase-grid {{
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 22px;
      align-items: stretch;
    }}
    .showcase-grid.single-col {{
      grid-template-columns: 1fr;
    }}

    /* #1 Lead Feature Card */
    .lead-feature-card {{
      background: var(--mist-soft);
      border: 1px solid var(--line);
      border-radius: 26px;
      padding: 30px 32px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
      transition: border-color var(--dur) ease, box-shadow var(--dur-slow) var(--spring), transform var(--dur-slow) var(--spring);
    }}
    .lead-feature-card:hover {{
      border-color: var(--brand-violet-border);
      box-shadow: var(--card-hover-shadow);
      transform: translateY(-2px);
    }}
    .lead-title {{
      margin: 14px 0 12px;
      font-size: clamp(22px, 2.35vw, 30px);
      font-weight: 800;
      line-height: 1.18;
      letter-spacing: -0.028em;
    }}
    .lead-title a {{
      color: var(--ink);
      text-decoration: none;
      transition: color var(--dur-fast) ease;
    }}
    .lead-feature-card:hover .lead-title a {{
      color: var(--brand-violet);
    }}
    .lead-summary {{
      margin: 0 0 18px;
      font-size: 15px;
      line-height: 1.62;
      color: var(--mute);
    }}
    .lead-why-box {{
      background: var(--card-bg);
      border: 1px solid var(--line);
      border-left: 3px solid var(--brand-violet);
      border-radius: 16px;
      padding: 16px 18px;
      margin-bottom: 20px;
    }}
    .lead-action-line {{
      margin-top: 9px;
      padding-top: 9px;
      border-top: 1px dashed var(--line);
      font-size: 12.5px;
      color: var(--mute);
    }}
    .lead-action-line strong {{
      color: var(--ink);
    }}

    /* #2-#4 Right Column Stack */
    .top-stack {{
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .stack-card {{
      flex: 1;
      background: var(--card-bg);
      border: 1px solid var(--line);
      border-radius: 20px;
      padding: 18px 20px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      cursor: pointer;
      transition: border-color var(--dur) ease, box-shadow var(--dur-slow) var(--spring), transform var(--dur-slow) var(--spring);
    }}
    .stack-card:hover {{
      border-color: var(--brand-violet-border);
      box-shadow: var(--card-hover-shadow);
      transform: translateY(-2px);
    }}
    .stack-title {{
      margin: 8px 0 6px;
      font-size: 17.5px;
      font-weight: 700;
      line-height: 1.28;
      letter-spacing: -0.02em;
    }}
    .stack-title a {{
      color: var(--ink);
      text-decoration: none;
      transition: color var(--dur-fast) ease;
    }}
    .stack-card:hover .stack-title a {{
      color: var(--brand-violet);
    }}
    .stack-plus {{
      margin: 0 0 12px;
      font-size: 13.5px;
      line-height: 1.5;
      color: var(--mute);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .stack-plus strong {{
      color: var(--ink-soft);
      font-weight: 700;
    }}

    /* =========================================================
       5. EXPLORE THE LATEST — STICKY PILL CONTROLS & 3 VIEWS
       ========================================================= */
    .explore-section {{
      border-top: 1px solid var(--line);
      padding-top: 38px;
      scroll-margin-top: 80px;
    }}
    .explore-top-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 20px;
    }}
    .explore-right-tools {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 10px;
    }}

    /* Rounded-Full Pill Search in #stories */
    .pill-search-wrap {{
      display: flex;
      align-items: center;
      gap: 8px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--card-bg);
      padding: 5px 14px;
      min-width: 250px;
      transition: border-color var(--dur-fast) ease, box-shadow var(--dur-fast) ease;
    }}
    .pill-search-wrap:focus-within {{
      border-color: var(--brand-violet);
      box-shadow: 0 0 0 3px var(--brand-violet-bg);
    }}
    .pill-search-wrap .svg-icon {{
      color: var(--mute);
      width: 15px;
      height: 15px;
    }}
    .search-input {{
      border: none;
      background: transparent;
      color: var(--ink);
      font-size: 13.5px;
      font-weight: 500;
      padding: 5px 0;
      width: 100%;
      outline: none;
    }}
    .search-input::placeholder {{ color: var(--mute); }}

    .view-toggle {{
      display: inline-flex;
      align-items: center;
      gap: 2px;
      padding: 3px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--mist);
    }}
    .view-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      color: var(--mute);
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease;
    }}
    .view-btn:hover {{ color: var(--ink); }}
    .view-btn.active {{
      background: var(--ink);
      color: var(--paper);
      font-weight: 700;
    }}
    .view-btn .svg-icon {{ width: 13.5px; height: 13.5px; }}

    /* Rounded-Full Category Pills */
    .controls-bar {{
      margin-bottom: 26px;
      padding: 12px 0;
      position: sticky;
      top: 68px;
      z-index: 40;
      background: var(--glass-sheet);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--line-subtle);
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
    }}
    .tab {{
      cursor: pointer;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--ink);
      padding: 8px 17px;
      font-size: 13.5px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease, border-color var(--dur-fast) ease, transform var(--dur-fast) ease;
      white-space: nowrap;
    }}
    .tab:hover {{
      border-color: var(--brand-violet);
      color: var(--brand-violet);
    }}
    .tab:active {{ transform: scale(0.98); }}
    .tab.active, .tab.active:hover {{
      background: var(--ink);
      border-color: var(--ink);
      color: var(--paper);
      font-weight: 700;
    }}

    /* Secondary Topic Chips */
    .topic-bar {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 6px;
      margin-top: 10px;
    }}
    .topic-pill {{
      cursor: pointer;
      border: 1px solid transparent;
      background: var(--mist);
      color: var(--mute);
      padding: 5px 11px;
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all var(--dur-fast) ease;
      user-select: none;
    }}
    .topic-pill:hover {{
      color: var(--ink);
      border-color: var(--line);
    }}
    .topic-pill.active {{
      background: var(--brand-violet-bg);
      border-color: var(--brand-violet-border);
      color: var(--brand-violet);
      font-weight: 700;
    }}

    /* =========================================================
       6. STORY CARDS GRID (rounded-3xl editorial cards)
       ========================================================= */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
      gap: 22px;
    }}
    .news-card {{
      background: var(--card-bg);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 25px 26px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      position: relative;
      cursor: pointer;
      box-shadow: var(--card-shadow);
      transition:
        transform var(--dur-slow) var(--spring),
        border-color var(--dur) ease,
        box-shadow var(--dur-slow) var(--spring);
    }}
    .news-card.pre-reveal {{ opacity: 0; }}
    .news-card.in-view {{
      animation: cardIn 0.6s var(--spring) backwards;
      animation-delay: var(--reveal-delay, 0ms);
    }}
    .news-card:hover {{
      transform: translateY(-2px);
      border-color: var(--brand-violet-border);
      box-shadow: var(--card-hover-shadow);
    }}
    .news-card:active {{
      transform: translateY(0) scale(0.996);
      transition-duration: 100ms;
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

    /* Editorial Category Eyebrows & Badges */
    .cat-eyebrow {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .cat-high {{ color: var(--brand-violet); }}
    .cat-ops {{ color: var(--emerald); }}
    .cat-gen {{ color: var(--brand-blue); }}

    .badge {{
      font-size: 11px;
      font-weight: 700;
      padding: 3px 9px;
      border-radius: 999px;
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }}
    .badge-high {{
      background: var(--brand-violet-bg);
      border: 1px solid var(--brand-violet-border);
      color: var(--brand-violet);
    }}
    .badge-ops {{
      background: var(--emerald-bg);
      border: 1px solid var(--emerald-border);
      color: var(--emerald);
    }}
    .badge-gen {{
      background: var(--brand-blue-bg);
      border: 1px solid var(--brand-blue-border);
      color: var(--brand-blue);
    }}
    .rank-pill {{
      font-size: 11px;
      font-weight: 800;
      padding: 3px 9px;
      border-radius: 6px;
      background: var(--ink);
      color: var(--paper);
      letter-spacing: 0.02em;
    }}
    .new-badge {{
      font-size: 9.5px;
      font-weight: 800;
      letter-spacing: 0.06em;
      padding: 2px 6px;
      border-radius: 5px;
      background: var(--emerald-bg);
      border: 1px solid var(--emerald-border);
      color: var(--emerald);
      text-transform: uppercase;
    }}
    .urgency-badge {{
      font-size: 9.5px;
      font-weight: 800;
      letter-spacing: 0.05em;
      padding: 2px 7px;
      border-radius: 5px;
      background: var(--danger-bg);
      border: 1px solid var(--danger-border);
      color: var(--danger);
      text-transform: uppercase;
      display: inline-flex;
      align-items: center;
      gap: 3px;
    }}

    .pub-pill {{
      font-size: 11.5px;
      font-weight: 600;
      color: var(--mute);
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .pub-favicon {{
      width: 15px;
      height: 15px;
      border-radius: 4px;
      object-fit: contain;
      flex-shrink: 0;
    }}

    .card-actions {{
      display: flex;
      align-items: center;
      gap: 2px;
      flex-shrink: 0;
    }}
    .icon-btn {{
      cursor: pointer;
      border: none;
      background: transparent;
      color: var(--mute);
      width: 30px;
      height: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border-radius: 8px;
      transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease, transform var(--dur) var(--spring);
    }}
    .icon-btn:hover {{
      background: var(--mist);
      color: var(--ink);
    }}
    .icon-btn:active {{ transform: scale(0.9); }}
    .icon-btn.saved {{ color: var(--brand-violet); }}
    .icon-btn.saved .svg-icon {{ fill: currentColor; }}
    .icon-btn.just-saved .svg-icon {{ animation: savePop 0.45s var(--spring); }}

    .card-title {{
      margin: 0 0 10px;
      font-size: 20px;
      font-weight: 700;
      line-height: 1.28;
      letter-spacing: -0.022em;
    }}
    .card-title a {{
      color: var(--ink);
      text-decoration: none;
      transition: color var(--dur-fast) ease;
    }}
    .news-card:hover .card-title a,
    .card-title a:hover {{
      color: var(--brand-violet);
    }}
    .card-summary {{
      font-size: 14px;
      color: var(--mute);
      margin: 0 0 16px;
      line-height: 1.58;
    }}

    /* "Why It Matters" Inset Callout Box */
    .benefit-box {{
      background: var(--mist);
      border: 1px solid var(--line-subtle);
      padding: 13px 15px;
      border-radius: 15px;
      font-size: 13px;
      line-height: 1.52;
      color: var(--ink-soft);
      margin-bottom: 18px;
    }}
    .benefit-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-bottom: 5px;
    }}
    .benefit-label {{
      font-size: 10px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--brand-violet);
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }}
    .ops-box .benefit-label {{ color: var(--emerald); }}
    .gen-box .benefit-label {{ color: var(--brand-blue); }}

    .score-meter-wrap {{
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      font-weight: 700;
      color: var(--mute);
    }}
    .score-info-trigger {{
      cursor: help;
      font-size: 10px;
      font-weight: 700;
      color: var(--mute);
      border: 1px solid var(--line);
      border-radius: 50%;
      width: 14px;
      height: 14px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 1;
    }}
    .score-bar {{
      width: 36px;
      height: 4px;
      background: var(--line);
      border-radius: 99px;
      overflow: hidden;
    }}
    .score-fill {{
      height: 100%;
      border-radius: 99px;
      background: var(--brand-violet);
    }}
    .ops-box .score-fill {{ background: var(--emerald); }}
    .gen-box .score-fill {{ background: var(--brand-blue); }}

    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      font-size: 12px;
      font-weight: 500;
      color: var(--mute);
      padding-top: 14px;
      border-top: 1px solid var(--line-subtle);
    }}
    .footer-links {{
      display: inline-flex;
      align-items: center;
      gap: 12px;
      flex-shrink: 0;
    }}
    .quick-brief-btn {{
      cursor: pointer;
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--mute);
      font-size: 11.5px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 999px;
      transition: border-color var(--dur-fast) ease, color var(--dur-fast) ease;
    }}
    .quick-brief-btn:hover {{
      border-color: var(--ink);
      color: var(--ink);
    }}
    .read-link {{
      color: var(--ink);
      font-weight: 700;
      font-size: 12.5px;
      text-decoration: none;
      display: inline-flex;
      align-items: center;
      gap: 3px;
      transition: color var(--dur-fast) ease;
    }}
    .read-link:hover {{ color: var(--brand-violet); }}
    .read-link span.arrow {{
      display: inline-block;
      transition: transform var(--dur) var(--spring);
    }}
    .news-card:hover .read-link span.arrow,
    .lead-feature-card:hover .read-link span.arrow,
    .stack-card:hover .read-link span.arrow {{
      transform: translate(2px, -1px);
    }}

    /* =========================================================
       7. VIEW 2: "BRIEFING" 5-MINUTE EDITORIAL STREAM
       ========================================================= */
    .briefing-stream {{
      max-width: 860px;
      margin: 0 auto;
      display: flex;
      flex-direction: column;
      gap: 18px;
    }}
    .stream-article {{
      background: var(--card-bg);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 26px 30px;
      cursor: pointer;
      transition: border-color var(--dur) ease, box-shadow var(--dur-slow) var(--spring);
    }}
    .stream-article:hover {{
      border-color: var(--brand-violet-border);
      box-shadow: var(--card-hover-shadow);
    }}
    .stream-num {{
      font-size: 12px;
      font-weight: 900;
      padding: 3px 9px;
      border-radius: 999px;
      background: var(--ink);
      color: var(--paper);
    }}
    .stream-headline {{
      margin: 12px 0 14px;
      font-size: clamp(19px, 2.1vw, 23px);
      font-weight: 800;
      letter-spacing: -0.025em;
      line-height: 1.25;
    }}
    .stream-headline a {{
      color: var(--ink);
      text-decoration: none;
    }}
    .stream-article:hover .stream-headline a {{ color: var(--brand-violet); }}
    .stream-bullets {{
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin: 0 0 16px;
      padding: 15px 18px;
      border-radius: 16px;
      background: var(--mist-soft);
      border: 1px solid var(--line-subtle);
      font-size: 14px;
      line-height: 1.58;
      color: var(--ink-soft);
    }}
    .stream-bullet strong {{
      color: var(--ink);
      font-weight: 800;
    }}

    /* =========================================================
       8. VIEW 3: COMPACT ANALYST TABLE (AlphaSignal Style)
       ========================================================= */
    .compact-table-wrap {{
      background: var(--card-bg);
      border: 1px solid var(--line);
      border-radius: 22px;
      overflow-x: auto;
      box-shadow: var(--card-shadow);
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
      letter-spacing: 0.08em;
      color: var(--mute);
      border-bottom: 1px solid var(--line);
      background: var(--mist-soft);
      white-space: nowrap;
    }}
    .compact-table td {{
      padding: 15px 16px;
      border-bottom: 1px solid var(--line-subtle);
      vertical-align: top;
      transition: background-color var(--dur-fast) ease;
    }}
    .compact-table tr {{ cursor: pointer; }}
    .compact-table tbody tr.row-in {{
      animation: rowIn 0.4s var(--spring) backwards;
      animation-delay: calc(var(--i, 0) * 16ms);
    }}
    .compact-table tr:hover td {{
      background: var(--mist-soft);
    }}
    .compact-headline {{
      font-weight: 700;
      font-size: 14.5px;
      color: var(--ink);
      text-decoration: none;
      display: block;
      margin-bottom: 4px;
      letter-spacing: -0.01em;
    }}
    .compact-headline:hover {{ color: var(--brand-violet); }}
    .compact-takeaway {{
      font-size: 12.8px;
      color: var(--mute);
    }}

    /* Deep-Link Target Glow & Keyboard Selection */
    .news-card.target-highlight, .lead-feature-card.target-highlight, .stack-card.target-highlight, .stream-article.target-highlight {{
      animation: targetGlow 2.4s ease-out;
      border-color: var(--brand-violet) !important;
    }}
    .news-card.kbd-selected, .stream-article.kbd-selected {{
      outline: 2px solid var(--brand-violet);
      outline-offset: 2px;
    }}
    .compact-table tr.kbd-selected td {{
      background: var(--mist);
      outline: 1px solid var(--brand-violet);
    }}
    @keyframes targetGlow {{
      0% {{ box-shadow: 0 0 0 4px var(--brand-violet-bg), 0 18px 40px rgba(139, 76, 212, 0.25); }}
      70% {{ box-shadow: 0 0 0 4px var(--brand-violet-bg), 0 18px 40px rgba(139, 76, 212, 0.25); }}
      100% {{ box-shadow: var(--card-shadow); }}
    }}

    /* =========================================================
       9. SLIDE-OVER EXECUTIVE DRAWER & MODALS
       ========================================================= */
    .drawer-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(10, 10, 10, 0.55);
      backdrop-filter: blur(4px);
      -webkit-backdrop-filter: blur(4px);
      z-index: 200;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--dur-slow) var(--drawer-ease);
    }}
    body.drawer-open {{ overflow: hidden; }}
    .drawer-backdrop.open {{ opacity: 1; pointer-events: auto; }}
    .drawer-panel {{
      position: fixed;
      top: 0;
      right: 0;
      bottom: 0;
      width: min(540px, 100vw);
      background: var(--paper);
      color: var(--ink);
      border-left: 1px solid var(--line);
      box-shadow: -24px 0 60px rgba(0, 0, 0, 0.28);
      z-index: 210;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      transform: translateX(104%);
      visibility: hidden;
      transition: transform 0.48s var(--drawer-ease), visibility 0s linear 0.48s;
      overflow-y: auto;
      overscroll-behavior: contain;
    }}
    .drawer-panel.open {{
      transform: translateX(0);
      visibility: visible;
      transition: transform 0.48s var(--drawer-ease), visibility 0s;
    }}
    .drawer-header {{
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      background: var(--paper);
      z-index: 5;
    }}
    .drawer-body {{
      padding: 26px 24px;
      flex: 1;
      transition: opacity var(--dur-fast) var(--ease-in-out), transform var(--dur-fast) var(--ease-in-out);
    }}
    .drawer-body.swap-next {{ opacity: 0; transform: translateX(-10px); }}
    .drawer-body.swap-prev {{ opacity: 0; transform: translateX(10px); }}
    .drawer-title {{
      font-size: 22px;
      font-weight: 800;
      line-height: 1.28;
      margin: 14px 0 10px;
      letter-spacing: -0.025em;
      color: var(--ink);
    }}
    .drawer-meta {{
      font-size: 12.5px;
      color: var(--mute);
      margin-bottom: 20px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--line);
    }}
    .drawer-section {{
      background: var(--mist-soft);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px 18px;
      margin-bottom: 14px;
    }}
    .drawer-sec-title {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 6px;
    }}
    .drawer-sec-text {{
      font-size: 14px;
      color: var(--ink-soft);
      line-height: 1.58;
      margin: 0;
    }}
    .drawer-footer {{
      padding: 16px 24px;
      border-top: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 10px;
      position: sticky;
      bottom: 0;
      background: var(--paper);
    }}
    .drawer-nav {{ display: inline-flex; gap: 6px; align-items: center; }}
    .drawer-progress {{ font-size: 12px; font-weight: 600; color: var(--mute); margin-left: 6px; }}

    .btn {{
      cursor: pointer;
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--ink);
      padding: 9px 16px;
      min-height: 40px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 7px;
      text-decoration: none;
      transition: all var(--dur-fast) ease;
    }}
    .btn:hover {{
      border-color: var(--ink);
      background: var(--mist);
    }}
    .btn-primary {{
      background: var(--ink);
      border-color: var(--ink);
      color: var(--paper);
    }}
    .btn-primary:hover {{
      background: var(--brand-violet);
      border-color: var(--brand-violet);
      color: #ffffff;
    }}

    /* Modals */
    .modal-backdrop {{
      position: fixed;
      inset: 0;
      background: rgba(10, 10, 10, 0.6);
      backdrop-filter: blur(5px);
      -webkit-backdrop-filter: blur(5px);
      z-index: 300;
      opacity: 0;
      pointer-events: none;
      transition: opacity var(--dur) var(--ease-in-out);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
    }}
    .modal-backdrop.open {{ opacity: 1; pointer-events: auto; }}
    .modal-dialog {{
      background: var(--paper);
      color: var(--ink);
      border: 1px solid var(--line);
      border-radius: 24px;
      max-width: 520px;
      width: 100%;
      box-shadow: 0 25px 60px rgba(0, 0, 0, 0.35);
      transform: translateY(14px) scale(0.97);
      transition: transform var(--dur-slow) var(--spring);
      overflow: hidden;
    }}
    .modal-backdrop.open .modal-dialog {{ transform: translateY(0) scale(1); }}
    .modal-header {{
      padding: 18px 22px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .modal-title {{
      font-size: 16.5px;
      font-weight: 800;
      letter-spacing: -0.02em;
      margin: 0;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .modal-body {{ padding: 22px; max-height: 80vh; overflow-y: auto; }}
    .share-channel-grid {{ display: grid; grid-template-columns: 1fr; gap: 10px; }}
    .share-channel-card {{
      background: var(--mist-soft);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px 16px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      cursor: pointer;
      transition: all var(--dur-fast) ease;
    }}
    .share-channel-card:hover {{
      border-color: var(--brand-violet);
      background: var(--mist);
      transform: translateY(-1px);
    }}
    .share-channel-info {{ display: flex; align-items: center; gap: 12px; }}
    .share-icon-wrap {{
      width: 38px;
      height: 38px;
      border-radius: 10px;
      background: var(--card-bg);
      border: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 17px;
      flex-shrink: 0;
    }}
    .kbd-shortcut-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 9px 0;
      border-bottom: 1px solid var(--line-subtle);
      font-size: 13.5px;
    }}
    .kbd-shortcut-row:last-child {{ border-bottom: none; }}
    kbd {{
      background: var(--mist);
      border: 1px solid var(--line);
      color: var(--ink);
      padding: 2px 7px;
      border-radius: 6px;
      font-size: 11px;
      font-weight: 700;
    }}

    /* =========================================================
       10. ROUNDED FOOTER SHEET
       ========================================================= */
    .site-footer-wrap {{
      padding: 0 10px 16px;
    }}
    .footer-sheet {{
      max-width: 1380px;
      margin: 0 auto;
      background: #171717;
      border: 1px solid rgba(255, 255, 255, 0.08);
      border-radius: 28px;
      padding: 44px 36px;
      color: #ffffff;
    }}
    .footer-grid {{
      max-width: 1220px;
      margin: 0 auto;
      display: grid;
      grid-template-columns: 1.4fr 1fr 1fr;
      gap: 32px;
    }}
    .footer-desc {{
      margin: 14px 0 16px;
      font-size: 13.5px;
      line-height: 1.6;
      color: rgba(255, 255, 255, 0.65);
      max-width: 44ch;
    }}
    .footer-col-title {{
      font-size: 11.5px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: rgba(255, 255, 255, 0.48);
      margin: 0 0 14px;
    }}
    .footer-links-list {{
      list-style: none;
      margin: 0;
      padding: 0;
      display: flex;
      flex-direction: column;
      gap: 9px;
    }}
    .footer-links-list button, .footer-links-list a {{
      background: none;
      border: none;
      padding: 0;
      color: rgba(255, 255, 255, 0.78);
      font-size: 13.5px;
      font-weight: 500;
      cursor: pointer;
      text-decoration: none;
      text-align: left;
      transition: color var(--dur-fast) ease;
    }}
    .footer-links-list button:hover, .footer-links-list a:hover {{ color: #ffffff; }}
    .footer-bottom {{
      max-width: 1220px;
      margin: 32px auto 0;
      padding-top: 22px;
      border-top: 1px solid rgba(255, 255, 255, 0.1);
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      font-size: 12px;
      color: rgba(255, 255, 255, 0.52);
    }}

    /* Floating Back-to-Top & Toast */
    #backToTop {{
      position: fixed;
      bottom: 24px;
      left: 24px;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      border: 1px solid var(--line);
      background: var(--ink);
      color: var(--paper);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.25);
      opacity: 0;
      transform: translateY(12px) scale(0.92);
      pointer-events: none;
      transition: opacity var(--dur) ease, transform var(--dur-slow) var(--spring);
      z-index: 90;
    }}
    #backToTop.visible {{ opacity: 1; transform: translateY(0) scale(1); pointer-events: auto; }}
    #backToTop:hover {{ background: var(--brand-violet); border-color: var(--brand-violet); color: #ffffff; }}

    #toast {{
      position: fixed;
      bottom: 24px;
      right: 24px;
      background: #171717;
      border: 1px solid rgba(255, 255, 255, 0.16);
      color: #ffffff;
      font-weight: 600;
      font-size: 13px;
      padding: 12px 18px;
      border-radius: 999px;
      box-shadow: 0 14px 34px rgba(0, 0, 0, 0.32);
      display: flex;
      align-items: center;
      gap: 8px;
      opacity: 0;
      transform: translateY(12px) scale(0.97);
      pointer-events: none;
      transition: opacity var(--dur) ease, transform var(--dur-slow) var(--spring);
      z-index: 350;
    }}
    #toast.show {{ opacity: 1; transform: translateY(0) scale(1); }}

    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 56px 20px;
      color: var(--mute);
      background: var(--mist-soft);
      border: 1px dashed var(--line);
      border-radius: 24px;
    }}

    @keyframes fadeSlideDown {{
      from {{ opacity: 0; transform: translateY(-10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes pulseDot {{
      0% {{ box-shadow: 0 0 0 0 rgba(0, 199, 88, 0.7); }}
      70% {{ box-shadow: 0 0 0 7px rgba(0, 199, 88, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(0, 199, 88, 0); }}
    }}
    @keyframes savePop {{
      0% {{ transform: scale(1); }}
      40% {{ transform: scale(1.24); }}
      100% {{ transform: scale(1); }}
    }}
    @keyframes cardIn {{
      from {{ opacity: 0; transform: translateY(14px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes rowIn {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    ::view-transition-old(root), ::view-transition-new(root) {{
      animation-duration: 300ms;
      animation-timing-function: var(--ease-in-out);
    }}

    @media (max-width: 1020px) {{
      .nav-links {{ display: none; }}
      .showcase-grid {{ grid-template-columns: 1fr; }}
      .footer-grid {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 680px) {{
      .site-nav-inner {{ padding: 0 14px; height: 60px; }}
      .brand-edition-pill {{ display: none; }}
      .nav-btn span.hide-sm {{ display: none; }}
      .editorial-hero {{ padding: 38px 16px 46px; }}
      .hero-kbd {{ display: none; }}
      .main-sheet-wrap {{ padding: 0 4px 10px; }}
      .main-sheet {{ padding: 24px 16px 48px; border-radius: 22px; }}
      .kpi-strip {{ grid-template-columns: repeat(2, 1fr); }}
      .lead-feature-card {{ padding: 22px 20px; border-radius: 22px; }}
      .controls-bar {{ top: 60px; }}
      .pill-search-wrap {{ width: 100%; min-width: 0; }}
      .explore-right-tools {{ width: 100%; justify-content: space-between; }}
      .cards-grid {{ grid-template-columns: 1fr; gap: 16px; }}
      .news-card {{ padding: 20px; border-radius: 20px; }}
      .stream-article {{ padding: 20px; }}
      .compact-hide-mobile {{ display: none; }}
      .footer-sheet {{ padding: 32px 20px; border-radius: 22px; }}
      .footer-grid {{ grid-template-columns: 1fr; gap: 24px; }}
      #toast {{ left: 14px; right: 14px; bottom: 16px; justify-content: center; }}
    }}

    /* Boardroom A4 Print / PDF Memo Stylesheet */
    @media print {{
      body {{ background: #ffffff !important; color: #171717 !important; font-size: 10.5pt; }}
      #scrollProgress, .site-nav, .editorial-hero, .executive-strip, .controls-bar, .explore-right-tools,
      .card-actions, .quick-brief-btn, #backToTop, #toast, .drawer-backdrop, .drawer-panel, .modal-backdrop, .site-footer-wrap {{
        display: none !important;
      }}
      .main-sheet-wrap, .main-sheet {{ padding: 0 !important; box-shadow: none !important; border-radius: 0 !important; background: #ffffff !important; }}
      .print-memo-header {{
        display: block !important;
        border-bottom: 2px solid #171717;
        padding-bottom: 10px;
        margin-bottom: 18px;
      }}
      .lead-feature-card, .stack-card, .news-card, .stream-article {{
        background: #ffffff !important;
        color: #171717 !important;
        border: 1px solid #d4d4d4 !important;
        box-shadow: none !important;
        opacity: 1 !important;
        transform: none !important;
        break-inside: avoid;
        page-break-inside: avoid;
      }}
      .cards-grid {{ grid-template-columns: repeat(2, 1fr) !important; gap: 12px !important; }}
      .benefit-box, .lead-why-box {{ background: #f8f8f8 !important; color: #171717 !important; border-left: 3px solid #171717 !important; }}
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

  <!-- 1. TOP STICKY OBSIDIAN MASTHEAD -->
  <header class="site-nav">
    <div class="site-nav-inner">
      <a class="brand-lockup" href="#" onclick="resetAllFilters(event)" aria-label="UK Finance & AI Daily Intelligence Home">
        <span class="brand-monogram" aria-hidden="true">AI</span>
        <span class="brand-wordmark">UK Finance &amp; AI</span>
        <span class="brand-edition-pill"><span id="brandFlagSlot"></span> Daily Briefing</span>
      </a>

      <nav class="nav-links" aria-label="Primary sections">
        <button class="nav-link" type="button" onclick="jumpToSection('heroSection', 'all')">Top Briefing</button>
        <button class="nav-link" type="button" onclick="jumpToSection('stories', 'all')">Latest News</button>
        <button class="nav-link" type="button" onclick="jumpToSection('stories', 'high')">UK CFO &amp; FCA</button>
        <button class="nav-link" type="button" onclick="jumpToSection('stories', 'ops')">AI Ops &amp; Agents</button>
        <button class="nav-link" type="button" onclick="jumpToSection('stories', 'saved')">Saved</button>
      </nav>

      <div class="nav-actions">
        <button class="nav-btn nav-btn-primary" type="button" onclick="openShareModal()" title="Share executive briefing via Teams, Slack or Email">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          <span>Share</span>
        </button>
        <button class="nav-btn" type="button" onclick="exportToCsv()" title="Export intelligence register to CSV (Excel)">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
          <span class="hide-sm">CSV</span>
        </button>
        <button class="nav-btn" type="button" onclick="window.print()" title="Print or save Boardroom PDF">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M6 14h12v7H6z"/></svg>
          <span class="hide-sm">PDF</span>
        </button>
        <button class="nav-btn nav-btn-icon" type="button" onclick="toggleKbdModal()" aria-label="Keyboard shortcuts" title="Keyboard shortcuts (?)">
          <span style="font-weight:800;font-size:13px;">?</span>
        </button>
        <button class="nav-btn nav-btn-icon" type="button" id="themeToggleBtn" onclick="toggleTheme()" aria-label="Toggle light and dark theme" title="Toggle light / dark theme (t)">
          <svg class="svg-icon" id="themeIconSvg" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
        </button>
      </div>
    </div>
  </header>

  <!-- 2. EDITORIAL HERO STAGE -->
  <section class="editorial-hero">
    <div class="hero-eyebrow-pill">
      <span class="live-dot"></span>
      <span id="heroFlagSlot"></span>
      <span>{html.escape(date_str)} · Refreshed {updated_str}</span>
    </div>
    <h1>
      UK Finance &amp; AI news<br />
      in <span class="text-gradient">5 minutes</span> a day.
    </h1>
    <p class="hero-subtitle">
      Get the latest AI breakthroughs, understand why they matter for UK CFOs, Audit &amp; FCA compliance, and apply them in your work.
    </p>

    <form class="hero-search-form" role="search" onsubmit="submitHeroSearch(event)">
      <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input
        type="search"
        id="heroSearchInput"
        class="hero-search-input"
        placeholder="Search FCA, Deloitte, OpenAI, audit, agents…"
        aria-label="Search AI news and UK finance takeaways"
        oninput="onSearchInput(this)"
      />
      <span class="hero-kbd">/</span>
      <button type="submit" class="hero-search-submit">
        Explore
        <span aria-hidden="true">→</span>
      </button>
    </form>

    <div class="hero-proof">
      <p class="hero-proof-label">
        Curated daily across <strong>{sources_count} verified feeds</strong> from leading institutions &amp; labs:
      </p>
      <div class="hero-proof-logos" aria-label="Featured intelligence sources">
        <button type="button" class="proof-source" onclick="quickFilterQuery('UK Finance')">UK Finance</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('Deloitte')">Deloitte</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('PwC')">PwC UK</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('OpenAI')">OpenAI</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('Google')">Google DeepMind</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('MIT')">MIT Tech Review</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('TechCrunch')">TechCrunch</button>
        <button type="button" class="proof-source" onclick="quickFilterQuery('ArXiv')">ArXiv</button>
      </div>
    </div>
  </section>

  <!-- 3. MAIN ROUNDED .sheet EDITORIAL CANVAS -->
  <main class="main-sheet-wrap">
    <div class="main-sheet">
      <div class="sheet-container">

        <div class="print-memo-header" style="display:none;">
          <h2 style="margin:0 0 4px;font-size:18pt;font-weight:800;">UK FINANCE &amp; AI — DAILY EXECUTIVE BRIEFING</h2>
          <div style="font-size:10pt;color:#404040;margin-bottom:6px;">
            <strong>Date:</strong> {html.escape(date_str)} · {updated_str} | <strong>Scope:</strong> CFO Strategy, FCA/PRA Compliance, Internal Audit &amp; FP&amp;A
          </div>
          <div style="font-size:8.5pt;color:#737373;text-transform:uppercase;letter-spacing:0.06em;">
            PREPARED FOR UK FINANCE EXECUTIVE LEADERSHIP
          </div>
        </div>

        <!-- Role Priority Switcher + Compact Signal Snapshot -->
        <div class="executive-strip">
          <div class="lens-group-wrap">
            <span class="strip-micro-label">Role Lens</span>
            <div class="segmented-box" role="group" aria-label="Finance Role Lens">
              <button class="lens-btn active" type="button" data-lens="default" onclick="setRoleLens('default', this)">All Roles</button>
              <button class="lens-btn" type="button" data-lens="cfo" onclick="setRoleLens('cfo', this)">CFO &amp; Strategy</button>
              <button class="lens-btn" type="button" data-lens="audit" onclick="setRoleLens('audit', this)">Audit, Risk &amp; FCA</button>
              <button class="lens-btn" type="button" data-lens="fpa" onclick="setRoleLens('fpa', this)">FP&amp;A &amp; Systems</button>
            </div>
          </div>

          <div class="signal-cluster">
            <div class="kpi-strip">
              <button type="button" class="kpi-card" data-kpi="high" onclick="setFilterByName('high')">
                <div class="kpi-val" style="color:var(--brand-violet);" data-count="{high_impact_count}">{high_impact_count}</div>
                <div class="kpi-label"><span id="kpiFlagSlot"></span> UK Finance</div>
              </button>
              <button type="button" class="kpi-card" data-kpi="ops" onclick="setFilterByName('ops')">
                <div class="kpi-val" style="color:var(--emerald);" data-count="{ops_count}">{ops_count}</div>
                <div class="kpi-label">Ops &amp; Security</div>
              </button>
              <button type="button" class="kpi-card" data-kpi="general" onclick="setFilterByName('general')">
                <div class="kpi-val" style="color:var(--brand-blue);" data-count="{general_count}">{general_count}</div>
                <div class="kpi-label">Global Research</div>
              </button>
              <button type="button" class="kpi-card active-kpi" data-kpi="all" onclick="setFilterByName('all')">
                <div class="kpi-val" data-count="{len(cards)}">{len(cards)}</div>
                <div class="kpi-label">Total Stories</div>
              </button>
            </div>
            <div class="signal-bar-row">
              <div class="signal-track" aria-hidden="true">
                <div class="signal-seg" style="width:{high_pct}%;background:var(--brand-violet);"></div>
                <div class="signal-seg" style="width:{ops_pct}%;background:var(--emerald);"></div>
                <div class="signal-seg" style="width:{gen_pct}%;background:var(--brand-blue);"></div>
              </div>
              <div class="signal-legend-inline">
                <span>UK <span class="sig-pct-high">{high_pct}%</span></span>
                <span>Ops <span class="sig-pct-ops">{ops_pct}%</span></span>
                <span>AI <span class="sig-pct-gen">{gen_pct}%</span></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 4. TODAY'S EXECUTIVE BRIEFING (Featured #1 Lead + #2-#4 Top Stack) -->
        <section class="editorial-showcase swap-target" id="heroSection" aria-labelledby="heroTitle">
          <div class="section-head">
            <div>
              <p class="eyebrow"><span class="eyebrow-dot"></span> Today's Briefing</p>
              <h2 class="section-h2 text-gradient-heading" id="heroTitle">Top priorities today</h2>
            </div>
            <span class="section-sub">Click any story to open the 3-point Executive Brief</span>
          </div>
          <div class="showcase-grid" id="heroGrid"></div>
        </section>

        <!-- 5. EXPLORE THE LATEST -->
        <section class="explore-section" id="stories" aria-labelledby="storiesHeading">
          <div class="explore-top-row">
            <div>
              <h2 class="section-h2 text-gradient-heading" id="storiesHeading">Explore the latest</h2>
              <p class="section-sub"><span id="storiesCountLabel">{len(cards)} stories</span> curated today. Stay up to speed.</p>
            </div>

            <div class="explore-right-tools">
              <div class="pill-search-wrap">
                <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
                <input
                  type="search"
                  id="searchInput"
                  class="search-input"
                  placeholder="Filter stories…"
                  aria-label="Filter stories"
                  oninput="onSearchInput(this)"
                />
              </div>

              <div class="view-toggle" role="group" aria-label="View layout" id="viewToggle">
                <button class="view-btn active" type="button" id="viewCardsBtn" onclick="setViewMode('cards')" title="Editorial 3-column cards">
                  <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
                  Grid
                </button>
                <button class="view-btn" type="button" id="viewBriefingBtn" onclick="setViewMode('briefing')" title="5-minute executive reading stream">
                  <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 6h16M4 10h16M4 14h10M4 18h12"/></svg>
                  Briefing
                </button>
                <button class="view-btn" type="button" id="viewTableBtn" onclick="setViewMode('table')" title="Compact analyst table">
                  <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h18M3 12h18M3 18h18"/></svg>
                  Table
                </button>
              </div>
            </div>
          </div>

          <!-- Sticky Category Pills & Topic Chips -->
          <div class="controls-bar">
            <div class="tabs" role="tablist" id="filterTabs">
              <button class="tab active" type="button" data-filter="all" role="tab" aria-selected="true" onclick="setFilter('all', this)">All news ({len(cards)})</button>
              <button class="tab" type="button" data-filter="high" role="tab" aria-selected="false" onclick="setFilter('high', this)"><span id="tabFlagSlot"></span> High UK Finance ({high_impact_count})</button>
              <button class="tab" type="button" data-filter="ops" role="tab" aria-selected="false" onclick="setFilter('ops', this)">Ops &amp; Security ({ops_count})</button>
              <button class="tab" type="button" data-filter="general" role="tab" aria-selected="false" onclick="setFilter('general', this)">Global AI &amp; Research ({general_count})</button>
              <button class="tab" type="button" data-filter="saved" id="savedTabBtn" role="tab" aria-selected="false" onclick="setFilter('saved', this)">Saved (0)</button>
            </div>

            <div class="topic-bar" id="topicBar" role="group" aria-label="Filter by Topic">
              <button class="topic-pill active" type="button" data-topic="all" onclick="setTopic('all', this)">All Topics</button>
              <button class="topic-pill" type="button" data-topic="fca" onclick="setTopic('fca', this)">🏛️ FCA &amp; Regulation</button>
              <button class="topic-pill" type="button" data-topic="audit" onclick="setTopic('audit', this)">🛡️ Audit &amp; Risk</button>
              <button class="topic-pill" type="button" data-topic="cfo" onclick="setTopic('cfo', this)">📈 CFO Strategy</button>
              <button class="topic-pill" type="button" data-topic="privacy" onclick="setTopic('privacy', this)">🔒 Data Privacy</button>
              <button class="topic-pill" type="button" data-topic="agents" onclick="setTopic('agents', this)">🤖 AI Agents</button>
              <button class="topic-pill" type="button" data-topic="models" onclick="setTopic('models', this)">🧠 Frontier Models</button>
            </div>
          </div>

          <div id="mainContainer" class="swap-target"></div>
        </section>

      </div>
    </div>
  </main>

  <!-- 6. ROUNDED OBSIDIAN FOOTER SHEET -->
  <footer class="site-footer-wrap">
    <div class="footer-sheet">
      <div class="footer-grid">
        <div>
          <div class="brand-lockup" style="margin-bottom:4px;">
            <span class="brand-monogram" aria-hidden="true">AI</span>
            <span class="brand-wordmark">UK Finance &amp; AI</span>
            <span class="brand-edition-pill"><span id="footerFlagSlot"></span> Daily Briefing</span>
          </div>
          <p class="footer-desc">
            Daily AI intelligence curated and ranked by practical benefit for UK CFOs, Audit Partners, FP&amp;A teams, and FCA compliance leaders.
          </p>
        </div>

        <div>
          <h3 class="footer-col-title">Intelligence Feeds</h3>
          <ul class="footer-links-list">
            <li><button type="button" onclick="jumpToSection('heroSection', 'all')">Today's Top Briefing</button></li>
            <li><button type="button" onclick="jumpToSection('stories', 'high')">High UK Finance &amp; FCA</button></li>
            <li><button type="button" onclick="jumpToSection('stories', 'ops')">Finance Ops, Agents &amp; Privacy</button></li>
            <li><button type="button" onclick="jumpToSection('stories', 'general')">Global AI Labs &amp; ArXiv Papers</button></li>
            <li><button type="button" onclick="jumpToSection('stories', 'saved')">Saved Reading List</button></li>
          </ul>
        </div>

        <div>
          <h3 class="footer-col-title">Executive Toolkit</h3>
          <ul class="footer-links-list">
            <li><button type="button" onclick="openShareModal()">Share MS Teams / Outlook Brief</button></li>
            <li><button type="button" onclick="exportToCsv()">Download CSV Risk Register</button></li>
            <li><button type="button" onclick="window.print()">Print Boardroom PDF Memo</button></li>
            <li><button type="button" onclick="toggleKbdModal()">Keyboard Shortcuts (?)</button></li>
            <li><a href="https://github.com/Mhutt97/ai-news-daily" target="_blank" rel="noopener noreferrer">Source Code &amp; Archive ↗</a></li>
          </ul>
        </div>
      </div>

      <div class="footer-bottom">
        <span>Informational executive summary only; does not constitute regulatory, legal, or investment advice.</span>
        <span>Verified Feeds: <strong style="color:#fff;">{sources_count}</strong> · Refreshed: <strong style="color:#fff;">{updated_str}</strong></span>
      </div>
    </div>
  </footer>

  <!-- Slide-Over Executive Quick-Brief Drawer -->
  <div class="drawer-backdrop" id="drawerBackdrop" onclick="closeDrawer()"></div>
  <aside class="drawer-panel" id="drawerPanel" role="dialog" aria-modal="true" aria-labelledby="drawerBadge" aria-label="Executive Quick-Brief Drawer">
    <div class="drawer-header">
      <span class="badge badge-high" id="drawerBadge">Executive Quick-Brief</span>
      <button class="icon-btn" type="button" onclick="closeDrawer()" aria-label="Close drawer" title="Close (Esc)">
        <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
      </button>
    </div>
    <div class="drawer-body" id="drawerBody"></div>
    <div class="drawer-footer">
      <div class="drawer-nav">
        <button class="btn" type="button" onclick="stepDrawer(-1)" title="Previous story (←)" aria-label="Previous story">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
        <button class="btn" type="button" onclick="stepDrawer(1)" title="Next story (→)" aria-label="Next story">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18l6-6-6-6"/></svg>
        </button>
        <span class="drawer-progress" id="drawerProgress"></span>
      </div>
      <a class="btn btn-primary" id="drawerReadLink" href="#" target="_blank" rel="noopener noreferrer">
        Read story
        <span aria-hidden="true">↗</span>
      </a>
    </div>
  </aside>

  <!-- Share Briefing Modal -->
  <div class="modal-backdrop" id="shareModalBackdrop" onclick="closeShareModal()">
    <div class="modal-dialog" onclick="event.stopPropagation()" role="dialog" aria-modal="true" aria-labelledby="shareModalTitle">
      <div class="modal-header">
        <h3 class="modal-title" id="shareModalTitle">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/></svg>
          Share Executive Briefing
        </h3>
        <button class="icon-btn" type="button" onclick="closeShareModal()" aria-label="Close modal">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="share-channel-grid">
          <div class="share-channel-card" onclick="copyTeamBriefing(); closeShareModal();">
            <div class="share-channel-info">
              <div class="share-icon-wrap">💬</div>
              <div>
                <strong style="display:block;font-size:13.5px;color:var(--ink);">Copy MS Teams &amp; Slack Briefing</strong>
                <span style="font-size:12px;color:var(--mute);">Formatted top 5 stories &amp; takeaways ready to paste</span>
              </div>
            </div>
            <span class="read-link">Copy <span class="arrow">→</span></span>
          </div>

          <div class="share-channel-card" onclick="openEmailDraft(); closeShareModal();">
            <div class="share-channel-info">
              <div class="share-icon-wrap">✉️</div>
              <div>
                <strong style="display:block;font-size:13.5px;color:var(--ink);">Draft Outlook / Email Memo</strong>
                <span style="font-size:12px;color:var(--mute);">Pre-filled executive email draft with top 5 action items</span>
              </div>
            </div>
            <span class="read-link">Open <span class="arrow">→</span></span>
          </div>

          <div class="share-channel-card" onclick="copyDashboardUrl(); closeShareModal();">
            <div class="share-channel-info">
              <div class="share-icon-wrap">🔗</div>
              <div>
                <strong style="display:block;font-size:13.5px;color:var(--ink);">Copy Live Dashboard URL</strong>
                <span style="font-size:12px;color:var(--mute);">Direct public link to today's interactive briefing</span>
              </div>
            </div>
            <span class="read-link">Copy <span class="arrow">→</span></span>
          </div>

          <div class="share-channel-card" onclick="exportToCsv(); closeShareModal();">
            <div class="share-channel-info">
              <div class="share-icon-wrap">📊</div>
              <div>
                <strong style="display:block;font-size:13.5px;color:var(--ink);">Export CSV Risk Register</strong>
                <span style="font-size:12px;color:var(--mute);">Structured dataset for Excel, audit scoping &amp; FP&amp;A</span>
              </div>
            </div>
            <span class="read-link">Download <span class="arrow">↓</span></span>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Keyboard Shortcuts Modal -->
  <div class="modal-backdrop" id="kbdModalBackdrop" onclick="closeKbdModal()">
    <div class="modal-dialog" onclick="event.stopPropagation()" role="dialog" aria-modal="true" aria-labelledby="kbdModalTitle">
      <div class="modal-header">
        <h3 class="modal-title" id="kbdModalTitle">⌨️ Keyboard Navigation</h3>
        <button class="icon-btn" type="button" onclick="closeKbdModal()" aria-label="Close modal">
          <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18"/></svg>
        </button>
      </div>
      <div class="modal-body">
        <div class="kbd-shortcut-row"><span>Focus Search</span><kbd>/</kbd></div>
        <div class="kbd-shortcut-row"><span>Next / Previous Story</span><span><kbd>j</kbd> / <kbd>k</kbd> or <kbd>↓</kbd> / <kbd>↑</kbd></span></div>
        <div class="kbd-shortcut-row"><span>Open Quick-Brief Drawer</span><span><kbd>Enter</kbd> or <kbd>o</kbd></span></div>
        <div class="kbd-shortcut-row"><span>Close Drawer or Modal</span><kbd>Esc</kbd></div>
        <div class="kbd-shortcut-row"><span>Share Briefing Modal</span><kbd>s</kbd></div>
        <div class="kbd-shortcut-row"><span>Copy Teams / Slack Summary</span><kbd>c</kbd></div>
        <div class="kbd-shortcut-row"><span>Export CSV Register</span><kbd>e</kbd></div>
        <div class="kbd-shortcut-row"><span>Toggle Light / Dark Theme</span><kbd>t</kbd></div>
        <div class="kbd-shortcut-row"><span>Toggle Shortcuts Help</span><kbd>?</kbd></div>
      </div>
    </div>
  </div>

  <button id="backToTop" type="button" onclick="window.scrollTo({{top: 0, behavior: 'smooth'}})" aria-label="Back to top" title="Back to top">
    <svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M18 15l-6-6-6 6"/></svg>
  </button>
  <div id="toast" role="status" aria-live="polite">✓ Copied Top 5 UK Finance Briefing</div>

  <script>
    const ITEMS = {cards_json};
    const ITEM_MAP = new Map(ITEMS.map(it => [it.id, it]));
    const DATE_STR = "{html.escape(date_str)}";
    let currentFilter = 'all';
    let currentLens = 'default';
    let currentTopic = 'all';
    let currentView = localStorage.getItem('ai-news-view') || 'cards';
    if (!['cards', 'briefing', 'table'].includes(currentView)) currentView = 'cards';
    let savedUrls = new Set(JSON.parse(localStorage.getItem('ai-news-saved') || '[]'));
    let activeDrawerId = null;
    let currentDisplayedIds = [];
    let revealObserver = null;
    let lastFocusedEl = null;
    let searchTimer = null;
    let selectedCardIndex = -1;
    const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    const ICON_LINK = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>';
    const ICON_BOOKMARK = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 3h12v18l-6-4-6 4z"/></svg>';
    const ICON_MOON = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>';
    const ICON_SUN = '<svg class="svg-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M6.34 17.66l-1.41 1.41M19.07 4.93l-1.41 1.41"/></svg>';
    const FLAG_SVG = '<svg class="uk-flag" viewBox="0 0 60 30" width="15" height="10" aria-hidden="true"><clipPath id="flag-clip"><path d="M0,0 v30 h60 v-30 z"/></clipPath><clipPath id="diag-clip"><path d="M30,15 h30 v15 z v15 h-30 z h-30 v-15 z v-15 h30 z"/></clipPath><g clip-path="url(#flag-clip)"><path d="M0,0 v30 h60 v-30 z" fill="#012169"/><path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" stroke-width="6"/><path d="M0,0 L60,30 M60,0 L0,30" clip-path="url(#diag-clip)" stroke="#C8102E" stroke-width="4"/><path d="M30,0 v30 M0,15 h60" stroke="#fff" stroke-width="10"/><path d="M30,0 v30 M0,15 h60" stroke="#C8102E" stroke-width="6"/></g></svg>';

    function swapContent(renderFn) {{
      const targets = document.querySelectorAll('.swap-target');
      if (REDUCED_MOTION) {{ renderFn(); return; }}
      targets.forEach(t => t.classList.add('is-swapping'));
      clearTimeout(window._swapTimer);
      window._swapTimer = setTimeout(() => {{
        renderFn();
        requestAnimationFrame(() => targets.forEach(t => t.classList.remove('is-swapping')));
      }}, 140);
    }}

    function getSearchQuery() {{
      const s = document.getElementById('searchInput');
      return ((s && s.value) || '').toLowerCase().trim();
    }}

    function syncSearchInputs(val, exceptEl) {{
      const s1 = document.getElementById('heroSearchInput');
      const s2 = document.getElementById('searchInput');
      if (s1 && s1 !== exceptEl) s1.value = val;
      if (s2 && s2 !== exceptEl) s2.value = val;
    }}

    function onSearchInput(sourceEl) {{
      const val = sourceEl ? sourceEl.value : '';
      syncSearchInputs(val, sourceEl);
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {{
        selectedCardIndex = -1;
        renderHero();
        renderMain({{ animate: false }});
      }}, 90);
    }}

    function submitHeroSearch(ev) {{
      if (ev) ev.preventDefault();
      const target = document.getElementById('stories');
      if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function quickFilterQuery(term) {{
      syncSearchInputs(term, null);
      selectedCardIndex = -1;
      renderHero();
      renderMain({{ animate: false }});
      const target = document.getElementById('stories');
      if (target) target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function resetAllFilters(ev) {{
      if (ev) ev.preventDefault();
      syncSearchInputs('', null);
      currentTopic = 'all';
      document.querySelectorAll('.topic-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-topic') === 'all'));
      setFilterByName('all');
      renderHero();
      renderMain();
      window.scrollTo({{ top: 0, behavior: 'smooth' }});
    }}

    function jumpToSection(sectionId, filterName) {{
      if (filterName && filterName !== currentFilter) {{
        setFilterByName(filterName);
      }}
      const el = document.getElementById(sectionId);
      if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function escapeHtml(str) {{
      if (!str) return '';
      return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }}

    function formatTagHtml(tag) {{
      return escapeHtml(tag || '').replace(/\\uD83C\\uDDEC\\uD83C\\uDDE7/g, FLAG_SVG);
    }}

    function safeUrl(url) {{
      if (!url) return '#';
      try {{
        const u = new URL(url, window.location.origin);
        if (u.protocol === 'https:' || u.protocol === 'http:') return u.href;
      }} catch (e) {{}}
      return '#';
    }}

    function updateDynamicMetrics() {{
      const sorted = getSortedItems();
      const total = Math.max(sorted.length, 1);
      let high = 0, ops = 0, gen = 0;
      sorted.forEach(it => {{
        const s = getActiveScore(it);
        if (s >= 85) high++;
        else if (s >= 70) ops++;
        else gen++;
      }});
      const tAll = document.querySelector('.tab[data-filter="all"]');
      const tHigh = document.querySelector('.tab[data-filter="high"]');
      const tOps = document.querySelector('.tab[data-filter="ops"]');
      const tGen = document.querySelector('.tab[data-filter="general"]');
      if (tAll) tAll.textContent = `All news (${{sorted.length}})`;
      if (tHigh) tHigh.innerHTML = `${{FLAG_SVG}} High UK Finance (${{high}})`;
      if (tOps) tOps.textContent = `Ops & Security (${{ops}})`;
      if (tGen) tGen.textContent = `Global AI & Research (${{gen}})`;

      const kHigh = document.querySelector('.kpi-card[data-kpi="high"] .kpi-val');
      const kOps = document.querySelector('.kpi-card[data-kpi="ops"] .kpi-val');
      const kGen = document.querySelector('.kpi-card[data-kpi="general"] .kpi-val');
      if (kHigh) kHigh.textContent = high;
      if (kOps) kOps.textContent = ops;
      if (kGen) kGen.textContent = gen;

      const pHigh = ((high / total) * 100).toFixed(1);
      const pOps = ((ops / total) * 100).toFixed(1);
      const pGen = Math.max(0, (100 - parseFloat(pHigh) - parseFloat(pOps))).toFixed(1);
      const segs = document.querySelectorAll('.signal-seg');
      if (segs.length >= 3) {{
        segs[0].style.width = pHigh + '%';
        segs[1].style.width = pOps + '%';
        segs[2].style.width = pGen + '%';
      }}
      const lHigh = document.querySelector('.sig-pct-high');
      const lOps = document.querySelector('.sig-pct-ops');
      const lGen = document.querySelector('.sig-pct-gen');
      if (lHigh) lHigh.textContent = `${{pHigh}}%`;
      if (lOps) lOps.textContent = `${{pOps}}%`;
      if (lGen) lGen.textContent = `${{pGen}}%`;
    }}

    function showToast(msg) {{
      const t = document.getElementById('toast');
      if (!t) return;
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

    function catClass(score) {{
      if (score >= 85) return 'cat-high';
      if (score >= 70) return 'cat-ops';
      return 'cat-gen';
    }}

    function boxClass(score) {{
      if (score >= 85) return '';
      if (score >= 70) return 'ops-box';
      return 'gen-box';
    }}

    function urgencyBadgeHtml(effScore, item) {{
      const text = ((item.func_tag || '') + ' ' + (item.title || '') + ' ' + (item.summary || '')).toLowerCase();
      const isCritical = effScore >= 88 && (
        text.includes('fca') ||
        text.includes('pra') ||
        text.includes('audit') ||
        text.includes('regulation') ||
        text.includes('privacy') ||
        text.includes('governance')
      );
      if (isCritical) {{
        return '<span class="urgency-badge" title="High Governance & Regulatory Relevance">● High Urgency</span>';
      }}
      return '';
    }}

    function updateSavedTabCount() {{
      const btn = document.getElementById('savedTabBtn');
      if (btn) btn.textContent = `Saved (${{savedUrls.size}})`;
    }}

    function toggleSaveById(id, ev) {{
      if (ev) ev.stopPropagation();
      const item = ITEM_MAP.get(id);
      if (!item) return;
      const url = item.url;
      const nowSaved = !savedUrls.has(url);
      if (nowSaved) {{
        savedUrls.add(url);
        showToast('✓ Saved to your reading list');
      }} else {{
        savedUrls.delete(url);
        showToast('Removed from saved list');
      }}
      localStorage.setItem('ai-news-saved', JSON.stringify(Array.from(savedUrls)));
      updateSavedTabCount();

      if (currentFilter === 'saved') {{
        swapContent(() => {{ renderHero(); renderMain(); }});
        return;
      }}
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
      const shareUrl = `${{window.location.origin}}${{window.location.pathname}}#${{id}}`;
      if (navigator.clipboard) {{
        navigator.clipboard.writeText(shareUrl).then(() => {{
          showToast(`✓ Direct story link copied (${{id}})`);
        }});
      }}
      try {{
        history.replaceState(null, '', '#' + id);
      }} catch (e) {{}}
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

      try {{
        history.replaceState(null, '', '#' + id);
      }} catch (e) {{}}

      const paint = () => {{
        fillDrawer(item);
        body.classList.remove('swap-next', 'swap-prev');
        panel.scrollTop = 0;
      }};

      if (alreadyOpen && direction && !REDUCED_MOTION) {{
        body.classList.add(direction > 0 ? 'swap-next' : 'swap-prev');
        setTimeout(paint, 140);
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
      document.getElementById('drawerBadge').innerHTML = `${{formatTagHtml(item.func_tag)}} · Priority ${{effScore}}/100`;
      document.getElementById('drawerReadLink').href = safeUrl(item.url);
      const pos = currentDisplayedIds.indexOf(item.id);
      document.getElementById('drawerProgress').textContent =
        pos > -1 ? `${{pos + 1}} of ${{currentDisplayedIds.length}}` : '';

      const summaryBlock = item.summary
        ? `<div class="drawer-section"><div class="drawer-sec-title" style="color:var(--ink);">📰 Key Summary</div><p class="drawer-sec-text">${{escapeHtml(item.summary)}}</p></div>`
        : '';

      document.getElementById('drawerBody').innerHTML = `
        <div class="tag-group">
          <span class="pub-pill">
            <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
            ${{escapeHtml(item.source)}}
          </span>
          <span class="badge ${{badgeClass(effScore)}}">${{escapeHtml(item.category)}}</span>
          ${{urgencyBadgeHtml(effScore, item)}}
        </div>
        <h2 class="drawer-title">${{escapeHtml(item.title)}}</h2>
        <div class="drawer-meta">Published ${{escapeHtml(formatRelativeTime(item.published_at))}} (${{escapeHtml(item.published_at)}})</div>
        ${{summaryBlock}}
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--brand-violet);">${{FLAG_SVG}} Why It Matters · UK CFO &amp; Finance</div>
          <p class="drawer-sec-text">${{escapeHtml(item.benefit)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--emerald);">🛡️ Audit, Risk &amp; FCA Governance Angle</div>
          <p class="drawer-sec-text">${{escapeHtml(item.risk_angle)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--brand-blue);">✅ Recommended Action</div>
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
      try {{
        history.replaceState(null, '', window.location.pathname);
      }} catch (e) {{}}
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
      selectedCardIndex = -1;
      document.querySelectorAll('.lens-btn').forEach(b => b.classList.remove('active'));
      if (btn) btn.classList.add('active');
      const labels = {{
        default: 'Top priorities today',
        cfo: 'Top priorities for CFO & Strategy',
        audit: 'Top priorities for Audit, Risk & FCA',
        fpa: 'Top priorities for FP&A & Systems'
      }};
      swapContent(() => {{
        document.getElementById('heroTitle').textContent = labels[lens] || labels.default;
        updateDynamicMetrics();
        renderHero();
        renderMain();
      }});
    }}

    function setTopic(topic, btn) {{
      if (topic === currentTopic) return;
      currentTopic = topic;
      selectedCardIndex = -1;
      document.querySelectorAll('.topic-pill').forEach(p => p.classList.remove('active'));
      if (btn) btn.classList.add('active');
      swapContent(() => {{ renderHero(); renderMain(); }});
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
          el.style.setProperty('--reveal-delay', `${{Math.min(i, 5) * 45}}ms`);
          el.classList.remove('pre-reveal');
          el.classList.add('in-view');
          el.addEventListener('animationend', () => el.classList.remove('in-view'), {{ once: true }});
          revealObserver.unobserve(el);
        }});
      }}, {{ threshold: 0.05, rootMargin: '0px 0px -20px 0px' }});
      cards.forEach(card => revealObserver.observe(card));
    }}

    /* Render Asymmetric Editorial Showcase (#1 Featured Lead + #2-#4 Top Stack) */
    function renderHero() {{
      const q = getSearchQuery();
      const sorted = getSortedItems();
      const top4 = sorted.slice(0, 4);
      const heroSec = document.getElementById('heroSection');
      const heroGrid = document.getElementById('heroGrid');
      if (!top4.length || currentFilter !== 'all' || currentTopic !== 'all' || q) {{
        heroSec.style.display = 'none';
        return;
      }}
      heroSec.style.display = 'block';
      heroGrid.classList.toggle('single-col', top4.length < 2);

      const lead = top4[0];
      const leadSaved = savedUrls.has(lead.url);
      const leadScore = getActiveScore(lead);
      const leadNew = lead.is_new ? '<span class="new-badge">NEW</span>' : '';
      const leadUrgency = urgencyBadgeHtml(leadScore, lead);
      const leadSummary = lead.summary
        ? `<p class="lead-summary">${{escapeHtml(lead.summary)}}</p>`
        : `<p class="lead-summary">Ranked #1 in today's intelligence feed for direct relevance to UK financial leadership and enterprise AI adoption.</p>`;

      const leadHtml = `
        <article class="lead-feature-card" data-card-id="${{lead.id}}" onclick="openDrawer('${{lead.id}}', event)">
          <div>
            <div class="card-top">
              <div class="tag-group">
                <span class="rank-pill">#1 LEAD · ${{leadScore}}/100</span>
                <span class="cat-eyebrow ${{catClass(leadScore)}}">${{formatTagHtml(lead.func_tag)}}</span>
                ${{leadUrgency}}
                ${{leadNew}}
              </div>
              <div class="card-actions">
                <button class="icon-btn" type="button" title="Copy story link" aria-label="Copy story link" onclick="shareById('${{lead.id}}', event)">${{ICON_LINK}}</button>
                <button class="icon-btn ${{leadSaved ? 'saved' : ''}}" type="button" data-save-id="${{lead.id}}" aria-pressed="${{leadSaved}}" title="Save story" aria-label="Save story" onclick="toggleSaveById('${{lead.id}}', event)">${{ICON_BOOKMARK}}</button>
              </div>
            </div>

            <h3 class="lead-title">
              <a href="${{safeUrl(lead.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(lead.title)}}</a>
            </h3>
            ${{leadSummary}}

            <div class="lead-why-box">
              <div class="benefit-header">
                <span class="benefit-label">${{FLAG_SVG}} Why It Matters · UK Finance</span>
                <span class="score-meter-wrap">
                  <span>${{leadScore}}/100</span>
                  <span class="score-bar"><span class="score-fill" style="width:${{leadScore}}%"></span></span>
                </span>
              </div>
              <div style="font-size:13.8px;line-height:1.55;color:var(--ink-soft);">${{escapeHtml(lead.benefit)}}</div>
              <div class="lead-action-line"><strong>Next step:</strong> ${{escapeHtml(lead.action_item)}}</div>
            </div>
          </div>

          <div class="card-footer">
            <span class="pub-pill">
              <img class="pub-favicon" src="${{faviconUrl(lead.pub_domain)}}" alt="" loading="lazy" />
              ${{escapeHtml(lead.source)}} · <span title="${{escapeHtml(lead.published_at)}}">${{escapeHtml(formatRelativeTime(lead.published_at))}}</span>
            </span>
            <div class="footer-links">
              <button class="quick-brief-btn" type="button" onclick="openDrawer('${{lead.id}}', event)">Quick brief</button>
              <a class="read-link" href="${{safeUrl(lead.url)}}" target="_blank" rel="noopener noreferrer">Read story <span class="arrow">↗</span></a>
            </div>
          </div>
        </article>
      `;

      const rest = top4.slice(1);
      if (!rest.length) {{
        heroGrid.innerHTML = leadHtml;
        return;
      }}

      const stackHtml = `
        <div class="top-stack">
          ${{rest.map((item, idx) => {{
            const isSaved = savedUrls.has(item.url);
            const effScore = getActiveScore(item);
            const newBadge = item.is_new ? '<span class="new-badge">NEW</span>' : '';
            const urgencyBadge = urgencyBadgeHtml(effScore, item);
            return `
              <article class="stack-card" data-card-id="${{item.id}}" onclick="openDrawer('${{item.id}}', event)">
                <div>
                  <div class="card-top" style="margin-bottom:4px;">
                    <div class="tag-group">
                      <span class="rank-pill">#${{idx + 2}} · ${{effScore}}</span>
                      <span class="cat-eyebrow ${{catClass(effScore)}}">${{formatTagHtml(item.func_tag)}}</span>
                      ${{urgencyBadge}}
                      ${{newBadge}}
                    </div>
                    <div class="card-actions">
                      <button class="icon-btn" type="button" title="Copy story link" aria-label="Copy story link" onclick="shareById('${{item.id}}', event)">${{ICON_LINK}}</button>
                      <button class="icon-btn ${{isSaved ? 'saved' : ''}}" type="button" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" title="Save story" aria-label="Save story" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                    </div>
                  </div>
                  <h3 class="stack-title">
                    <a href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
                  </h3>
                  <p class="stack-plus"><strong>Why it matters:</strong> ${{escapeHtml(item.benefit)}}</p>
                </div>
                <div class="card-footer" style="padding-top:10px;">
                  <span class="pub-pill">
                    <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                    ${{escapeHtml(item.source)}} · ${{escapeHtml(formatRelativeTime(item.published_at))}}
                  </span>
                  <span class="read-link">Quick brief <span class="arrow">→</span></span>
                </div>
              </article>
            `;
          }}).join('')}}
        </div>
      `;

      heroGrid.innerHTML = leadHtml + stackHtml;
    }}

    function setFilter(filter, btn) {{
      if (filter === currentFilter) return;
      currentFilter = filter;
      selectedCardIndex = -1;
      document.querySelectorAll('.tab').forEach(t => {{
        t.classList.remove('active');
        t.setAttribute('aria-selected', 'false');
      }});
      if (btn) {{
        btn.classList.add('active');
        btn.setAttribute('aria-selected', 'true');
      }}
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
      selectedCardIndex = -1;
      localStorage.setItem('ai-news-view', mode);
      document.getElementById('viewCardsBtn').classList.toggle('active', mode === 'cards');
      document.getElementById('viewBriefingBtn').classList.toggle('active', mode === 'briefing');
      document.getElementById('viewTableBtn').classList.toggle('active', mode === 'table');
      swapContent(() => renderMain());
    }}

    function renderMain(opts = {{}}) {{
      const animate = opts.animate !== false;
      const q = getSearchQuery();
      const container = document.getElementById('mainContainer');
      const sorted = getSortedItems();

      const filtered = sorted.filter(item => {{
        const effScore = getActiveScore(item);
        if (currentFilter === 'high' && effScore < 85) return false;
        if (currentFilter === 'ops' && (effScore < 70 || effScore >= 85)) return false;
        if (currentFilter === 'general' && effScore >= 70) return false;
        if (currentFilter === 'saved' && !savedUrls.has(item.url)) return false;

        if (currentTopic !== 'all') {{
          const tag = (item.func_tag || '').toLowerCase();
          const txt = (item.title + ' ' + (item.summary || '') + ' ' + (item.benefit || '')).toLowerCase();
          if (currentTopic === 'fca' && !(tag.includes('fca') || tag.includes('regulation') || txt.includes('fca') || txt.includes('pra') || txt.includes('regulatory'))) return false;
          if (currentTopic === 'audit' && !(tag.includes('audit') || tag.includes('risk') || txt.includes('audit') || txt.includes('internal audit') || txt.includes('sox'))) return false;
          if (currentTopic === 'cfo' && !(tag.includes('cfo') || tag.includes('strategy') || txt.includes('cfo') || txt.includes('finance ops') || txt.includes('forecasting'))) return false;
          if (currentTopic === 'privacy' && !(tag.includes('privacy') || tag.includes('security') || txt.includes('privacy') || txt.includes('gdpr') || txt.includes('confidential'))) return false;
          if (currentTopic === 'agents' && !(tag.includes('agent') || tag.includes('workflow') || tag.includes('architecture') || txt.includes('agent'))) return false;
          if (currentTopic === 'models' && !(tag.includes('frontier') || tag.includes('model') || txt.includes('gpt') || txt.includes('gemini') || txt.includes('claude') || txt.includes('deepmind'))) return false;
        }}

        if (q) {{
          const hay = (item.title + ' ' + item.summary + ' ' + item.benefit + ' ' + item.source + ' ' + item.func_tag).toLowerCase();
          if (!hay.includes(q)) return false;
        }}
        return true;
      }});

      currentDisplayedIds = filtered.map(i => i.id);

      const countLbl = document.getElementById('storiesCountLabel');
      if (countLbl) {{
        countLbl.textContent = `${{filtered.length}} ${{filtered.length === 1 ? 'story' : 'stories'}}`;
      }}

      if (!filtered.length) {{
        container.className = 'swap-target';
        container.innerHTML = '<div class="empty-state">No stories match your current filter, topic, or search query.</div>';
        return;
      }}

      /* VIEW MODE 3: COMPACT ANALYST TABLE */
      if (currentView === 'table') {{
        container.className = 'compact-table-wrap swap-target';
        container.innerHTML = `
          <table class="compact-table">
            <thead>
              <tr>
                <th>Save</th>
                <th>Category</th>
                <th>Story &amp; Why It Matters (UK Finance)</th>
                <th class="compact-hide-mobile">Publisher</th>
                <th class="compact-hide-mobile">Score</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              ${{filtered.map((item, rowIdx) => {{
                const isSaved = savedUrls.has(item.url);
                const effScore = getActiveScore(item);
                const newBadge = item.is_new ? '<span class="new-badge" style="margin-right:6px;">NEW</span>' : '';
                const urgencyBadge = urgencyBadgeHtml(effScore, item);
                return `
                  <tr class="${{animate ? 'row-in' : ''}}" style="--i:${{Math.min(rowIdx, 20)}}" data-card-id="${{item.id}}" onclick="openDrawer('${{item.id}}', event)">
                    <td>
                      <button class="icon-btn ${{isSaved ? 'saved' : ''}}" type="button" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" aria-label="Save story" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                    </td>
                    <td>
                      <span class="badge ${{badgeClass(effScore)}}">${{formatTagHtml(item.func_tag)}}</span>
                      ${{urgencyBadge}}
                    </td>
                    <td>
                      <a class="compact-headline" href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">
                        ${{newBadge}}${{escapeHtml(item.title)}}
                      </a>
                      <div class="compact-takeaway">${{escapeHtml(item.benefit)}}</div>
                    </td>
                    <td class="compact-hide-mobile">
                      <span class="pub-pill">
                        <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                        ${{escapeHtml(item.source)}}
                      </span>
                    </td>
                    <td class="compact-hide-mobile"><strong>${{effScore}}</strong>/100</td>
                    <td style="white-space:nowrap;color:var(--mute);" title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</td>
                  </tr>
                `;
              }}).join('')}}
            </tbody>
          </table>
        `;
        return;
      }}

      /* VIEW MODE 2: "BRIEFING" 5-MINUTE READING STREAM */
      if (currentView === 'briefing') {{
        container.className = 'briefing-stream swap-target';
        container.innerHTML = filtered.map((item, idx) => {{
          const isSaved = savedUrls.has(item.url);
          const effScore = getActiveScore(item);
          const newBadge = item.is_new ? '<span class="new-badge">NEW</span>' : '';
          const urgencyBadge = urgencyBadgeHtml(effScore, item);
          const numStr = String(idx + 1).padStart(2, '0');
          const summaryLine = item.summary
            ? `<div class="stream-bullet"><strong>Key Summary:</strong> ${{escapeHtml(item.summary)}}</div>`
            : '';
          return `
            <article class="stream-article" data-card-id="${{item.id}}" onclick="openDrawer('${{item.id}}', event)">
              <div class="card-top">
                <div class="tag-group">
                  <span class="stream-num">${{numStr}}</span>
                  <span class="cat-eyebrow ${{catClass(effScore)}}">${{formatTagHtml(item.func_tag)}}</span>
                  <span class="badge ${{badgeClass(effScore)}}">${{effScore}}/100</span>
                  ${{urgencyBadge}}
                  ${{newBadge}}
                </div>
                <div class="card-actions">
                  <button class="icon-btn" type="button" title="Copy story link" aria-label="Copy story link" onclick="shareById('${{item.id}}', event)">${{ICON_LINK}}</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" type="button" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" title="Save story" aria-label="Save story" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                </div>
              </div>
              <h3 class="stream-headline">
                <a href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              <div class="stream-bullets">
                ${{summaryLine}}
                <div class="stream-bullet"><strong>Why it matters (UK Finance):</strong> ${{escapeHtml(item.benefit)}}</div>
                <div class="stream-bullet"><strong>Action &amp; Governance:</strong> ${{escapeHtml(item.action_item)}}</div>
              </div>
              <div class="card-footer">
                <span class="pub-pill">
                  <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                  ${{escapeHtml(item.source)}} · ${{escapeHtml(formatRelativeTime(item.published_at))}}
                </span>
                <div class="footer-links">
                  <button class="quick-brief-btn" type="button" onclick="openDrawer('${{item.id}}', event)">Full Risk Brief</button>
                  <a class="read-link" href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">Read story <span class="arrow">↗</span></a>
                </div>
              </div>
            </article>
          `;
        }}).join('');
        return;
      }}

      /* VIEW MODE 1 (DEFAULT): 3-COLUMN ROUNDED-3XL EDITORIAL CARDS */
      container.className = 'cards-grid swap-target';
      container.innerHTML = filtered.map(item => {{
        const isSaved = savedUrls.has(item.url);
        const effScore = getActiveScore(item);
        const newBadge = item.is_new ? '<span class="new-badge">NEW</span>' : '';
        const urgencyBadge = urgencyBadgeHtml(effScore, item);
        const summaryHtml = item.summary
          ? `<p class="card-summary">${{escapeHtml(item.summary)}}</p>`
          : '';
        return `
          <article class="news-card ${{animate ? 'pre-reveal' : ''}}" data-card-id="${{item.id}}" onclick="openDrawer('${{item.id}}', event)">
            <div>
              <div class="card-top">
                <div class="tag-group">
                  <span class="cat-eyebrow ${{catClass(effScore)}}">${{formatTagHtml(item.func_tag)}}</span>
                  ${{urgencyBadge}}
                  ${{newBadge}}
                </div>
                <div class="card-actions">
                  <button class="icon-btn" type="button" title="Copy direct link" aria-label="Copy direct link" onclick="shareById('${{item.id}}', event)">${{ICON_LINK}}</button>
                  <button class="icon-btn ${{isSaved ? 'saved' : ''}}" type="button" data-save-id="${{item.id}}" aria-pressed="${{isSaved}}" title="Save story" aria-label="Save story" onclick="toggleSaveById('${{item.id}}', event)">${{ICON_BOOKMARK}}</button>
                </div>
              </div>
              <h3 class="card-title">
                <a href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
              </h3>
              ${{summaryHtml}}
            </div>
            <div>
              <div class="benefit-box ${{boxClass(effScore)}}">
                <div class="benefit-header">
                  <span class="benefit-label">${{FLAG_SVG}} Why It Matters</span>
                  <span class="score-meter-wrap">
                    <span>${{effScore}}/100</span>
                    <span class="score-info-trigger" title="Priority Score (1-100) measures direct relevance to UK CFOs, FCA regulatory compliance, and FP&A automation.">ⓘ</span>
                    <span class="score-bar"><span class="score-fill" style="width:${{effScore}}%"></span></span>
                  </span>
                </div>
                ${{escapeHtml(item.benefit)}}
              </div>
              <div class="card-footer">
                <span class="pub-pill">
                  <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                  ${{escapeHtml(item.source)}} · <span title="${{escapeHtml(item.published_at)}}">${{escapeHtml(formatRelativeTime(item.published_at))}}</span>
                </span>
                <div class="footer-links">
                  <button class="quick-brief-btn" type="button" onclick="openDrawer('${{item.id}}', event)">Brief</button>
                  <a class="read-link" href="${{safeUrl(item.url)}}" target="_blank" rel="noopener noreferrer">Read story <span class="arrow">↗</span></a>
                </div>
              </div>
            </div>
          </article>
        `;
      }}).join('');

      setupScrollReveal();
    }}

    function animateKpiCounters() {{
      document.querySelectorAll('.kpi-val[data-count]').forEach(el => {{
        const target = parseInt(el.getAttribute('data-count'), 10) || 0;
        const duration = 600;
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
        `*UK Finance & AI — Daily Executive Briefing (${{DATE_STR}})*`,
        `Live Dashboard: https://mhutt97.github.io/ai-news-daily/`,
        ``
      ];
      top5.forEach((it, idx) => {{
        lines.push(`${{idx + 1}}. *${{it.title}}* (${{it.source}} — ${{it.func_tag}})`);
        lines.push(`   ↳ Why it matters: ${{(it.benefit || '')}}`);
        lines.push(`   ↳ Next step: ${{(it.action_item || '')}}`);
        lines.push(`   ${{it.url}}`);
        lines.push(``);
      }});
      navigator.clipboard.writeText(lines.join('\\n')).then(() => {{
        showToast('✓ Copied Top 5 Briefing for Teams / Slack');
      }});
    }}

    function openEmailDraft() {{
      const top5 = getSortedItems().slice(0, 5);
      const subject = encodeURIComponent(`UK Finance & AI Executive Briefing — ${{DATE_STR}}`);
      let body = `UK FINANCE & AI — DAILY EXECUTIVE BRIEFING\\nDate: ${{DATE_STR}}\\nLive Dashboard: https://mhutt97.github.io/ai-news-daily/\\n\\n` +
        `TOP 5 STORIES & WHY THEY MATTER FOR UK FINANCE:\\n\\n`;
      top5.forEach((it, idx) => {{
        body += `${{idx + 1}}. ${{it.title}} [${{it.func_tag}}]\\n`;
        body += `Why it matters: ${{it.benefit}}\\n`;
        body += `Recommended action: ${{it.action_item}}\\n`;
        body += `Story: ${{it.url}}\\n\\n`;
      }});
      body += `Note: Algorithmic executive aggregation curated for internal UK finance discussion.`;
      window.location.href = `mailto:?subject=${{subject}}&body=${{encodeURIComponent(body)}}`;
    }}

    function copyDashboardUrl() {{
      const shareUrl = `${{window.location.origin}}${{window.location.pathname}}`;
      if (navigator.clipboard) {{
        navigator.clipboard.writeText(shareUrl).then(() => {{
          showToast('✓ Live Dashboard URL copied');
        }});
      }}
    }}

    function exportToCsv() {{
      const sorted = getSortedItems();
      const headers = [
        "Rank",
        "Priority Score",
        "Tier",
        "Area / Tag",
        "Title",
        "Executive Summary",
        "Why It Matters (UK Finance)",
        "Audit & FCA Governance Risk",
        "Recommended Action",
        "Publisher",
        "Category",
        "Published At",
        "URL"
      ];
      const rows = [headers.map(h => `"${{h.replace(/"/g, '""')}}"`).join(",")];
      sorted.forEach((it, idx) => {{
        const effScore = getActiveScore(it);
        const row = [
          idx + 1,
          effScore,
          it.tier || "",
          it.func_tag || "",
          it.title || "",
          it.summary || "",
          it.benefit || "",
          it.risk_angle || "",
          it.action_item || "",
          it.source || "",
          it.category || "",
          it.published_at || "",
          it.url || ""
        ];
        rows.push(row.map(val => `"${{String(val || '').replace(/"/g, '""')}}"`).join(","));
      }});
      const csvContent = "\\uFEFF" + rows.join("\\r\\n");
      const blob = new Blob([csvContent], {{ type: "text/csv;charset=utf-8;" }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const datePart = new Date().toISOString().slice(0, 10);
      link.setAttribute("href", url);
      link.setAttribute("download", `UK_Finance_AI_Briefing_${{datePart}}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      showToast("✓ Exported CSV Risk Register");
    }}

    function openShareModal() {{
      lastFocusedEl = document.activeElement;
      document.getElementById('shareModalBackdrop').classList.add('open');
    }}
    function closeShareModal() {{
      document.getElementById('shareModalBackdrop').classList.remove('open');
      if (lastFocusedEl && document.contains(lastFocusedEl)) lastFocusedEl.focus({{ preventScroll: true }});
    }}

    function toggleKbdModal() {{
      const modal = document.getElementById('kbdModalBackdrop');
      if (modal.classList.contains('open')) {{
        closeKbdModal();
      }} else {{
        lastFocusedEl = document.activeElement;
        modal.classList.add('open');
      }}
    }}
    function closeKbdModal() {{
      document.getElementById('kbdModalBackdrop').classList.remove('open');
      if (lastFocusedEl && document.contains(lastFocusedEl)) lastFocusedEl.focus({{ preventScroll: true }});
    }}

    function checkUrlHash() {{
      const hash = (window.location.hash || '').replace('#', '').trim();
      if (!hash) return;
      const item = ITEM_MAP.get(hash);
      if (!item) return;

      if (currentFilter !== 'all' || currentTopic !== 'all') {{
        currentFilter = 'all';
        currentTopic = 'all';
        document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-filter') === 'all'));
        document.querySelectorAll('.topic-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-topic') === 'all'));
        renderMain({{ animate: false }});
      }}

      setTimeout(() => {{
        const cardEl = document.querySelector(`[data-card-id="${{hash}}"]`);
        if (cardEl) {{
          cardEl.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
          cardEl.classList.remove('target-highlight');
          void cardEl.offsetWidth;
          cardEl.classList.add('target-highlight');
        }}
        openDrawer(hash);
      }}, 120);
    }}

    function syncThemeIcon(theme) {{
      const btn = document.getElementById('themeToggleBtn');
      if (btn) btn.innerHTML = theme === 'dark' ? ICON_SUN : ICON_MOON;
    }}

    function toggleTheme() {{
      const root = document.documentElement;
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      const apply = () => {{
        root.setAttribute('data-theme', next);
        localStorage.setItem('uk-fin-ai-theme', next);
        syncThemeIcon(next);
      }};
      if (REDUCED_MOTION) {{ apply(); return; }}
      if (document.startViewTransition) {{
        document.startViewTransition(apply);
        return;
      }}
      root.classList.add('theme-anim');
      apply();
      setTimeout(() => root.classList.remove('theme-anim'), 300);
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

    window.addEventListener('hashchange', checkUrlHash);

    window.addEventListener('keydown', (e) => {{
      const activeEl = document.activeElement;
      const isInput = activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA');

      if (e.key === 'Escape') {{
        if (document.getElementById('shareModalBackdrop').classList.contains('open')) {{
          closeShareModal();
          return;
        }}
        if (document.getElementById('kbdModalBackdrop').classList.contains('open')) {{
          closeKbdModal();
          return;
        }}
        if (activeDrawerId) {{
          closeDrawer();
          return;
        }}
        if (isInput) {{
          activeEl.blur();
          return;
        }}
      }}

      if (activeDrawerId && e.key === 'ArrowRight') {{
        stepDrawer(1);
        return;
      }}
      if (activeDrawerId && e.key === 'ArrowLeft') {{
        stepDrawer(-1);
        return;
      }}

      if (isInput) return;

      if (e.key === '/') {{
        e.preventDefault();
        const heroSearch = document.getElementById('heroSearchInput');
        const mainSearch = document.getElementById('searchInput');
        const targetInput = (window.scrollY < 320 && heroSearch) ? heroSearch : mainSearch;
        if (targetInput) targetInput.focus();
        return;
      }}

      if (e.key === '?' || (e.key === '/' && e.shiftKey)) {{
        e.preventDefault();
        toggleKbdModal();
        return;
      }}

      if (e.key === 's' || e.key === 'S') {{
        e.preventDefault();
        openShareModal();
        return;
      }}

      if (e.key === 'c' || e.key === 'C') {{
        e.preventDefault();
        copyTeamBriefing();
        return;
      }}

      if (e.key === 'e' || e.key === 'E') {{
        e.preventDefault();
        exportToCsv();
        return;
      }}

      if (e.key === 't' || e.key === 'T') {{
        e.preventDefault();
        toggleTheme();
        return;
      }}

      const navigableCards = Array.from(document.querySelectorAll('.cards-grid .news-card, .briefing-stream .stream-article, .compact-table tbody tr'));
      if (!navigableCards.length) return;

      if (e.key === 'j' || e.key === 'ArrowDown') {{
        e.preventDefault();
        selectedCardIndex = Math.min(selectedCardIndex + 1, navigableCards.length - 1);
        navigableCards.forEach((c, idx) => c.classList.toggle('kbd-selected', idx === selectedCardIndex));
        if (navigableCards[selectedCardIndex]) {{
          navigableCards[selectedCardIndex].scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}
        return;
      }}

      if (e.key === 'k' || e.key === 'ArrowUp') {{
        e.preventDefault();
        selectedCardIndex = Math.max(selectedCardIndex - 1, 0);
        navigableCards.forEach((c, idx) => c.classList.toggle('kbd-selected', idx === selectedCardIndex));
        if (navigableCards[selectedCardIndex]) {{
          navigableCards[selectedCardIndex].scrollIntoView({{ behavior: 'smooth', block: 'nearest' }});
        }}
        return;
      }}

      if (e.key === 'Enter' || e.key === 'o') {{
        if (selectedCardIndex >= 0 && navigableCards[selectedCardIndex]) {{
          e.preventDefault();
          navigableCards[selectedCardIndex].click();
        }}
      }}
    }});

    (function init() {{
      ['brandFlagSlot', 'heroFlagSlot', 'kpiFlagSlot', 'tabFlagSlot', 'footerFlagSlot'].forEach(slotId => {{
        const slot = document.getElementById(slotId);
        if (slot) slot.innerHTML = FLAG_SVG;
      }});

      const savedTheme = localStorage.getItem('uk-fin-ai-theme') || 'light';
      document.documentElement.setAttribute('data-theme', savedTheme);
      syncThemeIcon(savedTheme);

      document.getElementById('viewCardsBtn').classList.toggle('active', currentView === 'cards');
      document.getElementById('viewBriefingBtn').classList.toggle('active', currentView === 'briefing');
      document.getElementById('viewTableBtn').classList.toggle('active', currentView === 'table');

      updateSavedTabCount();
      updateDynamicMetrics();
      renderHero();
      renderMain();
      animateKpiCounters();
      setTimeout(checkUrlHash, 220);
    }})();
  </script>
</body>
</html>"""


def generate_dashboard_files(
    items: list[NewsItem], settings: Settings
) -> tuple[Path, list[dict[str, object]]]:
    """Generate docs/index.html and docs/data.json for the web dashboard."""
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    cards = prepare_prioritized_cards(items, settings)
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%B %d, %Y")
    updated_at_str = now_utc.strftime("%d %b %Y · %H:%M UTC")
    dashboard_html = build_dashboard_html(cards, today_str, updated_at=updated_at_str)

    index_path = DOCS_DIR / "index.html"
    data_path = DOCS_DIR / "data.json"
    index_path.write_text(dashboard_html, encoding="utf-8")
    data_path.write_text(json.dumps(cards, indent=2, ensure_ascii=False), encoding="utf-8")
    return index_path, cards
