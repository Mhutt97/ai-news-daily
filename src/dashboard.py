"""Interactive UK Finance & AI News Dashboard generator, 7-day rolling archive, and Finance Benefit prioritization engine."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import html
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request

from src.config import DIGESTS_DIR, PROJECT_ROOT, Settings
from src.sources import NewsItem

DOCS_DIR = PROJECT_ROOT / "docs"
DEFAULT_DASHBOARD_URL = "https://mhutt97.github.io/ai-news-daily/"
RETENTION_DAYS = 7

PUBLISHER_DOMAINS: dict[str, str] = {
    "deloitte": "deloitte.com",
    "ey": "ey.com",
    "pwc": "pwc.co.uk",
    "kpmg": "kpmg.com",
    "bdo": "bdo.co.uk",
    "grant thornton": "grantthornton.co.uk",
    "rsm": "rsmuk.com",
    "mazars": "forvismazars.com",
    "icaew": "icaew.com",
    "acca": "accaglobal.com",
    "fca": "fca.org.uk",
    "bank of england": "bankofengland.co.uk",
    "uk finance": "ukfinance.org.uk",
    "accountancy today": "accountancytoday.co.uk",
    "accountancy age": "accountancyage.com",
    "accountingweb": "accountingweb.co.uk",
    "international accounting bulletin": "internationalaccountingbulletin.com",
    "scottish financial news": "scottishfinancialnews.com",
    "citywire": "citywire.com",
    "ff news": "ffnews.com",
    "fintech global": "fintech.global",
    "fintech futures": "fintechfutures.com",
    "fintech magazine": "fintechmagazine.com",
    "finextra": "finextra.com",
    "financial times": "ft.com",
    "ibs intelligence": "ibsintelligence.com",
    "credit connect": "credit-connect.co.uk",
    "pei private equity": "privateequityinternational.com",
    "private equity international": "privateequityinternational.com",
    "the banker": "thebanker.com",
    "insurance business": "insurancebusinessmag.com",
    "yahoo finance": "uk.finance.yahoo.com",
    "investing.com": "uk.investing.com",
    "the globe and mail": "theglobeandmail.com",
    "wsj": "wsj.com",
    "reuters": "reuters.com",
    "bloomberg": "bloomberg.com",
    "cnbc": "cnbc.com",
    "bbc": "bbc.co.uk",
    "the guardian": "theguardian.com",
    "telegraph": "telegraph.co.uk",
    "the times": "thetimes.com",
    "city a.m.": "cityam.com",
    "city am": "cityam.com",
    "silicon uk": "silicon.co.uk",
    "digit.fyi": "digit.fyi",
    "tech.eu": "tech.eu",
    "sifted": "sifted.eu",
    "computer weekly": "computerweekly.com",
    "computing": "computing.co.uk",
    "the register": "theregister.com",
    "enterprise times": "enterprisetimes.co.uk",
    "it brief uk": "itbrief.co.uk",
    "seeking alpha": "seekingalpha.com",
    "going concern": "goingconcern.com",
    "tokenpost": "tokenpost.com",
    "openai": "openai.com",
    "google": "blog.google",
    "deepmind": "deepmind.google",
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
    s_clean = (source_name or "").strip().lower()
    for key, dom in PUBLISHER_DOMAINS.items():
        if key in s_clean:
            return dom
    if re.match(r"^[a-z0-9.-]+\.[a-z]{2,}$", s_clean):
        return s_clean.lstrip("www.")
    try:
        parsed = urllib.parse.urlparse(article_url)
        if parsed.netloc and "news.google.com" not in parsed.netloc:
            return parsed.netloc.lstrip("www.")
    except Exception:
        pass
    return "ukfinance.org.uk"


def clean_article_title(raw_title: str) -> str:
    """Strip noisy trailing site pipes, bylines, and broken separators from headlines."""
    t = html.unescape(raw_title or "").strip()
    t = re.sub(r"\s+\|\s+(?:Inside FinTech|Global law firm|ETIH EdTech News).*$", "", t, flags=re.I)
    t = re.sub(r"\s+By\s+Investing\.com\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+-\s+WSJ\s*$", "", t, flags=re.I)
    t = re.sub(r"\s+-\s*$", "", t).strip()
    return t


def clean_summary_text(raw_summary: str, title: str = "") -> str:
    """Clean and normalize raw feed descriptions before executive synthesis."""
    text = (raw_summary or "").strip()
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"^\[\d+\s+upvotes?\]\s*", "", text, flags=re.I)
    text = re.sub(r"\s*submitted by\s+/u/\S+.*$", "", text, flags=re.I)
    text = re.sub(r"^\d+\s+points?\s*·\s*\d+\s+comments?\s+on\s+HN.*$", "", text, flags=re.I)
    text = re.sub(
        r"^This story originally appeared in The Algorithm,\s*our weekly[^.]*\.\s*",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"^On Equity,\s*we discuss\s+", "Examines ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    if title and text.lower().startswith(title.lower()[:32]):
        return ""
    return text


def is_noisy_outlier(title: str, source: str) -> bool:
    """Filter out generic stock-index chart pages, RNS director share notices, or promo stubs."""
    t_low = clean_article_title(title).lower()
    if re.search(r"\(\^[a-z0-9]+\)\s*charts,\s*data\s*and\s*news", t_low):
        return True
    if source and re.search(r"[\uac00-\ud7af\u4e00-\u9fff]", source):
        return True
    if re.search(
        r"\b(sip shares|cfo share purchase|updates share capital|director/pdmr shareholding|total voting rights)\b",
        t_low,
    ):
        return True
    if re.search(
        r"^(more in squawk box|news from the week beginning|midterm elections \d{4}: all the news|weekly recap: q\d profit .* buyback)",
        t_low,
    ):
        return True
    if re.search(
        r"\b(days left: how techcrunch founder summit|halloween costumes for tech nerds|nemotron-halloween)\b",
        t_low,
    ):
        return True
    return False


def _extract_article_signals(item: NewsItem) -> dict[str, str]:
    """Extract structured semantic entities, metrics, and subject phrases from an article."""
    title = clean_article_title(item.title)
    source = (item.source or "Curated Source").strip()
    clean_raw = clean_summary_text(item.summary, title)

    stats = re.findall(
        r"(?:\£\d+(?:\.\d+)?\s*(?:bn|billion|m|million|k)?|(?:USD\s*)?\$\d+(?:\.\d+)?\s*(?:T|trillion|B|bn|billion|M|m|million|k)?|\€\d+(?:\.\d+)?\s*(?:bn|billion|m|million|k)?|\d+(?:\.\d+)?%|\b(?:Nine in ten|\d{1,3},\d{3}\s+(?:staff|employees)|29\s+new\s+partners|seven\s+acquisitions|April\s+2027|iOS\s+\d+\.\d+|v\d+\.\d+(?:\.\d+)?)\b)",
        f"{title} {clean_raw}",
        flags=re.I,
    )
    stat_str = stats[0].strip() if stats else ""

    prefix = ""
    rest = title
    if ":" in title:
        p_cand, _, r_cand = title.partition(":")
        if 2 <= len(p_cand.strip()) <= 42 and r_cand.strip():
            prefix = p_cand.strip()
            rest = r_cand.strip()

    actor = prefix
    if not actor:
        verb_split = re.split(
            r"\s+(?:urges|warns|launches|unveils|raises|secures|backs|promotes|hits|expands|swings|clamps|appoints|seeks|declares|doubles|sue|helps|brings|identifies|says|announces|introduces|pitches|weighs|allows|shifts|turns|is|are|will|can|could|might)\b",
            title,
            maxsplit=1,
            flags=re.I,
        )
        if len(verb_split) == 2 and 3 <= len(verb_split[0].strip()) <= 46:
            actor = re.sub(r"^(?:How|Why|When|Introducing|Announcing|Preparing|Rewarding)\s+", "", verb_split[0].strip(), flags=re.I).strip()
        if not actor or len(actor) < 3:
            words = re.sub(r"^(?:How|Why|When|Introducing|Announcing|Welcome)\s+", "", title, flags=re.I).split()
            actor = " ".join(words[:5]).rstrip(",:;–—-")

    focus_words = re.sub(r"^['\"“”‘’]+|['\"“”‘’]+$", "", rest).strip()
    if focus_words and focus_words[0].isupper() and not re.match(r"^(?:UK|US|AI|FCA|BoE|PRA|HMRC|EY|PwC|KPMG|BDO|LLM|LLMs|CLI|GUI|MCP|SVD|AWS|VW|CEO|CFO)\b", focus_words):
        focus_lower = focus_words[0].lower() + focus_words[1:]
    else:
        focus_lower = focus_words

    return {
        "title": title,
        "source": source,
        "clean_raw": clean_raw,
        "stat": stat_str,
        "prefix": prefix,
        "rest": rest,
        "actor": actor,
        "focus_lower": focus_lower,
    }


def _polish_executive_summary(
    sig: dict[str, str],
    category: str,
    synthesized_fallback: str,
    context_extension: str,
) -> str:
    """Ensure every article has a complete, multi-sentence executive summary free of truncation."""
    raw = sig["clean_raw"]
    if not raw:
        return synthesized_fallback

    # If the raw feed snippet is already our synthesized summary (from re-hydration), return as-is
    if len(raw) >= 140 and not raw.endswith("…") and not raw.endswith("..."):
        return raw

    # Clean trailing mid-sentence ellipsis truncation from RSS/ArXiv snippets
    cleaned = raw
    if cleaned.endswith("…") or cleaned.endswith("..."):
        cleaned = re.sub(r"\s*(?:…|\.\.\.)$", "", cleaned).strip()
        # Trim back to last complete clause or word boundary and close cleanly
        last_punct = max(cleaned.rfind(". "), cleaned.rfind("; "))
        if last_punct > 75:
            cleaned = cleaned[: last_punct + 1].strip()
        else:
            cleaned = re.sub(r"\s+\b(?:and|or|the|a|an|to|in|of|for|with|by|on|at|from|that|which|as|is|are|was|were|be)$", "", cleaned, flags=re.I).strip()
            if not cleaned.endswith("."):
                cleaned += "."

    if not cleaned.endswith((".", "!", "?")):
        cleaned += "."

    # For research papers where the truncated abstract didn't state the title's framework
    if category == "Research Papers" and sig["prefix"] and sig["prefix"].lower() not in cleaned.lower():
        return f"Introduces {sig['prefix']}, a research framework addressing {sig['focus_lower']}. {cleaned}"

    # If the feed teaser is short (< 130 chars), append the article-specific context extension
    if len(cleaned) < 130:
        return f"{cleaned} {context_extension}"

    return cleaned


def _synthesize_research_and_community(
    item: NewsItem, sig: dict[str, str], text: str
) -> dict[str, object] | None:
    """Synthesize article-specific executive summary, benefit, and actionable outcome for Research & Community items."""
    title = sig["title"]
    source = sig["source"]
    actor = sig["prefix"] or sig["actor"]
    focus = sig["focus_lower"]

    if item.category == "Research Papers":
        if "earnings forecasting" in text or "epsbench" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Researchers introduce {actor}, an evaluation benchmark testing how accurately LLM agents synthesize financial statements, macroeconomic signals, and earnings transcripts to forecast quarterly corporate EPS.",
                f"Evaluates multi-step financial reasoning and earnings-per-share (EPS) prediction accuracy across real-world corporate reporting periods.",
            )
            return {
                "score": 82,
                "tier": "Finance Ops & Productivity",
                "func_tag": "🔬 Financial AI Benchmark",
                "summary": summary,
                "benefit": f"FP&A & Equity Forecasting Benchmark ({actor}): Directly tests whether autonomous LLM agents can connect historical financial statements with forward-looking guidance to predict quarterly earnings.",
                "action_item": f"Benchmark your FP&A team's internal forecasting prompts against {actor}'s multi-quarter financial statement and transcript evaluation criteria before relying on LLM variance projections.",
                "risk_angle": f"Unverified LLM earnings forecasts suffer from look-ahead bias and numerical hallucination unless grounded in audited XBRL filings and deterministic spreadsheet formulas.",
            }

        if "broken on arrival" in text or ("quantized" in text and "registries" in text):
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Empirical study ({actor}) auditing public model registries reveals that a significant share of community-uploaded quantized LLM artifacts suffer from silent weight corruption, broken tokenizers, or degraded reasoning accuracy.",
                f"Demonstrates how unverified quantized model weights in public repositories introduce silent numerical and reasoning failures into enterprise deployments.",
            )
            return {
                "score": 69,
                "tier": "General AI & Research",
                "func_tag": "🔬 AI Supply-Chain Audit",
                "summary": summary,
                "benefit": f"Model Registry Supply-Chain Integrity ({actor}): Warns enterprise engineering and risk teams that downloading pre-quantized open-weight models without checksum and eval verification risks silent accuracy collapse.",
                "action_item": f"Mandate automated golden-dataset regression testing and cryptographic hash verification before promoting any quantized open-weight LLM from public registries into internal sandboxes.",
                "risk_angle": f"Silent degradation in quantized model weights can corrupt downstream financial document extraction or classification without triggering runtime error logs.",
            }

        if "prompt injection" in text or "heads of security" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Introduces {actor}, a defensive architecture that trains specialized attention gates inside transformer models to detect and neutralize indirect prompt-injection attacks embedded in untrusted documents.",
                f"Shows how learned attention-head gating can isolate malicious instructions hidden inside retrieved enterprise documents and emails.",
            )
            return {
                "score": 68,
                "tier": "General AI & Research",
                "func_tag": "🔬 AI Security Research",
                "summary": summary,
                "benefit": f"Indirect Prompt-Injection Defense ({actor}): Relevant to UK finance teams connecting RAG copilots to external supplier invoices, PDFs, or emails that could harbour hidden adversarial instructions.",
                "action_item": f"Incorporate indirect prompt-injection test cases—such as adversarial text hidden in sample vendor invoices—into your pre-deployment security red-teaming for finance RAG tools.",
                "risk_angle": f"AI assistants that ingest external PDFs or emails without prompt-injection filtering can be hijacked into exfiltrating sensitive financial ledger data.",
            }

        if "differentially private" in text or "privacy amplification" in text or "private filtering" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Presents {actor} ({source}), establishing tighter mathematical bounds for differential privacy when training or querying models on sensitive datasets with observable counts or outlier filtering.",
                f"Advances formal privacy-budget accounting so organizations can train analytical models on sensitive records without leaking individual data points.",
            )
            return {
                "score": 66,
                "tier": "General AI & Research",
                "func_tag": "🔬 Privacy & Audit Research",
                "summary": summary,
                "benefit": f"Mathematical Privacy Guarantees ({actor}): Provides data-science and compliance teams with stronger differential-privacy noise calibration when analyzing sensitive customer or payroll datasets.",
                "action_item": f"Share {actor}'s differential-privacy calibration techniques with your data engineering lead when scoping analytics over UK GDPR-protected customer or HR datasets.",
                "risk_angle": f"Standard anonymization of financial datasets often fails re-identification tests unless backed by formal differential-privacy sensitivity bounds.",
            }

        if "loss of control" in text or "harmful manipulation" in text or "deepseek" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Safety researchers evaluate {title}, stress-testing frontier open-weight reasoning capabilities against autonomous loss-of-control scenarios, deceptive alignment, and persuasive manipulation benchmarks.",
                f"Provides empirical red-team evidence on how high-capability open-weight models behave under adversarial autonomy and manipulation prompts.",
            )
            return {
                "score": 67,
                "tier": "General AI & Research",
                "func_tag": "🔬 Frontier Safety Eval",
                "summary": summary,
                "benefit": f"Frontier Model Red-Teaming ({actor}): Gives enterprise AI governance committees an independent safety scorecard before approving open-weight frontier models for internal use.",
                "action_item": f"Require model-risk documentation to include independent manipulation and loss-of-control evaluation results before whitelisting frontier models like DeepSeek V4.1 on corporate infrastructure.",
                "risk_angle": f"Deploying high-autonomy models without behavioural guardrails increases exposure to unauthorized tool execution and social-engineering manipulation.",
            }

        if "memory fails" in text or "group decisions" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Investigates how multi-agent LLM workflows fail when complex discussion histories are compressed into short memory summaries ({title}), causing critical minority evidence to be discarded.",
                f"Demonstrates why naive context summarization in multi-agent systems systematically drops rare but decisive risk signals.",
            )
            return {
                "score": 65,
                "tier": "General AI & Research",
                "func_tag": "🔬 Multi-Agent Reliability",
                "summary": summary,
                "benefit": f"Multi-Agent Memory Fidelity ({actor}): Crucial warning for enterprise architects building multi-agent diligence or audit workflows where compressed context summaries can erase material exceptions.",
                "action_item": f"Configure enterprise RAG and multi-agent workflows to preserve verbatim citations to anomalous financial footnotes rather than relying solely on rolling LLM memory summaries.",
                "risk_angle": f"Lossy memory compression in automated review pipelines can drop rare fraud indicators or covenant breach clauses during multi-stage summarization.",
            }

        if "mcp" in text or "cli" in text or "coworkos" in text or "webharbor" in text or "teammates" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Research study '{title}' ({source}) evaluates how autonomous language agents interact with enterprise execution environments, comparing tool-calling reliability, human collaboration, and interface harnesses.",
                f"Quantifies how interface design (such as Model Context Protocol vs. CLI or GUI harnesses) alters agent execution accuracy and error recovery.",
            )
            return {
                "score": 64,
                "tier": "General AI & Research",
                "func_tag": "🔬 Agent Systems Research",
                "summary": summary,
                "benefit": f"Enterprise Agent Harness Design ({actor}): Shows IT and automation leads how structured tool interfaces (MCP/CLI) materially affect agent reliability on multi-step operational workflows.",
                "action_item": f"Use {actor}'s evaluation methodology to test whether your internal AI agents perform more reliably via structured API/MCP connectors than via brittle browser-GUI automation.",
                "risk_angle": f"Agents operating across loosely constrained CLI or web interfaces without deterministic schema validation can execute unintended state changes in enterprise systems.",
            }

        if "instruction capacity" in text or "controlled load" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Examines {title}, measuring how language model compliance degrades as system prompts stack multiple simultaneous formatting, compliance, and analytical constraints.",
                f"Identifies the threshold where overloaded system prompts cause LLMs to silently drop secondary instructions and guardrails.",
            )
            return {
                "score": 63,
                "tier": "General AI & Research",
                "func_tag": "🔬 Prompt Reliability Paper",
                "summary": summary,
                "benefit": f"System-Prompt Load Limits ({actor}): Explains why stuffing dozens of accounting rules into a single monolithic prompt causes LLMs to silently ignore edge-case compliance constraints.",
                "action_item": f"Refactor complex finance prompts into modular, single-purpose verification steps rather than overloading a single prompt with more than 8–10 simultaneous rules.",
                "risk_angle": f"Overloaded prompts degrade predictably under high instruction density, causing silent omission of mandatory compliance checks.",
            }

        if "quantization" in text or "svd" in text or "attention" in text or "token" in text or "efficient" in text or "distillation" in text or "muon" in text or "looped" in text:
            summary = _polish_executive_summary(
                sig,
                item.category,
                f"Technical paper '{title}' from {source} proposes an algorithmic optimization for {focus}, reducing transformer compute overhead while preserving downstream benchmark accuracy.",
                f"Targets lower memory bandwidth and faster token generation across long-context and multimodal inference workloads.",
            )
            return {
                "score": 60,
                "tier": "General AI & Research",
                "func_tag": "🔬 Model Efficiency Paper",
                "summary": summary,
                "benefit": f"Inference Efficiency & Compute Economics ({actor}): Tracks algorithmic advances in {focus[:55]} that lower the cost of running long-context enterprise LLMs.",
                "action_item": f"Have your ML/platform engineering team track {actor} when evaluating low-latency model serving or fine-tuning configurations for long-document enterprise workloads.",
                "risk_angle": f"Aggressive model compression, sparse attention, or distillation must be validated against domain-specific financial benchmarks to ensure numerical precision is preserved.",
            }

        summary = _polish_executive_summary(
            sig,
            item.category,
            f"Published via {source}, '{title}' investigates {focus}, introducing new methodology and empirical benchmarks for next-generation foundation models.",
            f"Contributes technical benchmarks and architectural insights for advancing reliability in {focus[:60]}.",
        )
        return {
            "score": 56,
            "tier": "General AI & Research",
            "func_tag": "🔬 Foundation R&D Paper",
            "summary": summary,
            "benefit": f"Foundation Model R&D ({actor}): Advances academic understanding of {focus[:65]}, informing next-generation multimodal and reasoning architectures.",
            "action_item": f"Log {actor} in your technical R&D radar for quarterly review by data-science leads; no immediate finance workflow changes required.",
            "risk_angle": f"Early-stage academic methods like {actor} require extensive enterprise hardening and reproducibility checks before production adoption.",
        }

    if item.category == "Hacker News & Reddit":
        summary = _polish_executive_summary(
            sig,
            item.category,
            f"Community engineering discussion on {source} examining '{title}', where practitioners benchmark real-world deployment trade-offs, latency, and implementation pitfalls.",
            f"Captures frontline developer feedback on production reliability, cost, and architectural trade-offs for {focus[:60]}.",
        )
        return {
            "score": 52,
            "tier": "General AI & Research",
            "func_tag": "💬 Practitioner Pulse",
            "summary": summary,
            "benefit": f"Practitioner Engineering Signal ({actor}): Surfaces candid developer benchmarks on '{title[:55]}' before vendor marketing narratives settle.",
            "action_item": f"Share this {source} practitioner thread on '{title[:50]}' with your engineering lead to sanity-check vendor claims against real production experience.",
            "risk_angle": f"Community workarounds and open-source scripts discussed on {source} must undergo formal security and license review before enterprise use.",
        }

    return None

def _synthesize_uk_finance_intel(
    item: NewsItem, sig: dict[str, str], text: str
) -> dict[str, object] | None:
    """Synthesize bespoke executive summary, benefit, and actionable outcome for High-Priority UK Finance items."""
    title = sig["title"]
    source = sig["source"]
    actor = sig["prefix"] or sig["actor"]
    focus = sig["focus_lower"]
    stat = sig["stat"]

    if re.search(r"\b(fca|financial conduct authority|bank of england|boe|pra)\b", text):
        if "customer needs" in text or "fintechs to design" in text:
            return {
                "score": 99,
                "tier": "High UK Finance Impact",
                "func_tag": "🏛️ FCA & Consumer Duty",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Reporting via {source} examines Financial Conduct Authority (FCA) guidance urging UK fintechs and financial firms to anchor AI system design around measurable customer needs rather than cost automation alone. The regulator emphasises that AI-driven product and credit workflows must satisfy Consumer Duty obligations for fair value, explainability, and vulnerable-customer protection.",
                    f"Reinforces that FCA supervisory reviews evaluate fintech AI models against Consumer Duty outcome standards.",
                ),
                "benefit": f"FCA Consumer Duty AI Design ({source}): Signals that the FCA evaluates AI deployments in UK financial services through verifiable Consumer Duty customer outcomes rather than prescriptive model rules.",
                "action_item": "Require product and finance leads to complete a Consumer Duty AI Outcome Assessment—documenting customer fairness metrics and human escalation paths—before launching any customer-facing model.",
                "risk_angle": "Deploying customer-facing AI without documented Consumer Duty outcome testing exposes UK regulated firms to FCA skilled-person reviews (s166) and remediation mandates.",
            }
        if "small advice firms" in text or "really encouraged" in text:
            return {
                "score": 98,
                "tier": "High UK Finance Impact",
                "func_tag": "🏛️ FCA & Advice Firms",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Coverage from {source} reports that the Financial Conduct Authority (FCA) has expressed positive encouragement regarding how smaller UK wealth management and financial advice firms are adopting AI assistants. Supervisors noted that using AI to automate meeting transcription, fact-find summaries, and file reviews boosts adviser productivity while preserving qualified human sign-off.",
                    f"Highlights proportionate FCA support for back-office AI productivity in regulated advice practices.",
                ),
                "benefit": f"Proportionate FCA Support for Adviser AI ({source}): Demonstrates that the FCA actively backs administrative AI adoption in smaller regulated UK practices when adviser suitability sign-off remains intact.",
                "action_item": "Prioritise low-risk administrative AI workflows—such as meeting transcription, fact-find indexing, and draft working papers—subject to mandatory human reviewer sign-off.",
                "risk_angle": "Even in back-office advice workflows, staff must verify AI-generated client summaries against primary records to prevent suitability errors.",
            }
        if "financial crime 360" in text or "crypto" in text or "aml" in text or "crime" in text:
            return {
                "score": 98,
                "tier": "High UK Finance Impact",
                "func_tag": "🏛️ FCA & Financial Crime",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports from the Financial Crime 360 summit in London, where senior supervisors from the FCA and Bank of England joined UK banking and compliance leaders to address AI-driven fraud, synthetic identity detection, and real-time AML monitoring. Speakers stressed pairing machine-learning anomaly detection with explainable audit trails for regulatory examinations.",
                    f"Aligns UK financial-crime and treasury controls with FCA and Bank of England expectations on countering AI-enabled payment fraud.",
                ),
                "benefit": f"FCA & BoE FinCrime Supervision ({source}): Highlights how UK regulators expect treasury and compliance teams to counter AI-generated payment scams with real-time behavioural analytics and explainable AML rules.",
                "action_item": "Conduct a joint review between Treasury and Financial Crime teams to test supplier bank-mandate verification and payment anomaly controls against synthetic voice and invoice fraud.",
                "risk_angle": "Black-box AML or fraud-scoring models that cannot explain why transactions were flagged or cleared fail FCA financial-crime auditability standards.",
            }
        if "lessons" in text and "survey" in text:
            return {
                "score": 99,
                "tier": "High UK Finance Impact",
                "func_tag": "🏛️ FCA & BoE Survey",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Legal analysis from {source} distils the core governance lessons from the joint Bank of England and FCA 2026 machine-learning survey across UK banking, insurance, and investment firms. The briefing highlights rapid growth in third-party foundation model usage alongside heightened supervisory scrutiny over data lineage, third-party concentration, and SM&CR accountability.",
                    f"Provides legal and compliance teams with a benchmark of FCA and PRA expectations following the 2026 sector survey.",
                ),
                "benefit": f"BoE & FCA 2026 Governance Lessons ({source}): Gives UK CFOs, CROs, and general counsel a legal readout on where UK regulators see governance gaps in third-party AI model deployment.",
                "action_item": "Map your firm's active AI use cases against the BoE/FCA 2026 survey governance criteria and assign a named Senior Management Function (SMF) owner to each production workflow.",
                "risk_angle": "Unclear allocation of SM&CR senior manager responsibility for automated financial or compliance models is a primary trigger for FCA governance intervention.",
            }
        return {
            "score": 99,
            "tier": "High UK Finance Impact",
            "func_tag": "🏛️ FCA & Regulation",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Global law firm {source} examines findings from the Bank of England and FCA survey showing accelerating AI adoption across UK financial services. While institutions report strong productivity gains in back-office operations and risk analytics, regulators flag growing systemic reliance on a concentrated group of cloud and frontier LLM providers.",
                f"Tracks how expanding UK financial-services AI adoption intersects with PRA and FCA operational resilience rules.",
            ),
            "benefit": f"Systemic Third-Party & FCA Oversight ({source}): Confirms that as AI moves into core UK financial infrastructure, supervisory reviews will focus heavily on operational resilience and Critical Third Party (CTP) concentration.",
            "action_item": "Update your Outsourcing and Critical Third Party (CTP) register to inventory all external LLM APIs, cloud AI endpoints, and embedded SaaS AI dependencies across finance and operations.",
            "risk_angle": "Concentrated reliance on a single foundation model vendor without tested fallback procedures violates PRA/FCA operational resilience expectations.",
        }

    if re.search(r"\b(cci|disclosure|consumer duty|frc|icaew|acca|hmrc|vat|reverse charge|tax)\b", text):
        if "reverse charge" in text or "april 2027" in text:
            return {
                "score": 96,
                "tier": "High UK Finance Impact",
                "func_tag": "🧾 UK VAT & HMRC",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Indirect-tax specialist {source} details upcoming UK VAT reverse-charge rule changes taking effect in April 2027 for supplies received from overseas vendors. The reform alters cross-border B2B place-of-supply and self-accounting rules, requiring UK VAT-registered businesses to update ERP tax determination engines and AP invoice workflows.",
                    f"Outlines ERP tax-code and cross-border supplier accounting adjustments required ahead of April 2027.",
                ),
                "benefit": f"April 2027 UK VAT Reverse-Charge Reform ({source}): Gives UK tax directors and financial controllers early visibility into cross-border VAT accounting changes impacting overseas software and service suppliers.",
                "action_item": "Schedule an ERP tax-code and vendor-master audit with your Indirect Tax lead to flag all non-UK supplier accounts requiring reverse-charge reconfiguration before April 2027.",
                "risk_angle": "Misconfigured ERP VAT reverse-charge codes on overseas SaaS and advisory invoices create systematic HMRC under-declaration and penalty exposure.",
            }
        if "taxready" in text or "fixed price per return" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🧾 Managed Tax AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Accounting outsourcing specialist QX Global Group ({source}) has launched 'QX TaxReady', an AI-powered managed tax preparation service offering accounting firms a single fixed price per return year-round. The platform pairs automated source-document extraction and workpaper population with dedicated tax reviewers to eliminate peak-season capacity bottlenecks.",
                    f"Demonstrates how AI document extraction is shifting outsourced tax preparation toward fixed-fee unit economics.",
                ),
                "benefit": "Fixed-Price Managed Tax Economics (QX TaxReady): Illustrates how AI workflow automation is shifting accounting firm tax outsourcing from hourly billing to predictable fixed-price unit economics per filing.",
                "action_item": "Benchmark your practice or group tax function's internal cost-per-return and seasonal contractor spend against fixed-fee AI-assisted preparation workflows ahead of the next filing cycle.",
                "risk_angle": "When utilizing outsourced or AI-managed tax preparation services, firms must verify cross-border taxpayer data encryption and engagement-letter disclosures.",
            }
        if "black ore" in text or "small accounting firms" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🧾 Practice Tax AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that fintech provider Black Ore has rolled out a dedicated AI tax automation platform designed for small and mid-tier accounting practices. The tool automates client tax-document ingestion, schedule categorization, and draft return assembly so smaller firms can expand high-margin advisory work without adding compliance headcount.",
                    f"Shows how turnkey AI tax automation lowers the technology barrier for smaller accounting practices.",
                ),
                "benefit": f"SME Tax Practice Automation (Black Ore · {source}): Shows how purpose-built AI tax engines enable smaller practices to compress return-preparation turnaround times and compete with larger networks.",
                "action_item": "Pilot automated source-document ingestion and draft tax-workpaper generation on a sample cohort of standard client returns to measure reviewer correction rates and hours saved.",
                "risk_angle": "Automated tax-return population requires strict source-document cross-referencing controls to prevent OCR or classification errors from reaching tax filings.",
            }
        return {
            "score": 96,
            "tier": "High UK Finance Impact",
            "func_tag": "📊 UK Tax & Reporting",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Reporting via {source} examines '{title}', detailing how evolving UK tax, statutory disclosure, and regulatory reporting standards are reshaping compliance workflows for corporate finance teams.",
                f"Highlights practical compliance and automated filing controls for UK finance and tax practitioners.",
            ),
            "benefit": f"UK Statutory & Tax Compliance ({actor}): Shows how UK finance teams can align mandatory disclosure and tax reporting workflows with evolving regulatory standards.",
            "action_item": f"Review '{title[:55]}' with your Head of Tax and Financial Controller to verify that current ERP reporting templates and filing calendars reflect the latest rules.",
            "risk_angle": "Manual spreadsheet bridges in statutory and tax reporting remain a primary source of filing adjustments and compliance audit findings.",
        }

    if "govern the ai they buy" in text or ("ethics" in text or "governance" in text or "who’s really in charge" in text or "whos really in charge" in text):
        if "anthropic" in text and "ipo" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ AI Vendor Governance",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} examines Anthropic's complex corporate governance structure ahead of its anticipated IPO, analyzing the tension between its Long-Term Benefit Trust, public shareholders, and strategic cloud backers like Amazon. Enterprise customers rely on this governance balance for long-term model safety, IP indemnification, and API stability.",
                    f"Breaks down how Anthropic's dual-purpose board and Long-Term Benefit Trust will govern commercial priorities post-IPO.",
                ),
                "benefit": f"Frontier Vendor Corporate Governance (Anthropic IPO · {source}): Helps enterprise procurement and risk leaders evaluate how post-IPO shareholder pressures could affect Anthropic's safety commitments and enterprise SLA terms.",
                "action_item": "Review contractual change-of-control, model-deprecation notice periods, and IP indemnity clauses in your enterprise LLM agreements ahead of frontier lab IPO transitions.",
                "risk_angle": "Governance shifts at frontier AI vendors can alter model retention policies, safety guardrails, or enterprise pricing tiers mid-contract.",
            }
        return {
            "score": 95,
            "tier": "High UK Finance Impact",
            "func_tag": "🛡️ SaaS AI Governance",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Analysis from {source} ('{title}') challenges whether UK enterprises hold verifiable audit evidence demonstrating effective governance over third-party AI embedded in procured SaaS platforms. While boards maintain high-level AI policies on paper, many organisations lack technical visibility into how vendor models process corporate financial data or log automated decisions.",
                f"Highlights the assurance gap between boardroom AI policies and technical oversight of bought-in SaaS AI features.",
            ),
            "benefit": f"Procured SaaS AI Assurance ({source}): Directly impacts UK CFOs, procurement heads, and internal auditors who sign off on ERP, spend-management, and FP&A renewals bundling third-party AI.",
            "action_item": "Add a mandatory Vendor AI Governance & Data Lineage Questionnaire to finance software procurement and renewal checklists, requiring zero-training attestations and sub-processor disclosure.",
            "risk_angle": "Procuring SaaS platforms with embedded AI without contractual audit rights leaves UK firms unable to evidence control effectiveness to external auditors or regulators.",
        }

    if re.search(
        r"\b(internal auditor|internal auditors|external audit|kpmg|deloitte|pwc|ey|bdo|grant thornton|rsm)\b",
        text,
    ):
        if "3.86bn" in text or "partner profits" in text:
            return {
                "score": 96,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ Big Four Financials",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that Big Four firm EY UK achieved record annual revenue of £3.86bn alongside a 10% increase in average distributable profit per partner. Growth was propelled by corporate demand for AI transformation advisory, tax structuring, and financial-services assurance across the UK market.",
                    f"Quantifies Big Four fee growth (£3.86bn) and partner profitability across UK audit and AI advisory.",
                ),
                "benefit": f"Big Four Fee & Margin Benchmark (£3.86bn · {source}): Signals resilient UK enterprise demand for technology-enabled audit, tax, and AI transformation advisory despite wider economic headwinds.",
                "action_item": "Review your external audit and Big Four advisory fee proposals for FY26/27, requesting transparent rate cards where AI-assisted audit tooling reduces manual sampling hours.",
                "risk_angle": "Rising Big Four partner profitability alongside AI automation underscores the need for audit committees to verify that automated audit efficiencies translate into deeper control testing.",
            }
        if "annual results 2026" in text and "ey" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ Big Four AI Strategy",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"EY UK's official 2026 annual results statement details how the firm's £3.86bn revenue performance was underpinned by sustained capital investment in proprietary AI assurance platforms, cloud data engineering, and staff upskilling across its UK regional offices.",
                    f"Outlines how technology and AI platform integration are reshaping delivery across UK audit, strategy, and tax lines.",
                ),
                "benefit": "EY UK Technology & Talent Blueprint: Illustrates how major UK accounting networks pair proprietary AI assurance platforms with structured staff upskilling to lift delivery margins.",
                "action_item": "Benchmark your internal finance and audit team's AI training curriculum against Big Four upskilling models so reviewers can effectively interrogate automated schedules.",
                "risk_angle": "Scaling AI across assurance and tax delivery requires strict methodology validation so automated sampling satisfies FRC Audit Quality Review (AQR) standards.",
            }
        if "bdo" in text and ("2,000" in text or "partners" in text):
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ UK Practice Talent",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that mid-tier accounting and advisory network BDO UK has promoted nearly 2,000 employees nationwide, including the appointment of 29 new partners across audit, tax, and advisory. The promotions reflect sustained investment in specialist leadership as mid-market UK businesses navigate regulatory and AI change.",
                    f"Demonstrates strong partner-track capacity expansion across the UK's fifth-largest accountancy network.",
                ),
                "benefit": f"UK Mid-Tier Practice Capacity (BDO 2,000 Promotions · {source}): Shows how leading UK mid-market practices are expanding senior partner review capacity while automating routine compliance work.",
                "action_item": "Assess how AI automation of junior bookkeeping and compliance tasks alters your finance team's career progression pyramid, ensuring newly promoted managers build strong review skills.",
                "risk_angle": "As AI automates entry-level preparation, finance leaders must prevent a skills hollow-out among newly promoted managers and senior reviewers.",
            }
        if "floqast" in text and "pwc" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ Close Automation & PwC",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that close-management vendor FloQast and Big Four firm PwC UK have expanded their strategic alliance to deliver AI-enabled finance managed services. The joint offering pairs FloQast's automated account reconciliation and month-end close workflows with PwC UK's operational finance delivery teams.",
                    f"Shows how Big Four managed services and cloud close software are converging to automate month-end accounting.",
                ),
                "benefit": f"Automated Close & Managed Services Alliance (FloQast × PwC UK): Demonstrates how UK CFOs can combine automated balance-sheet reconciliation software with Big Four managed delivery.",
                "action_item": "Audit your month-end close checklist to identify manual balance-sheet reconciliations and intercompany eliminations suitable for automated close-management workflows.",
                "risk_angle": "Transitioning month-end reconciliations to automated or managed workflows requires clear maker-checker sign-off hierarchies to preserve SOX and UK corporate controls.",
            }
        if "work-from-home" in text or "amitrano" in text:
            return {
                "score": 93,
                "tier": "High UK Finance Impact",
                "func_tag": "🛡️ Practice Workforce",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} covers commentary from PwC UK Senior Partner Marco Amitrano warning that prolonged work-from-home policies have had adverse developmental consequences for young professionals entering accounting and finance. Amitrano emphasises that in-person apprenticeship and side-by-side coaching remain critical as AI reshapes entry-level tasks.",
                    f"Highlights the talent-development tension between remote working, AI automation, and junior auditor apprenticeship.",
                ),
                "benefit": f"UK Finance Apprenticeship & Hybrid Governance (PwC UK · {source}): Highlights the leadership challenge of training junior accountants when remote work and AI simultaneously reduce routine task exposure.",
                "action_item": "Establish structured in-person coaching during month-end close and audit cycles so junior finance analysts learn how to interrogate AI-generated variances and working papers.",
                "risk_angle": "Junior staff working remotely with AI copilots without close senior mentorship face higher risk of accepting plausible-sounding model errors in financial schedules.",
            }
        return {
            "score": 94,
            "tier": "High UK Finance Impact",
            "func_tag": "🛡️ Audit & Big Four",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Insight from {source} ('{title}') examines how {actor} is addressing {focus}, highlighting strategic priorities across enterprise resilience, workforce capabilities, and technology adoption.",
                f"Tracks how Big Four and mid-tier advisory leaders are guiding UK boards on {focus[:60]}.",
            ),
            "benefit": f"Big Four Advisory Benchmark ({source} · {actor}): Outlines how leading accounting and advisory networks frame {focus[:65]} for UK corporate boards and finance functions.",
            "action_item": f"Incorporate {source}'s perspective on '{title[:55]}' into your next Audit & Risk Committee briefing paper to benchmark internal capabilities.",
            "risk_angle": f"Addressing {focus[:60]} without aligning internal audit controls and staff training creates execution gaps between board strategy and finance operations.",
        }

    if "prove value" in text or "roi" in text or "struggle" in text or "productivity" in text or "liquidity" in text or "cash" in text:
        if "kyriba" in text or "budget reaction" in text:
            return {
                "score": 96,
                "tier": "High UK Finance Impact",
                "func_tag": "💷 UK Budget & Liquidity",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Treasury management leader Kyriba warns via {source} that short-term market reactions to the UK Budget risk masking deeper structural pressures on corporate liquidity, borrowing costs, and workforce productivity. Kyriba executives urge UK CFOs to replace static cash spreadsheets with real-time, AI-driven liquidity stress-testing and working-capital visibility.",
                    f"Connects post-Budget UK fiscal policy with real-time treasury forecasting and liquidity risk management.",
                ),
                "benefit": f"Post-Budget UK Liquidity Strategy (Kyriba · {source}): Emphasises why UK CFOs and group treasurers need continuous 13-week rolling cash visibility and automated interest-rate scenario modelling.",
                "action_item": "Run a post-Budget working-capital and liquidity stress test across your 13-week cash forecast, incorporating updated UK employer National Insurance, tax, and gilt-yield assumptions.",
                "risk_angle": "Relying on static month-end cash snapshots during UK fiscal and interest-rate volatility can mask intraday liquidity squeezes across group subsidiaries.",
            }
        if "nine in ten" in text or "cash management" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "💷 AI Cash Management",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports survey findings showing that nine in ten (90%) senior finance leaders now back AI-powered cash management to improve working-capital forecasting, receivables collection, and idle-cash sweeping. Finance directors cite real-time anomaly detection across multi-bank ledgers as a top treasury priority.",
                    f"Quantifies strong CFO consensus (90%) behind deploying AI for automated treasury and cash-flow forecasting.",
                ),
                "benefit": f"CFO Consensus on Treasury AI (90% Adoption · {source}): Demonstrates that AI-assisted cash forecasting and automated receivables matching have moved into the mainstream for UK corporate treasurers.",
                "action_item": "Evaluate connecting your treasury management system (TMS) or bank feeds to automated AR/AP cash-forecasting models to reduce variance between projected and actual weekly cash positions.",
                "risk_angle": "Automated cash-sweeping or payment-scheduling rules must enforce dual-authorization limits in banking portals to prevent erroneous treasury transfers.",
            }
        return {
            "score": 95,
            "tier": "High UK Finance Impact",
            "func_tag": "📈 CFO ROI & Value",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Reporting from {source} ('{title}') examines how finance and executive teams measure concrete productivity, cash-flow, and P&L returns from enterprise AI investments.",
                f"Addresses how CFOs convert AI pilot activity into auditable cost savings and cycle-time reductions.",
            ),
            "benefit": f"CFO Value Realisation ({actor}): Focuses on converting AI software spend into measurable close-cycle speed, working-capital discipline, and P&L productivity.",
            "action_item": f"Require every active AI pilot in your finance function to report baseline vs. post-deployment hours saved and error-rate reductions before approving annual license renewals.",
            "risk_angle": "Expanding enterprise AI licenses without auditable productivity KPIs leads to SaaS sprawl and unrecovered software overhead.",
        }

    if "acquisition" in text or "acquisitions" in text or "private equity" in text or "raises" in text or "secures" in text:
        if "livingbridge" in text or "apteus" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "💼 UK Accounting PE Roll-Up",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that mid-market private equity firm Livingbridge has backed the launch of Apteus, a consolidated UK accounting services group formed through seven simultaneous regional practice acquisitions. The platform strategy centres on unifying cloud practice management, AI compliance automation, and shared advisory capabilities.",
                    f"Illustrates rapid private-equity consolidation across UK regional accountancy practices.",
                ),
                "benefit": f"UK Accounting PE Consolidation (Livingbridge / Apteus · 7 Acquisitions): Shows how private-equity sponsors are rolling up UK accountancy practices to amortize AI and technology investment across a larger client base.",
                "action_item": "If operating in or advising the mid-tier practice market, evaluate how centralising ERP, client onboarding, and AI tax/audit tooling across acquired practices drives EBITDA margin expansion.",
                "risk_angle": "Rapid multi-practice roll-ups create fragmented client data environments and inconsistent quality-management controls (ISQM 1) if IT integration lags deal completion.",
            }
        if "collective" in text and "100m" in text:
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "💼 Accounting FinTech Capital",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that financial platform Collective has secured $100M in fresh capital to scale its AI-native accounting, bookkeeping, and tax formation platform for solo business owners and independent consultants. The funding accelerates automation of monthly close, expense categorization, and quarterly tax filings.",
                    f"Highlights major venture backing ($100M) for end-to-end AI bookkeeping and tax platforms.",
                ),
                "benefit": f"AI-Native Bookkeeping Scale (Collective $100M · {source}): Signals how well-capitalised fintech platforms are automating end-to-end SME bookkeeping, payroll, and tax compliance.",
                "action_item": "Assess how automated bookkeeping and categorization engines can be integrated into your client-accounting or subsidiary ledger workflows to eliminate manual bank-feed coding.",
                "risk_angle": "Automated SME bookkeeping platforms require periodic accountant review of chart-of-accounts mappings to prevent systematic misclassification of capital vs. revenue expenditure.",
            }
        if "talky" in text or "unwritten rules of accounting" in text:
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "💼 Accounting Tribal Knowledge AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that European accounting-AI startup Talky has raised €1.5 million to capture and codify the 'unwritten rules' and client-specific institutional knowledge inside accounting practices. The platform helps firms retain tacit partner and manager context on complex client ledgers and historical adjustments.",
                    f"Addresses how accounting practices codify tacit client-ledger knowledge into reusable AI workflows.",
                ),
                "benefit": f"Codifying Tacit Accounting Knowledge (Talky €1.5M · {source}): Solves a classic practice pain point—preventing client-specific accounting nuances from walking out the door during staff turnover.",
                "action_item": "Document client-specific or subsidiary-specific accounting policies and recurring journal adjustments in structured knowledge repositories so AI review tools apply consistent rules.",
                "risk_angle": "Training internal AI assistants on historical working papers requires scrubbing outdated tax rates or superseded accounting treatments first.",
            }
        if "ravical" in text:
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "💼 Practice Growth & AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Reporting via {source} ('{title}') details how accounting-tech startup Ravical secured a $17 million seed round led by MMC Ventures to deploy domain-specific AI agents for accounting and advisory firms. The platform aims to decouple practice revenue growth from linear headcount hiring by automating routine compliance and client preparation.",
                    f"Shows how MMC-backed Ravical ($17M) is targeting the link between accounting firm growth and linear staffing.",
                ),
                "benefit": f"Decoupling Practice Growth from Headcount (Ravical $17M · {source}): Demonstrates how UK and European venture capital is backing agentic AI to expand revenue per partner in accounting practices.",
                "action_item": "Measure your finance or practice team's revenue-per-FTE (or transactions-processed-per-FTE) before and after deploying AI workflow automation to validate operating leverage.",
                "risk_angle": "Scaling client or transaction volume without proportional senior reviewer bandwidth can strain quality control if AI confidence thresholds are not strictly enforced.",
            }

    if "banking" in text or "uk finance" in text:
        if "86%" in text or "ibs intelligence" in text.lower():
            return {
                "score": 96,
                "tier": "High UK Finance Impact",
                "func_tag": "🏦 UK Finance 86% Adoption",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"A new sector study reported by {source} reveals that AI adoption across UK financial services has reached 86%, with banks, insurers, and wealth managers moving rapidly from experimental pilots to production deployment across fraud detection, credit underwriting, and finance operations.",
                    f"Establishes an 86% adoption benchmark across UK financial institutions.",
                ),
                "benefit": f"UK Financial Sector Adoption Benchmark (86% · {source}): Confirms that AI deployment is now standard operating practice across UK financial services, shifting competitive advantage from basic adoption to governance and ROI.",
                "action_item": "Benchmark your finance department's production AI maturity against the 86% UK sector adoption rate and identify the top two manual close or reporting bottlenecks still running on legacy scripts.",
                "risk_angle": "With 86% of UK financial firms deploying AI, lagging on model risk management or data quality creates immediate regulatory and operational disadvantages.",
            }
        if "autonomous are ai agents" in text or "digit.fyi" in text.lower():
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🏦 Autonomous Agents in UK Finance",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} investigates the true degree of autonomy granted to AI agents inside UK financial institutions, finding that while agentic workflows are increasingly drafting reconciliations, compliance alerts, and customer responses, regulated firms strictly restrict autonomous execution over ledger postings and fund transfers.",
                    f"Examines where UK financial institutions draw the boundary between agent autonomy and human sign-off.",
                ),
                "benefit": f"Agent Autonomy Boundaries in UK Finance ({source}): Clarifies that leading UK institutions deploy AI agents in 'propose-and-verify' mode rather than granting unconstrained write access to core ledgers.",
                "action_item": "Enforce a strict read-only / draft-only permission tier for all AI agents connected to ERP, treasury, and general-ledger systems, requiring explicit human approval before posting entries.",
                "risk_angle": "Granting autonomous write or payment-execution privileges to probabilistic AI agents violates segregation-of-duties controls in UK financial services.",
            }
        if "banking password" in text or "bank of america" in text:
            return {
                "score": 95,
                "tier": "High UK Finance Impact",
                "func_tag": "🏦 AI Agent Credential Risk",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that Bank of America has issued formal customer guidance warning against sharing online banking passwords or authentication tokens with third-party AI assistants and browser agents, reminding account holders that they bear liability for transactions initiated via delegated agent access.",
                    f"Highlights banking liability and security risks when users hand credentials to autonomous AI browser agents.",
                ),
                "benefit": f"Corporate Banking Credential Security (Bank of America · {source}): Critical reminder for UK treasury and AP teams that sharing banking portal credentials with third-party AI automation tools voids bank fraud protections.",
                "action_item": "Issue an immediate treasury security reminder prohibiting finance staff from entering corporate banking credentials, MFA codes, or API keys into unapproved third-party AI agents.",
                "risk_angle": "Delegating banking portal access to third-party AI agents bypasses dual-control payment mandates and shifts unauthorized transaction liability onto the corporate account holder.",
            }
        return {
            "score": 94,
            "tier": "High UK Finance Impact",
            "func_tag": "🏦 UK Banking & Strategy",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Coverage from {source} ('{title}') analyses how UK banking and financial institutions are aligning AI deployment with data architecture modernisation, workforce training, and regulatory resilience.",
                f"Examines strategic priorities across UK banking technology and governance.",
            ),
            "benefit": f"UK Banking & Financial Strategy ({actor}): Highlights why clean data architecture, staff training, and governance matter as much as model selection in UK financial services.",
            "action_item": f"Review '{title[:55]}' against your finance data-governance roadmap to ensure underlying ledger and reporting data are structured cleanly for AI consumption.",
            "risk_angle": "Connecting AI models to fragmented or unreconciled banking and ERP data pipelines amplifies reporting errors at scale.",
        }

    if re.search(
        r"\b(cfo|cfos|finance leader|finance leaders|finance team|finance teams|fp&a|accountant|accounting|payroll)\b",
        text,
    ):
        if "levvy ai" in text or "hidden hours" in text:
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "📈 Practice Advisory Revenue",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that practice-automation platform Levvy AI is helping accounting firms identify unbilled 'hidden hours' lost to manual client chasing, spreadsheet cleanup, and routine bookkeeping, reallocating that capacity into higher-margin CFO advisory services.",
                    f"Shows how AI workflow telemetry uncovers capacity bottlenecks inside accounting practices.",
                ),
                "benefit": f"Converting Compliance Hours to Advisory Revenue (Levvy AI · {source}): Demonstrates how accounting practices use AI workflow automation to recover realization rates and grow fractional-CFO advisory margins.",
                "action_item": "Track time spent by finance and practice staff on manual data chasing and reconciliation cleanup over one month-end cycle to quantify the capacity recoverable via automation.",
                "risk_angle": "Shifting staff from compliance preparation to client advisory requires updated engagement letters and professional indemnity scope checks.",
            }
        if "intuit" in text and "mid-market" in text:
            return {
                "score": 94,
                "tier": "High UK Finance Impact",
                "func_tag": "📈 Mid-Market Accounting AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that financial software giant Intuit has unveiled a new suite of agentic AI tools built for accounting firms and mid-market finance teams, automating multi-entity financial reporting, anomaly detection, and collaborative client close workflows.",
                    f"Expands Intuit's embedded AI automation from small businesses into mid-market finance and accounting practices.",
                ),
                "benefit": f"Mid-Market ERP & Accounting Automation (Intuit · {source}): Shows how incumbent accounting software vendors are embedding multi-entity FP&A and close automation directly into core ledgers.",
                "action_item": "Evaluate embedded AI capabilities within your existing accounting or ERP suite before procuring standalone point solutions that require custom ledger integrations.",
                "risk_angle": "Enabling automated ledger categorization or journal suggestions inside core accounting suites requires role-based approval thresholds to preserve audit trails.",
            }
        if "payroll leaders" in text or "the shard" in text:
            return {
                "score": 93,
                "tier": "High UK Finance Impact",
                "func_tag": "📈 UK Payroll & Practice Ops",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports on QX Accounting Services' executive roundtable at The Shard in London, where senior UK payroll and accounting leaders examined how AI validation, HMRC real-time reporting compliance, and managed services are reshaping payroll operations.",
                    f"Captures senior UK practitioner perspectives on automating high-volume payroll and compliance checks.",
                ),
                "benefit": f"UK Payroll Automation & Compliance (QX Accounting Services · {source}): Highlights how UK finance and practice leaders are using AI anomaly checks to prevent payroll errors and HMRC PAYE discrepancies.",
                "action_item": "Implement automated pre-run variance checks comparing current-month payroll gross-to-net schedules against prior-month baselines and HR starter/leaver logs.",
                "risk_angle": "Payroll processing errors carry immediate employee relations and HMRC compliance consequences; AI variance checks must supplement rather than replace payroll sign-off.",
            }
        if "askdost" in text or "dost launches" in text:
            return {
                "score": 93,
                "tier": "High UK Finance Impact",
                "func_tag": "📈 AP & Finance Assistant",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that financial automation provider Dost has launched AskDost, a conversational AI assistant built for corporate finance and operations teams to query supplier invoices, reconcile purchase orders, and resolve accounts-payable exceptions in real time.",
                    f"Brings natural-language querying and automated three-way PO matching to accounts-payable operations.",
                ),
                "benefit": f"Conversational AP & Supplier Reconciliation (AskDost · {source}): Shows how natural-language finance assistants reduce time spent investigating supplier invoice discrepancies and delivery mismatches.",
                "action_item": "Pilot automated three-way matching (PO, goods-received note, and supplier invoice) in accounts payable to reduce manual exception handling.",
                "risk_angle": "Conversational assistants querying AP ledgers must enforce strict vendor-master access controls so users cannot approve or modify supplier bank details.",
            }
        if "sage" in text and "explainable ai" in text:
            return {
                "score": 91,
                "tier": "High UK Finance Impact",
                "func_tag": "📈 Explainable Finance AI",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} profiles how UK accounting software leader Sage is experimenting with multimodal and sonified data representations ('Explainable AI Music') to help finance users intuitively spot anomalies, cash-flow rhythms, and ledger outliers alongside transparent audit explanations.",
                    f"Explores novel multimodal interfaces for making complex financial ledger patterns and AI anomaly flags interpretable.",
                ),
                "benefit": f"Explainable Anomaly Detection (Sage · {source}): Reinforces why UK accounting software leaders prioritise human interpretability and transparent reasoning trails over black-box predictions.",
                "action_item": "Ensure any anomaly-detection tool used in month-end review surfaces the exact underlying journal lines and rule triggers behind every flagged outlier.",
                "risk_angle": "Unexplainable anomaly alerts create reviewer alert-fatigue and are routinely discounted by external auditors during substantive testing.",
            }

    if item.category == "UK Finance & CFO AI":
        if "contractor demand" in text or "contractor uk" in text.lower():
            return {
                "score": 91,
                "tier": "High UK Finance Impact",
                "func_tag": "💷 UK AI Talent & IR35",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports that UK enterprise demand for specialist IT and AI contractors surged in September 2026 to its highest level since 2023, as banks, corporates, and public-sector bodies bring in interim data engineers and AI implementation leads.",
                    f"Tracks surging UK day-rate contractor demand for enterprise AI and data-engineering projects.",
                ),
                "benefit": f"UK IT & AI Contractor Budget Pressure ({source}): Alerts UK CFOs and procurement teams to tightening supply and rising day rates for interim AI and data-engineering specialists.",
                "action_item": "Review FY26/27 IT project budgets and IR35 status determinations for interim AI/data contractors, ensuring clear milestone deliverables and knowledge-transfer clauses.",
                "risk_angle": "Relying heavily on external IT contractors to build internal finance AI tools without documentation handovers creates key-person dependency and IR35 compliance exposure.",
            }
        if "operating loss" in text and "895 billion" in text:
            return {
                "score": 92,
                "tier": "High UK Finance Impact",
                "func_tag": "💷 AI Vendor Economics",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"{source} reports financial disclosures showing Anthropic swinging back to an operating loss as projected multi-year cloud and compute commitments reaching $895 billion weigh on margins ahead of its planned IPO.",
                    f"Highlights the massive capital intensity ($895B compute commitments) shaping frontier AI vendor financials.",
                ),
                "benefit": f"Frontier AI Vendor Financial Due Diligence ($895B Compute · {source}): Crucial financial signal for UK CFOs assessing long-term vendor pricing power, capital burn, and API unit economics.",
                "action_item": "Avoid locking your enterprise into single-vendor multi-year minimum LLM spend commitments without price-protection caps and model-portability architecture.",
                "risk_angle": "Massive compute commitments at frontier labs could drive sudden API price increases or tier restructuring as vendors seek pre-IPO profitability.",
            }
        if "outside financial support" in text or "consultancy.uk" in text.lower():
            return {
                "score": 90,
                "tier": "High UK Finance Impact",
                "func_tag": "💷 Fractional CFO & Advisory",
                "summary": _polish_executive_summary(
                    sig,
                    item.category,
                    f"Advisory briefing from {source} examines the inflection points—such as fundraising, cross-border expansion, ERP migration, or AI automation—where growing UK businesses should bring in external fractional CFOs or financial advisory support.",
                    f"Outlines key operational triggers for engaging external CFO and financial transformation specialists.",
                ),
                "benefit": f"Scaling UK Finance Function Maturity ({source}): Helps high-growth UK companies and advisory practices identify when internal bookkeeping must be upgraded to institutional FP&A and controller governance.",
                "action_item": "Assess whether upcoming ERP, M&A, or AI transformation projects require temporary specialist controller or FP&A advisory capacity to protect BAU month-end close.",
                "risk_angle": "Delaying senior financial controller oversight during rapid revenue growth increases the risk of working-capital shortfalls and audit adjustments.",
            }
        return {
            "score": 90,
            "tier": "High UK Finance Impact",
            "func_tag": "💷 UK Finance & Market Pulse",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Market intelligence via {source} ('{title}') examines how {actor} is navigating {focus}, highlighting capital-allocation, governance, and technology adoption implications for UK financial leaders.",
                f"Provides UK finance and strategy teams with market context on {focus[:65]}.",
            ),
            "benefit": f"UK Finance & Market Intelligence ({source} · {actor}): Tracks how developments in '{title[:55]}' influence capital allocation, vendor risk, and operational strategy for UK finance teams.",
            "action_item": f"Assess the relevance of '{title[:55]}' ({source}) during your next monthly finance leadership or investment committee review.",
            "risk_angle": f"Market and technology shifts around {focus[:55]} require ongoing monitoring of counterparty exposure, cost assumptions, and governance controls.",
        }

    return None

def _synthesize_ops_and_global_intel(
    item: NewsItem, sig: dict[str, str], text: str
) -> dict[str, object]:
    """Synthesize bespoke executive summary, benefit, and actionable outcome for Enterprise Ops & Global AI items."""
    title = sig["title"]
    source = sig["source"]
    actor = sig["prefix"] or sig["actor"]
    focus = sig["focus_lower"]
    stat = sig["stat"]

    if "scraping" in text or "opt out" in text or "robots.txt" in text or "training preferences" in text:
        return {
            "score": 84,
            "tier": "Finance Ops & Productivity",
            "func_tag": "🔒 Data Privacy & IP",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Reporting via {source} ('{title}') details how major frontier AI labs and web standards bodies are converging on standardized machine-readable opt-out protocols so publishers and enterprises can block unauthorized AI web scraping and model training.",
                f"Establishes machine-readable opt-out signals to protect proprietary web content from AI training crawlers.",
            ),
            "benefit": f"Corporate IP & Training Opt-Out Controls ({actor} · {source}): Helps legal, IR, and finance teams protect published annual reports, pricing tables, and proprietary research from unauthorized LLM scraping.",
            "action_item": f"Following this {source} update on '{title[:50]}', ask your web/security administrator to verify that robots.txt and AI training opt-out headers are configured across investor-relations and corporate portals.",
            "risk_angle": "Unprotected public portals and misconfigured workspace tenants allow external crawlers and consumer AI tools to ingest proprietary corporate disclosures.",
        }

    if (
        "no internet" in text
        or "live internet" in text
        or "containment" in text
        or "securing" in text
        or "security" in text
        or "bug bount" in text
        or "misalignment" in text
        or "backdoored" in text
        or "cwe-bench" in text
    ):
        return {
            "score": 83,
            "tier": "Finance Ops & Productivity",
            "func_tag": "🔒 AI Security & Controls",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Security report from {source} ('{title}') examines how {actor} is addressing {focus}, detailing defensive hardening, vulnerability benchmarking, and real-time containment controls against AI-enabled cyber threats.",
                f"Highlights enterprise security posture and vulnerability controls around {focus[:65]}.",
            ),
            "benefit": f"Enterprise AI Security Posture ({actor}{f' · {stat}' if stat else ''}): Tracks how security teams and frontier labs detect model misalignment, patch supply-chain backdoors, and contain autonomous agent actions.",
            "action_item": f"Share this {source} security update on '{title[:55]}' with your CISO and internal audit lead to verify that IDE extensions, model APIs, and agent permissions are continuously monitored.",
            "risk_angle": f"Security vulnerabilities across {focus[:55]} can expose developer credentials, internal codebases, or connected financial databases to unauthorized access.",
        }

    if "diligence" in text or "transactional" in text or "ropes & gray" in text or "statebench" in text or "integration contracts" in text:
        return {
            "score": 81,
            "tier": "Finance Ops & Productivity",
            "func_tag": "⚙️ Enterprise AI Workflows",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Case study from {source} ('{title}') demonstrates how {actor} is engineering structured AI verification harnesses to handle {focus}, improving multi-document state tracking and legal/financial review reliability.",
                f"Shows how structured evaluation harnesses make enterprise document and transactional diligence auditable.",
            ),
            "benefit": f"Transactional & Document Diligence ({actor}): Shows M&A, legal, and finance teams how wrapping LLMs in deterministic state-tracking harnesses accelerates contract and data-room review.",
            "action_item": f"Evaluate structured AI extraction workflows modeled on {actor} for M&A data-room review, lease-accounting (IFRS 16) abstraction, and supplier contract audits.",
            "risk_angle": "Long-document AI review without state-tracking verification risks missing late-stage contract amendments, side letters, or change-of-control clauses.",
        }

    if "agents" in text or "agent" in text or "agentic" in text:
        return {
            "score": 78,
            "tier": "Finance Ops & Productivity",
            "func_tag": "🤖 AI Agents & Governance",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Analysis from {source} ('{title}') examines {focus}, exploring how organizations measure real-world task completion, enforce behavioural incentives, and maintain human accountability over autonomous AI agents.",
                f"Evaluates practical governance, liability, and output quality metrics for production AI agents.",
            ),
            "benefit": f"Agentic Workflow Governance ({actor} · {source}): Highlights why finance and operations leaders must judge AI agents by verified business outputs and auditability rather than raw token volume.",
            "action_item": f"Apply the lessons from '{title[:55]}' by requiring real-time action logging, spend caps, and human sign-off gates before any internal AI agent interacts with production systems.",
            "risk_angle": f"Unmonitored agent autonomy in {focus[:55]} creates corporate liability and operational errors when agents optimize for proxy metrics or bypass intended rules.",
        }

    if "dictation" in text or "voice" in text or "anyspeech" in text or "on-device" in text or "palette" in text:
        return {
            "score": 76,
            "tier": "Finance Ops & Productivity",
            "func_tag": "💻 Local & Productivity AI",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Product and engineering update from {source} ('{title}') showcases how {actor} enables {focus} using compact, specialized, or on-device models that keep enterprise content consistent and private.",
                f"Demonstrates how specialized small models automate executive deck creation, speech transcription, and local workflows.",
            ),
            "benefit": f"Confidential & Specialized Workplace AI ({actor}): Shows how compact on-device and task-specific models automate board-deck formatting and meeting notes without exposing sensitive data to public clouds.",
            "action_item": f"Test whether specialized productivity tooling like {actor} can streamline board-pack preparation or executive meeting transcription under your corporate data-privacy policy.",
            "risk_angle": "Third-party dictation, meeting-note, and slide-generation tools must be vetted for local processing or enterprise zero-data-retention before use in board or audit meetings.",
        }

    if "data center" in text or "compute campuses" in text or "grid" in text or "scaling git" in text or "ram" in text:
        return {
            "score": 75,
            "tier": "Finance Ops & Productivity",
            "func_tag": "⚡ Cloud & Compute Infra",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Infrastructure report via {source} ('{title}') examines how {actor} is navigating {focus}, highlighting the capital expenditure, energy grid constraints, and credit guarantees underpinning global AI compute expansion.",
                f"Tracks data-center financing, power-grid commitments, and hyperscale infrastructure economics.",
            ),
            "benefit": f"AI Compute & Infrastructure Economics ({actor}): Tracks how '{title[:52]}' shapes power-grid bottlenecks, financing guarantees, and hardware costs driving enterprise cloud AI pricing.",
            "action_item": f"Factor cloud compute and energy pass-through costs highlighted in '{title[:50]}' into your 3-year IT cloud FinOps budget and vendor financing assessments.",
            "risk_angle": f"Escalating data-center power, environmental permitting, and financing pressures around {focus[:50]} can translate into regional cloud capacity constraints and higher API unit costs.",
        }

    if re.search(
        r"\b(gemini|gpt|claude|grok|mistral|granite|frontier model|openai|deepmind|anthropic|genie|lfm3)\b",
        text,
    ):
        return {
            "score": 74,
            "tier": "Finance Ops & Productivity",
            "func_tag": "🧠 Frontier Models & Labs",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"{source} reports on '{title}', detailing how {actor} is advancing {focus} across model architecture, workspace integration, corporate affairs, and enterprise commercialization.",
                f"Covers frontier lab developments and enterprise model capabilities from {actor}.",
            ),
            "benefit": f"Frontier Lab & Model Intelligence ({actor}{f' · {stat}' if stat else ''}): Keeps technology and finance leaders informed on how '{title[:55]}' shifts enterprise copilot capabilities, vendor credit profiles, and licensing.",
            "action_item": f"Evaluate how {actor}'s update ('{title[:50]}') impacts your approved enterprise model catalog, workspace integrations, or AI vendor risk scorecard.",
            "risk_angle": f"Rapid frontier model updates and commercial shifts around {focus[:55]} require version pinning and governance review so automated enterprise workflows remain stable.",
        }

    if "shutting down" in text or "downturn" in text or "stock crashes" in text or "skyrocketing quarter" in text or "doubles its valuation" in text or "raises" in text or "$1t business" in text:
        return {
            "score": 69,
            "tier": "General AI & Research",
            "func_tag": "📉 AI Market & Valuations",
            "summary": _polish_executive_summary(
                sig,
                item.category,
                f"Financial and market coverage from {source} ('{title}') analyzes {focus}, examining revenue quality, capex burn, valuation multiples, and competitive shakeouts across the AI ecosystem.",
                f"Provides capital-markets context on AI vendor valuations, semiconductor capex, and startup consolidation.",
            ),
            "benefit": f"AI Capital Markets & Vendor Viability ({actor}{f' · {stat}' if stat else ''}): Essential context for CFOs evaluating AI supplier balance-sheet durability and enterprise cloud capex trends.",
            "action_item": f"Use the financial signals in '{title[:55]}' when conducting vendor solvency checks and negotiating data-escrow or termination protections with AI software suppliers.",
            "risk_angle": f"High valuation multiples and capex burn across {focus[:55]} mean smaller AI point-solution vendors face heightened shutdown or acquisition risk mid-contract.",
        }

    return {
        "score": 50,
        "tier": "General AI & Research",
        "func_tag": "🌐 Enterprise Tech & AI",
        "summary": _polish_executive_summary(
            sig,
            item.category,
            f"Reporting from {source} ('{title}') explores how {actor} is approaching {focus}, illustrating broader shifts in workplace AI policy, platform strategy, and enterprise technology adoption.",
            f"Provides broader industry context on {focus[:65]} as reported by {source}.",
        ),
        "benefit": f"Industry & Workplace AI Context ({actor} · {source}): Tracks how developments in '{title[:55]}' shape workforce policies, platform ecosystems, and digital strategy.",
        "action_item": f"Note '{title[:55]}' ({source}) in your quarterly technology horizon scan to anticipate downstream impacts on workplace tooling and employee AI policies.",
        "risk_angle": f"Emerging shifts in {focus[:55]} can influence employee expectations, shadow-IT usage, and platform vendor lock-in if not addressed in corporate IT policy.",
    }


def synthesize_article_intelligence(item: NewsItem) -> dict[str, object]:
    """Master synthesis engine returning score, tier, func_tag, summary, benefit, action_item, risk_angle, and role weights."""
    sig = _extract_article_signals(item)
    text = f"{sig['title']} {sig['clean_raw']}".lower()

    intel = _synthesize_research_and_community(item, sig, text)
    if intel is None:
        intel = _synthesize_uk_finance_intel(item, sig, text)
    if intel is None:
        intel = _synthesize_ops_and_global_intel(item, sig, text)

    score = int(intel["score"])
    func_tag = str(intel["func_tag"])

    cfo_w = score
    audit_w = score
    fpa_w = score
    if "🏛️" in func_tag or "🛡️" in func_tag or "🔒" in func_tag or "🧾" in func_tag:
        audit_w = min(100, score + 12)
        cfo_w = min(98, score + 4)
    elif "📈" in func_tag or "🏦" in func_tag or "📊" in func_tag or "💼" in func_tag or "💷" in func_tag:
        cfo_w = min(100, score + 10)
        fpa_w = min(96, score + 6)
    elif "🤖" in func_tag or "⚙️" in func_tag or "💻" in func_tag or "⚡" in func_tag or "🧠" in func_tag or "🔬" in func_tag:
        fpa_w = min(99, score + 14)
        cfo_w = min(92, score + 5)
    else:
        fpa_w = min(90, score + 8)

    intel["cfo_score"] = cfo_w
    intel["audit_score"] = audit_w
    intel["fpa_score"] = fpa_w
    intel["clean_title"] = sig["title"]
    return intel


def analyze_uk_finance_benefit(item: NewsItem) -> tuple[int, str, str, str, str]:
    """
    Evaluate a news item for UK Finance Team priority.
    Returns (priority_score_0_to_100, priority_tier, func_tag, executive_summary, uk_finance_benefit).
    """
    intel = synthesize_article_intelligence(item)
    return (
        int(intel["score"]),
        str(intel["tier"]),
        str(intel["func_tag"]),
        str(intel["summary"]),
        str(intel["benefit"]),
    )


def build_executive_breakdown(
    item: NewsItem, score: int, func_tag: str, benefit: str
) -> dict[str, object]:
    """Build structured 3-point Executive Drawer guidance + role-specific priority weights."""
    intel = synthesize_article_intelligence(item)
    return {
        "strategic": benefit or str(intel["benefit"]),
        "risk_angle": str(intel["risk_angle"]),
        "action_item": str(intel["action_item"]),
        "cfo_score": int(intel["cfo_score"]),
        "audit_score": int(intel["audit_score"]),
        "fpa_score": int(intel["fpa_score"]),
    }


def make_stable_id(url: str) -> str:
    """Create a deterministic card ID from its URL so deep-links persist across the 7-day archive."""
    digest = hashlib.sha1((url or "").encode("utf-8")).hexdigest()[:8]
    return f"item-{digest}"


def format_date_label(date_key: str) -> str:
    """Format YYYY-MM-DD into a crisp UK readable date like '3 Nov 2026'."""
    try:
        dt = datetime.strptime(date_key, "%Y-%m-%d")
        return f"{dt.day} {dt.strftime('%b %Y')}"
    except Exception:
        return date_key


def parse_digest_markdown_file(md_path: Path, date_key: str) -> list[NewsItem]:
    """Parse historical NewsItem entries from a saved digests/YYYY-MM-DD.md file."""
    if not md_path.exists():
        return []
    try:
        lines = md_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return []

    section_to_category = {
        "uk finance": "UK Finance & CFO AI",
        "ai labs": "AI Labs & Blogs",
        "tech & ai": "Tech & AI News",
        "research papers": "Research Papers",
        "community pulse": "Hacker News & Reddit",
    }
    current_cat = "Tech & AI News"
    parsed_items: list[NewsItem] = []

    for raw in lines:
        line = raw.strip()
        if line.startswith("## "):
            h_low = line[3:].lower()
            for key, mapped_cat in section_to_category.items():
                if key in h_low:
                    current_cat = mapped_cat
                    break
            continue

        if not line.startswith(("- ", "* ")):
            continue

        rest = line[2:].strip()
        m = re.match(r"^\*\*\[([^\]]+)\]\((https?://[^\)]+)\)\*\*(.*)$", rest)
        if not m:
            continue
        title = m.group(1).strip()
        url = m.group(2).strip()
        tail = m.group(3).strip()

        source = "Curated Source"
        meta = re.match(
            r"^\(\*([^*]+)\*\s*·\s*[^·]+?\s*·\s*Priority\s*`\d+/100`\)(.*)$",
            tail,
        )
        if meta:
            source = meta.group(1).strip()
            tail = meta.group(2).strip()
        else:
            meta2 = re.match(r"^\(\*([^*]+)\*\)(.*)$", tail)
            if meta2:
                source = meta2.group(1).strip()
                tail = meta2.group(2).strip()

        summary = re.sub(r"^(?:—|–|-|:)\s*", "", tail).strip()
        if is_noisy_outlier(title, source):
            continue

        parsed_items.append(
            NewsItem(
                title=title,
                url=url,
                source=source,
                category=current_cat,
                published_at=f"{date_key} 08:00 UTC",
                summary=summary,
            )
        )
    return parsed_items


def build_card_dict(
    item: NewsItem,
    date_key: str,
    is_new: bool,
    gemini_override: dict[str, object] | None = None,
) -> dict[str, object]:
    """Construct a single enriched dashboard card dictionary with 7-day date metadata."""
    intel = synthesize_article_intelligence(item)
    score = int(intel["score"])
    tier = str(intel["tier"])
    func_tag = str(intel["func_tag"])
    summary = str(intel["summary"])
    benefit = str(intel["benefit"])
    risk_angle = str(intel["risk_angle"])
    action_item = str(intel["action_item"])
    clean_title = str(intel["clean_title"])

    if gemini_override:
        score = int(gemini_override.get("score", score))
        func_tag = str(gemini_override.get("func_tag") or func_tag)
        g_sum = clean_summary_text(str(gemini_override.get("summary") or ""), clean_title)
        if len(g_sum) >= 55:
            summary = g_sum
        benefit = str(gemini_override.get("benefit") or benefit)
        action_item = str(gemini_override.get("action_item") or action_item)
        risk_angle = str(gemini_override.get("risk_angle") or risk_angle)
        if score >= 85:
            tier = "High UK Finance Impact"
        elif score >= 70:
            tier = "Finance Ops & Productivity"
        else:
            tier = "General AI & Research"

    pub_domain = resolve_publisher_domain(item.source, item.url)

    return {
        "id": make_stable_id(item.url),
        "title": clean_title,
        "url": item.url,
        "source": item.source,
        "pub_domain": pub_domain,
        "category": item.category,
        "published_at": item.published_at,
        "date_key": date_key,
        "date_label": format_date_label(date_key),
        "score": score,
        "cfo_score": int(intel["cfo_score"]),
        "audit_score": int(intel["audit_score"]),
        "fpa_score": int(intel["fpa_score"]),
        "tier": tier,
        "func_tag": func_tag,
        "summary": summary,
        "raw_summary": item.summary,
        "benefit": benefit,
        "risk_angle": risk_angle,
        "action_item": action_item,
        "is_new": is_new,
    }


def enrich_items_with_gemini(
    items: list[NewsItem], settings: Settings
) -> dict[int, dict[str, object]]:
    """Optionally use Gemini API to refine executive summaries, benefits, and actionable outcomes."""
    if not settings.gemini_api_key or not items:
        return {}

    subset = items[:30]
    prompt_lines = [
        "You are a UK CFO & Finance Director advisor. For each news item below (indexed 0..N), return a JSON array of objects with keys:",
        '`{"idx": int, "score": int (1-100 priority for a UK finance team), "func_tag": "short tag e.g. 🏛️ FCA & Regulation | 🛡️ Audit & Controls | 📈 CFO Strategy | 🔒 Data Privacy | 🤖 AI Agents | 🔬 Research", "summary": "specific 2-sentence executive summary of the article", "benefit": "specific, non-repetitive 1-sentence takeaway for a UK finance team", "action_item": "concrete 1-sentence actionable outcome for a finance or technology leader", "risk_angle": "specific 1-sentence audit, governance, or regulatory risk angle"}`.',
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


def _deduplicate_archive_cards(cards: list[dict[str, object]]) -> list[dict[str, object]]:
    """Consolidate duplicate papers (e.g. ArXiv vs HF Daily Papers) and syndicated press releases across the 7-day archive."""
    seen_norm_titles: set[str] = set()
    seen_syndicated_keys: set[str] = set()
    unique: list[dict[str, object]] = []

    for c in cards:
        title = str(c.get("title") or "")
        t_low = title.lower()
        norm_title = re.sub(r"[^a-z0-9]+", "", t_low)
        if not norm_title or norm_title in seen_norm_titles:
            continue

        # Consolidate identical syndicated funding/rebrand stories reported across multiple outlets
        syn_key = ""
        if "ravical raises" in t_low and "17" in t_low:
            syn_key = "ravical-17m-seed"
        elif "compute campuses" in t_low and "openai" in t_low:
            syn_key = "openai-compute-campuses"
        if syn_key:
            if syn_key in seen_syndicated_keys:
                continue
            seen_syndicated_keys.add(syn_key)

        seen_norm_titles.add(norm_title)
        unique.append(c)

    return unique


def prepare_prioritized_cards(
    items: list[NewsItem], settings: Settings
) -> list[dict[str, object]]:
    """
    Enrich today's news items and merge them with a rolling 7-day archive
    (sourced from docs/data.json and digests/YYYY-MM-DD.md), pruning any stories older than 7 days.
    """
    now_utc = datetime.now(timezone.utc)
    today_date: date = now_utc.date()
    today_slug = today_date.strftime("%Y-%m-%d")
    cutoff_date: date = today_date - timedelta(days=RETENTION_DAYS - 1)
    cutoff_slug = cutoff_date.strftime("%Y-%m-%d")

    valid_dates = [
        (cutoff_date + timedelta(days=offset)).strftime("%Y-%m-%d")
        for offset in range(RETENTION_DAYS)
    ]
    historical_dates = [d for d in valid_dates if d < today_slug]

    # Map of url -> card dict for stories from previous 6 days
    archive_by_url: dict[str, dict[str, object]] = {}

    # 1. Hydrate from historical digests/YYYY-MM-DD.md (oldest -> yesterday) so earliest briefing date wins
    for d_str in historical_dates:
        md_file = DIGESTS_DIR / f"{d_str}.md"
        for hist_item in parse_digest_markdown_file(md_file, d_str):
            if hist_item.url not in archive_by_url:
                archive_by_url[hist_item.url] = build_card_dict(
                    hist_item, date_key=d_str, is_new=False
                )

    # 2. Hydrate/upgrade from existing docs/data.json (keeps exact timestamps/raw_summary if within 7-day window)
    prev_data_path = DOCS_DIR / "data.json"
    if prev_data_path.exists():
        try:
            prev_data = json.loads(prev_data_path.read_text(encoding="utf-8"))
            if isinstance(prev_data, list):
                for row in prev_data:
                    if not isinstance(row, dict) or not row.get("url"):
                        continue
                    url = str(row["url"])
                    title = str(row.get("title") or "")
                    source = str(row.get("source") or "Curated Source")
                    if is_noisy_outlier(title, source):
                        continue
                    pub_at = str(row.get("published_at") or "")
                    row_date = str(row.get("date_key") or "")
                    if not re.match(r"^\d{4}-\d{2}-\d{2}$", row_date):
                        if re.match(r"^\d{4}-\d{2}-\d{2}", pub_at):
                            row_date = pub_at[:10]
                        else:
                            row_date = today_slug
                    if row_date < cutoff_slug or row_date > today_slug:
                        continue
                    if url in archive_by_url:
                        row_date = str(archive_by_url[url]["date_key"])
                    raw_sum = str(
                        row.get("raw_summary")
                        if "raw_summary" in row
                        else (row.get("summary") or "")
                    )
                    temp_item = NewsItem(
                        title=title,
                        url=url,
                        source=source,
                        category=str(row.get("category") or "Tech & AI News"),
                        published_at=pub_at or f"{row_date} 08:00 UTC",
                        summary=raw_sum,
                    )
                    if row_date < today_slug:
                        archive_by_url[url] = build_card_dict(
                            temp_item, date_key=row_date, is_new=False
                        )
        except Exception:
            pass

    # 3. Process today's freshly fetched items
    clean_today_items = [
        it for it in items if not is_noisy_outlier(it.title, it.source)
    ]
    gemini_map = enrich_items_with_gemini(clean_today_items, settings)

    final_by_url: dict[str, dict[str, object]] = dict(archive_by_url)
    for idx, item in enumerate(clean_today_items):
        g_override = gemini_map.get(idx)
        if item.url in archive_by_url:
            orig_date = str(archive_by_url[item.url]["date_key"])
            final_by_url[item.url] = build_card_dict(
                item, date_key=orig_date, is_new=False, gemini_override=g_override
            )
        else:
            final_by_url[item.url] = build_card_dict(
                item, date_key=today_slug, is_new=True, gemini_override=g_override
            )

    # Also include any items from today's digest file if already generated and not in final_by_url
    today_md = DIGESTS_DIR / f"{today_slug}.md"
    for t_item in parse_digest_markdown_file(today_md, today_slug):
        if t_item.url not in final_by_url:
            final_by_url[t_item.url] = build_card_dict(
                t_item, date_key=today_slug, is_new=True
            )

    # Filter strictly to [cutoff_slug, today_slug], sort by score desc then date_key desc, and deduplicate
    cards = [
        c
        for c in final_by_url.values()
        if cutoff_slug <= str(c.get("date_key", "")) <= today_slug
    ]
    cards.sort(
        key=lambda c: (int(c["score"]), str(c.get("date_key", ""))),
        reverse=True,
    )
    return _deduplicate_archive_cards(cards)



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
      --ink-soft: #1f1f1f;
      --body-copy: #383838;
      --mute: #636366;
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
      --ink-soft: #ededf0;
      --body-copy: #d8d8dc;
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
      font-size: 15.5px;
      line-height: 1.65;
      color: var(--body-copy);
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
    .stack-summary {{
      margin: 0 0 8px;
      font-size: 13.4px;
      line-height: 1.52;
      color: var(--body-copy);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .stack-plus {{
      margin: 0 0 6px;
      font-size: 13.2px;
      line-height: 1.5;
      color: var(--ink-soft);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .stack-plus strong {{
      color: var(--ink);
      font-weight: 700;
    }}
    .stack-outcome {{
      margin: 0 0 10px;
      padding-top: 6px;
      border-top: 1px dashed var(--line);
      font-size: 12.6px;
      line-height: 1.48;
      color: var(--body-copy);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .stack-outcome strong {{
      color: var(--brand-violet);
      font-weight: 800;
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
      font-size: 14.5px;
      color: var(--body-copy);
      margin: 0 0 16px;
      line-height: 1.62;
      display: -webkit-box;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    /* "Why It Matters" Inset Callout Box */
    .benefit-box {{
      background: var(--mist);
      border: 1px solid var(--line-subtle);
      border-left: 3px solid var(--brand-violet);
      padding: 13px 15px;
      border-radius: 14px;
      font-size: 13.5px;
      line-height: 1.58;
      color: var(--ink-soft);
      margin-bottom: 18px;
    }}
    .benefit-box.ops-box {{ border-left-color: var(--emerald); }}
    .benefit-box.gen-box {{ border-left-color: var(--brand-blue); }}
    .benefit-lead {{
      color: var(--ink);
      font-weight: 800;
    }}
    .card-outcome-line {{
      margin-top: 9px;
      padding-top: 8px;
      border-top: 1px dashed var(--line);
      font-size: 12.8px;
      line-height: 1.52;
      color: var(--body-copy);
    }}
    .card-outcome-label {{
      color: var(--brand-violet);
      font-weight: 800;
      text-transform: uppercase;
      font-size: 10px;
      letter-spacing: 0.06em;
      margin-right: 4px;
    }}
    .ops-box .card-outcome-label {{ color: var(--emerald); }}
    .gen-box .card-outcome-label {{ color: var(--brand-blue); }}

    /* Comfort Reading Font Size Mode (A+) */
    html[data-font-size="large"] .lead-title {{ font-size: clamp(24px, 2.7vw, 33px); }}
    html[data-font-size="large"] .lead-summary {{ font-size: 17px; line-height: 1.68; }}
    html[data-font-size="large"] .stack-title {{ font-size: 18px; }}
    html[data-font-size="large"] .stack-plus {{ font-size: 14.5px; line-height: 1.58; }}
    html[data-font-size="large"] .card-title {{ font-size: 21.5px; line-height: 1.34; }}
    html[data-font-size="large"] .card-summary {{ font-size: 16px; line-height: 1.66; -webkit-line-clamp: 4; }}
    html[data-font-size="large"] .benefit-box {{ font-size: 14.8px; line-height: 1.62; }}
    html[data-font-size="large"] .stream-headline {{ font-size: clamp(21px, 2.4vw, 25px); }}
    html[data-font-size="large"] .stream-bullets {{ font-size: 15.8px; line-height: 1.66; }}
    html[data-font-size="large"] .drawer-sec-text {{ font-size: 15.8px; line-height: 1.66; }}

    /* 7-Day Rolling Archive Date Filter Bar */
    .date-filter-row {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding-bottom: 12px;
      margin-bottom: 12px;
      border-bottom: 1px solid var(--line-subtle);
    }}
    .date-filter-left {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex: 1;
      min-width: 0;
      overflow-x: auto;
      scrollbar-width: none;
      padding-bottom: 2px;
    }}
    .date-filter-left::-webkit-scrollbar {{ display: none; }}
    .date-bar-label {{
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.1em;
      color: var(--mute);
      white-space: nowrap;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      margin-right: 4px;
      flex-shrink: 0;
    }}
    .date-pills {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }}
    .date-pill {{
      cursor: pointer;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--body-copy);
      padding: 5px 12px;
      font-size: 12px;
      font-weight: 600;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      white-space: nowrap;
      transition: all var(--dur-fast) ease;
    }}
    .date-pill:hover {{
      border-color: var(--brand-violet);
      color: var(--brand-violet);
    }}
    .date-pill.active {{
      background: var(--brand-violet);
      border-color: var(--brand-violet);
      color: #ffffff;
      font-weight: 700;
    }}
    .date-pill-count {{
      font-size: 10.5px;
      opacity: 0.82;
      font-weight: 700;
    }}
    .date-picker-wrap {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      flex-shrink: 0;
    }}
    .date-picker-input {{
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--ink);
      border-radius: 999px;
      padding: 4px 11px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      outline: none;
    }}
    .date-picker-input:focus {{
      border-color: var(--brand-violet);
    }}
    .sort-btn {{
      cursor: pointer;
      border: 1px solid var(--line);
      background: var(--card-bg);
      color: var(--ink);
      padding: 6px 13px;
      border-radius: 999px;
      font-size: 12.5px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      gap: 5px;
      transition: all var(--dur-fast) ease;
      white-space: nowrap;
    }}
    .sort-btn:hover {{
      border-color: var(--brand-violet);
      color: var(--brand-violet);
    }}
    .active-filter-banner {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      background: var(--mist);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 9px 15px;
      margin-bottom: 20px;
      font-size: 12.8px;
      color: var(--body-copy);
    }}
    .filter-reset-link {{
      cursor: pointer;
      border: none;
      background: var(--ink);
      color: var(--paper);
      font-size: 11.5px;
      font-weight: 700;
      padding: 4px 11px;
      border-radius: 999px;
      transition: opacity var(--dur-fast) ease;
    }}
    .filter-reset-link:hover {{ opacity: 0.86; }}
    .day-group-header {{
      grid-column: 1 / -1;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 16px;
      margin: 10px 0 4px;
      background: var(--mist);
      border: 1px solid var(--line);
      border-left: 4px solid var(--brand-violet);
      border-radius: 14px;
      font-size: 13.5px;
      font-weight: 800;
      color: var(--ink);
      letter-spacing: -0.01em;
    }}
    .day-group-sub {{
      font-size: 12px;
      font-weight: 600;
      color: var(--mute);
    }}
    .card-date-badge {{
      display: inline-flex;
      align-items: center;
      padding: 2px 7px;
      border-radius: 6px;
      background: var(--mist);
      border: 1px solid var(--line);
      color: var(--body-copy);
      font-size: 11px;
      font-weight: 700;
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
        <button class="nav-btn nav-btn-icon" type="button" id="fontSizeToggleBtn" onclick="toggleFontSize()" aria-label="Toggle comfortable reading text size" title="Toggle Comfort Reading Text Size (f)">
          <span style="font-weight:800;font-size:12px;">A+</span>
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

              <button class="sort-btn" type="button" id="sortModeBtn" onclick="toggleSortMode()" title="Switch between Priority Score and Chronological Date order">
                <span>Sort: Priority ↓</span>
              </button>

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

          <!-- Sticky Date Filter, Category Pills & Topic Chips -->
          <div class="controls-bar">
            <div class="date-filter-row" role="group" aria-label="Filter stories by date (7-day rolling archive)">
              <div class="date-filter-left">
                <span class="date-bar-label">📅 7-Day Archive</span>
                <div class="date-pills" id="dateFilterPills"></div>
              </div>
              <div class="date-picker-wrap">
                <input type="date" id="datePickerInput" class="date-picker-input" title="Find stories from a specific day (last 7 days)" aria-label="Jump to date in 7-day archive" onchange="onDatePickerChange(this.value)" />
              </div>
            </div>

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

          <div id="activeFilterBanner" class="active-filter-banner" style="display:none;"></div>
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
        <div class="kbd-shortcut-row"><span>Toggle Comfort Text Size (A+)</span><kbd>f</kbd></div>
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
    let currentDate = 'all';
    let currentSort = 'score';
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
      currentDate = 'all';
      document.querySelectorAll('.topic-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-topic') === 'all'));
      document.querySelectorAll('.date-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-date') === 'all'));
      const dp = document.getElementById('datePickerInput');
      if (dp) dp.value = '';
      setFilterByName('all');
      updateDynamicMetrics();
      renderHero();
      renderMain();
      if (ev) window.scrollTo({{ top: 0, behavior: 'smooth' }});
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

    function formatBenefitHtml(str) {{
      if (!str) return '';
      const esc = escapeHtml(str);
      const colonIdx = esc.indexOf(':');
      if (colonIdx > 2 && colonIdx <= 44) {{
        return `<strong class="benefit-lead">${{esc.slice(0, colonIdx + 1)}}</strong>${{esc.slice(colonIdx + 1)}}`;
      }}
      return esc;
    }}

    function getAllArchiveDates() {{
      const dateSet = new Set();
      ITEMS.forEach(it => {{
        if (it.date_key) dateSet.add(it.date_key);
      }});
      const sortedDates = Array.from(dateSet).sort().reverse();
      if (!sortedDates.length) return [];
      const newest = new Date(sortedDates[0] + 'T00:00:00Z');
      const full7 = [];
      for (let i = 0; i < 7; i++) {{
        const d = new Date(newest.getTime() - i * 86400000);
        full7.push(d.toISOString().slice(0, 10));
      }}
      return full7;
    }}

    function formatDatePillLabel(dateKey, idx) {{
      const dt = new Date(dateKey + 'T00:00:00Z');
      if (isNaN(dt.getTime())) return dateKey;
      const dayNum = dt.getUTCDate();
      const mon = dt.toLocaleString('en-GB', {{ month: 'short', timeZone: 'UTC' }});
      const wk = dt.toLocaleString('en-GB', {{ weekday: 'short', timeZone: 'UTC' }});
      if (idx === 0) return `Today · ${{dayNum}} ${{mon}}`;
      if (idx === 1) return `Yesterday · ${{dayNum}} ${{mon}}`;
      return `${{wk}} ${{dayNum}} ${{mon}}`;
    }}

    function formatFullDayHeading(dateKey) {{
      const dates = getAllArchiveDates();
      const idx = dates.indexOf(dateKey);
      const dt = new Date(dateKey + 'T00:00:00Z');
      if (isNaN(dt.getTime())) return dateKey;
      const formatted = dt.toLocaleDateString('en-GB', {{
        weekday: 'long',
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        timeZone: 'UTC'
      }});
      if (idx === 0) return `${{formatted}} — Today's Edition`;
      if (idx === 1) return `${{formatted}} — Yesterday's Edition`;
      return formatted;
    }}

    function buildDateFilterPills() {{
      const wrap = document.getElementById('dateFilterPills');
      if (!wrap) return;
      const dates = getAllArchiveDates();
      const counts = {{}};
      dates.forEach(d => counts[d] = 0);
      ITEMS.forEach(it => {{
        if (it.date_key && counts[it.date_key] !== undefined) counts[it.date_key]++;
      }});

      const dp = document.getElementById('datePickerInput');
      if (dp && dates.length) {{
        dp.max = dates[0];
        dp.min = dates[dates.length - 1];
      }}

      let htmlPills = `
        <button type="button" class="date-pill ${{currentDate === 'all' ? 'active' : ''}}" data-date="all" onclick="setDateFilter('all')">
          All 7 Days <span class="date-pill-count">(${{ITEMS.length}})</span>
        </button>
      `;
      dates.forEach((d, idx) => {{
        const c = counts[d] || 0;
        if (c === 0 && idx > 1) return;
        const lbl = formatDatePillLabel(d, idx);
        htmlPills += `
          <button type="button" class="date-pill ${{currentDate === d ? 'active' : ''}}" data-date="${{d}}" onclick="setDateFilter('${{d}}')">
            ${{escapeHtml(lbl)}} <span class="date-pill-count">(${{c}})</span>
          </button>
        `;
      }});
      wrap.innerHTML = htmlPills;
    }}

    function setDateFilter(dateVal) {{
      if (dateVal === currentDate) return;
      currentDate = dateVal;
      selectedCardIndex = -1;
      document.querySelectorAll('.date-pill').forEach(p => {{
        p.classList.toggle('active', p.getAttribute('data-date') === dateVal);
      }});
      const dp = document.getElementById('datePickerInput');
      if (dp) dp.value = dateVal === 'all' ? '' : dateVal;
      swapContent(() => {{
        updateDynamicMetrics();
        renderHero();
        renderMain();
      }});
    }}

    function onDatePickerChange(val) {{
      if (!val) {{
        setDateFilter('all');
        return;
      }}
      setDateFilter(val);
    }}

    function toggleSortMode() {{
      currentSort = currentSort === 'score' ? 'date' : 'score';
      const btn = document.getElementById('sortModeBtn');
      if (btn) {{
        btn.innerHTML = currentSort === 'score' ? '<span>Sort: Priority ↓</span>' : '<span>Sort: Newest Date ↓</span>';
      }}
      swapContent(() => renderMain());
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
      const kAll = document.querySelector('.kpi-card[data-kpi="all"] .kpi-val');
      if (kHigh) kHigh.textContent = high;
      if (kOps) kOps.textContent = ops;
      if (kGen) kGen.textContent = gen;
      if (kAll) kAll.textContent = sorted.length;

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
      const base = currentDate === 'all'
        ? [...ITEMS]
        : ITEMS.filter(it => it.date_key === currentDate);
      if (currentSort === 'date') {{
        return base.sort((a, b) => {{
          const dCmp = String(b.date_key || '').localeCompare(String(a.date_key || ''));
          if (dCmp !== 0) return dCmp;
          return getActiveScore(b) - getActiveScore(a);
        }});
      }}
      return base.sort((a, b) => {{
        const sCmp = getActiveScore(b) - getActiveScore(a);
        if (sCmp !== 0) return sCmp;
        return String(b.date_key || '').localeCompare(String(a.date_key || ''));
      }});
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
        ? `<div class="drawer-section"><div class="drawer-sec-title" style="color:var(--ink);">📰 Executive Summary</div><p class="drawer-sec-text">${{escapeHtml(item.summary)}}</p></div>`
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
        <div class="drawer-meta">Briefing Date: <strong>${{escapeHtml(item.date_label || item.date_key || '')}}</strong> · Published ${{escapeHtml(formatRelativeTime(item.published_at))}} (${{escapeHtml(item.published_at)}})</div>
        ${{summaryBlock}}
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--brand-violet);">${{FLAG_SVG}} Why It Matters · UK CFO &amp; Finance</div>
          <p class="drawer-sec-text">${{formatBenefitHtml(item.benefit)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--brand-blue);">🎯 Actionable Outcome</div>
          <p class="drawer-sec-text">${{escapeHtml(item.action_item)}}</p>
        </div>
        <div class="drawer-section">
          <div class="drawer-sec-title" style="color:var(--emerald);">🛡️ Audit, Risk &amp; FCA Governance Angle</div>
          <p class="drawer-sec-text">${{escapeHtml(item.risk_angle)}}</p>
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
      const allDates = getAllArchiveDates();
      const targetHeroDate = currentDate === 'all' ? (allDates[0] || '') : currentDate;
      const heroPool = targetHeroDate
        ? ITEMS.filter(it => it.date_key === targetHeroDate).sort((a, b) => getActiveScore(b) - getActiveScore(a))
        : getSortedItems();
      const top4 = (heroPool.length >= 2 ? heroPool : getSortedItems()).slice(0, 4);
      const heroSec = document.getElementById('heroSection');
      const heroGrid = document.getElementById('heroGrid');
      const eyebrowEl = heroSec ? heroSec.querySelector('.eyebrow') : null;
      if (eyebrowEl && targetHeroDate) {{
        const isLatest = allDates.length && targetHeroDate === allDates[0];
        eyebrowEl.innerHTML = `<span class="eyebrow-dot"></span> ${{isLatest ? "Today's Briefing" : "Archive Briefing · " + escapeHtml(formatFullDayHeading(targetHeroDate))}}`;
      }}
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
              <div style="font-size:14px;line-height:1.6;color:var(--ink-soft);">${{formatBenefitHtml(lead.benefit)}}</div>
              <div class="lead-action-line"><strong>🎯 Actionable Outcome:</strong> ${{escapeHtml(lead.action_item)}}</div>
            </div>
          </div>

          <div class="card-footer">
            <span class="pub-pill">
              <img class="pub-favicon" src="${{faviconUrl(lead.pub_domain)}}" alt="" loading="lazy" />
              ${{escapeHtml(lead.source)}} · <span class="card-date-badge">${{escapeHtml(lead.date_label || lead.date_key || '')}}</span> · <span title="${{escapeHtml(lead.published_at)}}">${{escapeHtml(formatRelativeTime(lead.published_at))}}</span>
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
                  <p class="stack-summary">${{escapeHtml(item.summary)}}</p>
                  <p class="stack-plus">${{formatBenefitHtml(item.benefit)}}</p>
                  <p class="stack-outcome"><strong>🎯 Outcome:</strong> ${{escapeHtml(item.action_item)}}</p>
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
        const archiveContext = currentDate === 'all' ? 'across 7-day archive' : `for ${{formatFullDayHeading(currentDate)}}`;
        countLbl.textContent = `${{filtered.length}} ${{filtered.length === 1 ? 'story' : 'stories'}} (${{archiveContext}})`;
      }}

      const banner = document.getElementById('activeFilterBanner');
      if (banner) {{
        const activeParts = [];
        if (currentDate !== 'all') activeParts.push(`📅 ${{formatFullDayHeading(currentDate)}}`);
        if (currentFilter !== 'all') activeParts.push(`Category: ${{currentFilter.toUpperCase()}}`);
        if (currentTopic !== 'all') activeParts.push(`Topic: ${{currentTopic.toUpperCase()}}`);
        if (q) activeParts.push(`Search: "${{escapeHtml(q)}}"`);
        if (activeParts.length > 0) {{
          banner.style.display = 'flex';
          banner.innerHTML = `
            <span>Showing <strong>${{filtered.length}}</strong> of ${{ITEMS.length}} stories (7-day archive) · ${{activeParts.join(' · ')}}</span>
            <button type="button" class="filter-reset-link" onclick="resetAllFilters()">Reset filters ✕</button>
          `;
        }} else {{
          banner.style.display = 'none';
        }}
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
                      <div class="compact-takeaway" style="color:var(--body-copy);margin-bottom:4px;">${{escapeHtml(item.summary)}}</div>
                      <div class="compact-takeaway">${{formatBenefitHtml(item.benefit)}}</div>
                      <div class="compact-takeaway" style="margin-top:3px;color:var(--ink-soft);"><strong>🎯 Actionable Outcome:</strong> ${{escapeHtml(item.action_item)}}</div>
                    </td>
                    <td class="compact-hide-mobile">
                      <span class="pub-pill">
                        <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                        ${{escapeHtml(item.source)}}
                      </span>
                    </td>
                    <td class="compact-hide-mobile"><strong>${{effScore}}</strong>/100</td>
                    <td style="white-space:nowrap;color:var(--mute);" title="${{escapeHtml(item.published_at)}}"><span class="card-date-badge">${{escapeHtml(item.date_label || '')}}</span></td>
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
        let lastStreamDate = '';
        container.innerHTML = filtered.map((item, idx) => {{
          const isSaved = savedUrls.has(item.url);
          const effScore = getActiveScore(item);
          const newBadge = item.is_new ? '<span class="new-badge">NEW</span>' : '';
          const urgencyBadge = urgencyBadgeHtml(effScore, item);
          const numStr = String(idx + 1).padStart(2, '0');
          const summaryLine = item.summary
            ? `<div class="stream-bullet"><strong>📰 Executive Summary:</strong> ${{escapeHtml(item.summary)}}</div>`
            : '';
          let streamDayHeader = '';
          if (currentSort === 'date' && item.date_key && item.date_key !== lastStreamDate) {{
            lastStreamDate = item.date_key;
            const dayCount = filtered.filter(x => x.date_key === item.date_key).length;
            streamDayHeader = `
              <div class="day-group-header">
                <span>📅 ${{escapeHtml(formatFullDayHeading(item.date_key))}}</span>
                <span class="day-group-sub">${{dayCount}} ${{dayCount === 1 ? 'story' : 'stories'}}</span>
              </div>
            `;
          }}
          return `
            ${{streamDayHeader}}
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
                <div class="stream-bullet"><strong>Why It Matters (UK Finance):</strong> ${{formatBenefitHtml(item.benefit)}}</div>
                <div class="stream-bullet"><strong>🎯 Actionable Outcome:</strong> ${{escapeHtml(item.action_item)}}</div>
              </div>
              <div class="card-footer">
                <span class="pub-pill">
                  <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                  ${{escapeHtml(item.source)}} · <span class="card-date-badge">${{escapeHtml(item.date_label || '')}}</span> · ${{escapeHtml(formatRelativeTime(item.published_at))}}
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
      let lastRenderedDate = '';
      container.innerHTML = filtered.map(item => {{
        const isSaved = savedUrls.has(item.url);
        const effScore = getActiveScore(item);
        const newBadge = item.is_new ? '<span class="new-badge">NEW</span>' : '';
        const urgencyBadge = urgencyBadgeHtml(effScore, item);
        const summaryHtml = item.summary
          ? `<p class="card-summary">${{escapeHtml(item.summary)}}</p>`
          : '';
        let dayHeaderHtml = '';
        if (currentSort === 'date' && item.date_key && item.date_key !== lastRenderedDate) {{
          lastRenderedDate = item.date_key;
          const dayCount = filtered.filter(x => x.date_key === item.date_key).length;
          dayHeaderHtml = `
            <div class="day-group-header">
              <span>📅 ${{escapeHtml(formatFullDayHeading(item.date_key))}}</span>
              <span class="day-group-sub">${{dayCount}} ${{dayCount === 1 ? 'story' : 'stories'}}</span>
            </div>
          `;
        }}
        return `
          ${{dayHeaderHtml}}
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
                ${{formatBenefitHtml(item.benefit)}}
                <div class="card-outcome-line">
                  <span class="card-outcome-label">🎯 Actionable Outcome:</span>${{escapeHtml(item.action_item)}}
                </div>
              </div>
              <div class="card-footer">
                <span class="pub-pill">
                  <img class="pub-favicon" src="${{faviconUrl(item.pub_domain)}}" alt="" loading="lazy" />
                  ${{escapeHtml(item.source)}} · <span class="card-date-badge">${{escapeHtml(item.date_label || '')}}</span>
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
        "Briefing Date",
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
          it.date_key || "",
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

      if (currentFilter !== 'all' || currentTopic !== 'all' || currentDate !== 'all') {{
        currentFilter = 'all';
        currentTopic = 'all';
        currentDate = 'all';
        document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.getAttribute('data-filter') === 'all'));
        document.querySelectorAll('.topic-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-topic') === 'all'));
        document.querySelectorAll('.date-pill').forEach(p => p.classList.toggle('active', p.getAttribute('data-date') === 'all'));
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

    function toggleFontSize() {{
      const root = document.documentElement;
      const next = root.getAttribute('data-font-size') === 'large' ? 'normal' : 'large';
      root.setAttribute('data-font-size', next);
      localStorage.setItem('uk-fin-ai-font-size', next);
      const btn = document.getElementById('fontSizeToggleBtn');
      if (btn) btn.classList.toggle('nav-btn-primary', next === 'large');
      showToast(next === 'large' ? '✓ Comfort Reading Text Size: Large (A+)' : 'Text Size: Standard');
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

      if (e.key === 'f' || e.key === 'F') {{
        e.preventDefault();
        toggleFontSize();
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

      const savedFont = localStorage.getItem('uk-fin-ai-font-size') || 'normal';
      document.documentElement.setAttribute('data-font-size', savedFont);
      const fontBtn = document.getElementById('fontSizeToggleBtn');
      if (fontBtn) fontBtn.classList.toggle('nav-btn-primary', savedFont === 'large');

      buildDateFilterPills();

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
