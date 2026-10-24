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


def analyze_uk_finance_benefit(item: NewsItem) -> tuple[int, str, str, str]:
    """
    Evaluate a news item for UK Finance Team priority.
    Returns (priority_score_0_to_100, priority_label, concise_summary, uk_finance_benefit).
    """
    text = f"{item.title} {item.summary} {item.source} {item.category}".lower()

    # Clean up redundant source suffixes in Google News summaries
    clean_summary = item.summary or ""
    if clean_summary and clean_summary.lower().startswith(item.title[:30].lower()):
        clean_summary = ""

    # Default score based on category
    score = 40
    tier = "General AI News"
    benefit = (
        "Keeps the team informed on broader AI capabilities and industry direction "
        "that may shape future enterprise software."
    )

    if item.category == "UK Finance & CFO AI":
        score = 92
        tier = "High UK Finance Impact"
        benefit = (
            "Directly relevant to UK CFOs and finance teams benchmarking AI adoption, "
            "governance, and financial operations in the UK market."
        )

    # Specific keyword rules tailored to UK Finance Teams (FP&A, Audit, FCA, Tax, Security, Agents)
    if re.search(
        r"\b(fca|financial conduct authority|bank of england|icaew|acca|frc|hmrc|uk finance|uk cci|financial reporting council)\b",
        text,
    ):
        score = max(score, 98)
        tier = "High UK Finance Impact"
        benefit = (
            "UK Regulatory & Compliance Impact: Helps UK finance, risk, and reporting teams "
            "stay aligned with FCA, ICAEW/ACCA, and UK disclosure expectations."
        )
    elif re.search(
        r"\b(audit|auditors|auditing|assurance|soc 2|attestation|internal control)\b",
        text,
    ):
        score = max(score, 94)
        tier = "High UK Finance Impact"
        benefit = (
            "Audit & Assurance Readiness: Provides frameworks for auditing AI-assisted "
            "decisions, strengthening internal controls and external audit confidence."
        )
    elif re.search(
        r"\b(cfo|cfos|finance leader|finance leaders|finance team|finance teams|accounting|accountant|fp&a|bookkeeping|reconciliation|accounts payable|payroll|erp)\b",
        text,
    ):
        score = max(score, 95)
        tier = "High UK Finance Impact"
        benefit = (
            "CFO & Finance Operations: Directly benchmarks how UK & European finance leaders "
            "are deploying AI across reporting, forecasting, and month-end close."
        )
    elif re.search(
        r"\b(privacy|containment|securing|no internet|live internet|red-team|gdpr|data protection|gmail)\b",
        text,
    ):
        score = max(score, 84)
        tier = "Finance Ops & Governance"
        benefit = (
            "Financial Data Security & Privacy: Critical for finance teams evaluating data "
            "leakage risks before uploading sensitive management accounts or PII into AI tools."
        )
    elif re.search(
        r"\b(agent|agents|enterprise|frontier model|gemini|chatgpt|claude|workflow|automation|voice|local|storage|scaling)\b",
        text,
    ):
        score = max(score, 78)
        tier = "Finance Ops & Productivity"
        benefit = (
            "Workflow Automation & Enterprise AI: Highlights frontier model and AI agent "
            "capabilities that can streamline financial analysis, reporting, and operations."
        )
    elif any(k in text for k in ("quantization", "test-time", "reasoning", "pass@", "diffusion", "speed", "cost")):
        score = max(score, 65)
        tier = "AI Efficiency & Research"
        benefit = (
            "AI Cost & Accuracy: Advances in model reasoning efficiency help lower inference "
            "costs and improve reliability for analytical tasks."
        )

    if not clean_summary:
        if item.category == "UK Finance & CFO AI":
            clean_summary = (
                f"Latest UK finance and accounting AI coverage from {item.source}, "
                f"focusing on practical adoption, governance, and compliance for finance leaders."
            )
        else:
            clean_summary = (
                f"Published by {item.source} ({item.category}) — click through to read the full coverage."
            )

    return score, tier, clean_summary, benefit


def enrich_items_with_gemini(
    items: list[NewsItem], settings: Settings
) -> dict[int, dict[str, object]]:
    """Optionally use Gemini API to refine concise summaries and UK finance team benefits."""
    if not settings.gemini_api_key or not items:
        return {}

    subset = items[:30]
    prompt_lines = [
        "You are a UK CFO & Finance Director advisor. For each news item below (indexed 0..N), return a JSON array of objects with keys:",
        '`{"idx": int, "score": int (1-100 priority for a UK finance team), "summary": "concise 1-sentence plain-English summary", "benefit": "concise 1-sentence practical takeaway for a UK finance team (or general awareness note)"}`.',
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
        score, tier, summary, benefit = analyze_uk_finance_benefit(item)
        if idx in gemini_map:
            g = gemini_map[idx]
            score = int(g.get("score", score))
            summary = str(g.get("summary") or summary)
            benefit = str(g.get("benefit") or benefit)
            if score >= 85:
                tier = "High UK Finance Impact"
            elif score >= 70:
                tier = "Finance Ops & Productivity"
            else:
                tier = "General AI News"

        cards.append(
            {
                "title": item.title,
                "url": item.url,
                "source": item.source,
                "category": item.category,
                "published_at": item.published_at,
                "score": score,
                "tier": tier,
                "summary": summary,
                "benefit": benefit,
            }
        )

    cards.sort(key=lambda c: int(c["score"]), reverse=True)
    return cards


def build_dashboard_html(cards: list[dict[str, object]], date_str: str) -> str:
    """Render a self-contained, interactive UK Finance & General AI News Dashboard HTML."""
    high_impact_count = sum(1 for c in cards if int(c["score"]) >= 85)
    ops_count = sum(1 for c in cards if 70 <= int(c["score"]) < 85)
    general_count = sum(1 for c in cards if int(c["score"]) < 70)

    cards_json = json.dumps(cards, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="en-GB">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>UK Finance & AI Daily Intelligence Dashboard — {html.escape(date_str)}</title>
  <style>
    :root {{
      --bg: #0b1120;
      --surface: #111827;
      --surface-hover: #1e293b;
      --border: #1f2937;
      --text: #f8fafc;
      --muted: #94a3b8;
      --accent: #3b82f6;
      --gold-bg: rgba(245, 158, 11, 0.12);
      --gold-border: rgba(245, 158, 11, 0.4);
      --gold-text: #fbbf24;
      --emerald-bg: rgba(16, 185, 129, 0.12);
      --emerald-border: rgba(16, 185, 129, 0.35);
      --emerald-text: #34d399;
      --blue-bg: rgba(59, 130, 246, 0.12);
      --blue-border: rgba(59, 130, 246, 0.35);
      --blue-text: #60a5fa;
      --benefit-bg: rgba(30, 41, 59, 0.75);
    }}
    [data-theme="light"] {{
      --bg: #f1f5f9;
      --surface: #ffffff;
      --surface-hover: #f8fafc;
      --border: #e2e8f0;
      --text: #0f172a;
      --muted: #475569;
      --accent: #2563eb;
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
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.55;
    }}
    .container {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 64px;
    }}
    header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--border);
    }}
    .brand-badge {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 12px;
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
      font-size: clamp(24px, 3vw, 32px);
      letter-spacing: -0.02em;
    }}
    .subtitle {{
      margin: 6px 0 0;
      color: var(--muted);
      font-size: 15px;
    }}
    .header-actions {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .btn {{
      cursor: pointer;
      border: 1px solid var(--border);
      background: var(--surface);
      color: var(--text);
      padding: 9px 14px;
      border-radius: 10px;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.15s ease;
    }}
    .btn:hover {{
      border-color: var(--accent);
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 14px;
      margin: 24px 0;
    }}
    .kpi-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 16px 20px;
    }}
    .kpi-label {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--muted);
    }}
    .kpi-val {{
      font-size: 28px;
      font-weight: 800;
      margin-top: 4px;
    }}
    .kpi-sub {{
      font-size: 12px;
      color: var(--muted);
      margin-top: 2px;
    }}
    .controls {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 22px;
      background: var(--surface);
      border: 1px solid var(--border);
      padding: 12px 16px;
      border-radius: 14px;
    }}
    .tabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .tab {{
      cursor: pointer;
      border: 1px solid transparent;
      background: transparent;
      color: var(--muted);
      padding: 8px 14px;
      border-radius: 9px;
      font-size: 13px;
      font-weight: 600;
      transition: all 0.15s;
    }}
    .tab.active {{
      background: var(--accent);
      color: #ffffff;
    }}
    .search-box {{
      display: flex;
      gap: 10px;
      flex: 1;
      max-width: 340px;
    }}
    .search-input {{
      width: 100%;
      padding: 9px 13px;
      border-radius: 9px;
      border: 1px solid var(--border);
      background: var(--bg);
      color: var(--text);
      font-size: 13px;
    }}
    .section-banner {{
      margin: 28px 0 14px;
      display: flex;
      align-items: center;
      justify-content: space-between;
    }}
    .section-banner h2 {{
      margin: 0;
      font-size: 19px;
    }}
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
      gap: 16px;
    }}
    .news-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 20px;
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
    .score-pill {{
      font-size: 11px;
      font-weight: 700;
      color: var(--muted);
    }}
    .card-title {{
      margin: 0 0 10px;
      font-size: 16px;
      font-weight: 700;
      line-height: 1.4;
    }}
    .card-title a {{
      color: var(--text);
      text-decoration: none;
    }}
    .card-title a:hover {{
      color: var(--accent);
      text-decoration: underline;
    }}
    .card-summary {{
      font-size: 13.5px;
      color: var(--muted);
      margin: 0 0 14px;
    }}
    .benefit-box {{
      background: var(--benefit-bg);
      border-left: 3px solid var(--gold-text);
      padding: 10px 12px;
      border-radius: 6px;
      font-size: 12.5px;
      margin-bottom: 14px;
    }}
    .benefit-box strong {{
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--gold-text);
      margin-bottom: 3px;
    }}
    .card-footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--muted);
      padding-top: 10px;
      border-top: 1px solid var(--border);
    }}
    .read-link {{
      color: var(--accent);
      font-weight: 600;
      text-decoration: none;
    }}
    .empty-state {{
      grid-column: 1 / -1;
      text-align: center;
      padding: 48px;
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="brand-badge">🇬🇧💷 UK Finance Team Priority Edition</div>
        <h1>Daily AI News & CFO Intelligence Dashboard</h1>
        <p class="subtitle">Updated {html.escape(date_str)} · Stories ranked by practical impact for UK Finance, Accounting, Audit & FP&A teams</p>
      </div>
      <div class="header-actions">
        <button class="btn" id="themeToggle" onclick="toggleTheme()">☀️ Light / 🌙 Dark</button>
      </div>
    </header>

    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">🇬🇧 High UK Finance Impact</div>
        <div class="kpi-val" style="color: var(--gold-text);">{high_impact_count}</div>
        <div class="kpi-sub">FCA, CFO, Audit, Accounting & UK Regulation</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">⚡ Finance Ops & Productivity</div>
        <div class="kpi-val" style="color: var(--emerald-text);">{ops_count}</div>
        <div class="kpi-sub">AI Agents, Data Security & Workflow Automation</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">🌐 General AI & Research</div>
        <div class="kpi-val" style="color: var(--blue-text);">{general_count}</div>
        <div class="kpi-sub">Global AI Labs, Tech Press, ArXiv & HN</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">📊 Total Curated Stories</div>
        <div class="kpi-val">{len(cards)}</div>
        <div class="kpi-sub">Prioritised & deduplicated from 11 feeds</div>
      </div>
    </div>

    <div class="controls">
      <div class="tabs">
        <button class="tab active" data-filter="all" onclick="setFilter('all', this)">All (Prioritised for UK Finance)</button>
        <button class="tab" data-filter="high" onclick="setFilter('high', this)">🇬🇧💷 UK Finance & CFO Focus ({high_impact_count})</button>
        <button class="tab" data-filter="ops" onclick="setFilter('ops', this)">⚡ Productivity & Data Security ({ops_count})</button>
        <button class="tab" data-filter="general" onclick="setFilter('general', this)">🌐 General AI & Research ({general_count})</button>
      </div>
      <div class="search-box">
        <input type="text" id="searchInput" class="search-input" placeholder="Search FCA, audit, OpenAI, agents..." oninput="renderCards()" />
      </div>
    </div>

    <div id="cardsContainer" class="cards-grid"></div>
  </div>

  <script>
    const ITEMS = {cards_json};
    let currentFilter = 'all';

    function escapeHtml(str) {{
      const d = document.createElement('div');
      d.textContent = str || '';
      return d.innerHTML;
    }}

    function badgeClass(score) {{
      if (score >= 85) return 'badge-high';
      if (score >= 70) return 'badge-ops';
      return 'badge-gen';
    }}

    function badgeIcon(score) {{
      if (score >= 85) return '🇬🇧💷';
      if (score >= 70) return '⚡';
      return '🌐';
    }}

    function setFilter(filter, btn) {{
      currentFilter = filter;
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      renderCards();
    }}

    function renderCards() {{
      const q = (document.getElementById('searchInput').value || '').toLowerCase().trim();
      const container = document.getElementById('cardsContainer');

      const filtered = ITEMS.filter(item => {{
        if (currentFilter === 'high' && item.score < 85) return false;
        if (currentFilter === 'ops' && (item.score < 70 || item.score >= 85)) return false;
        if (currentFilter === 'general' && item.score >= 70) return false;
        if (q) {{
          const hay = (item.title + ' ' + item.summary + ' ' + item.benefit + ' ' + item.source + ' ' + item.category).toLowerCase();
          if (!hay.includes(q)) return false;
        }}
        return true;
      }});

      if (!filtered.length) {{
        container.innerHTML = '<div class="empty-state">No stories match your current filter or search query.</div>';
        return;
      }}

      container.innerHTML = filtered.map(item => `
        <article class="news-card">
          <div>
            <div class="card-top">
              <span class="badge ${{badgeClass(item.score)}}">${{badgeIcon(item.score)}} ${{escapeHtml(item.tier)}}</span>
              <span class="score-pill">Priority: ${{item.score}}/100</span>
            </div>
            <h3 class="card-title">
              <a href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title)}}</a>
            </h3>
            <p class="card-summary">${{escapeHtml(item.summary)}}</p>
          </div>
          <div>
            <div class="benefit-box">
              <strong>🇬🇧 How This Benefits a UK Finance Team</strong>
              ${{escapeHtml(item.benefit)}}
            </div>
            <div class="card-footer">
              <span>${{escapeHtml(item.source)}} · ${{escapeHtml(item.published_at)}}</span>
              <a class="read-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noopener noreferrer">Read article →</a>
            </div>
          </div>
        </article>
      `).join('');
    }}

    function toggleTheme() {{
      const root = document.documentElement;
      const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      root.setAttribute('data-theme', next);
      localStorage.setItem('ai-news-theme', next);
    }}

    (function init() {{
      const saved = localStorage.getItem('ai-news-theme');
      if (saved) document.documentElement.setAttribute('data-theme', saved);
      renderCards();
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
