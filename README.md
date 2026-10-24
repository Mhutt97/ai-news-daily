# 🤖 AI News Daily (`ai-news-daily`)

An automated daily AI news aggregator, Gemini AI summarizer, and multi-channel notifier (**Discord Webhook** & **Email** via SMTP/Resend). Built with zero required third-party runtime dependencies so it runs effortlessly in **GitHub Actions (off-prem)**, Docker, or locally.

---

## ✨ Features

- **Multi-Source Aggregation**:
  - **AI Labs & Official Blogs**: OpenAI News, Google AI & DeepMind Blog, Hugging Face Blog
  - **Tech & AI Press**: TechCrunch AI, The Verge AI, Ars Technica AI, MIT Technology Review AI
  - **Research Papers**: Hugging Face Daily Papers API, ArXiv (`cs.AI` & `cs.LG`)
  - **Community Pulse**: Hacker News Algolia API (top AI/LLM stories) & Reddit (`r/MachineLearning`, `r/LocalLLaMA`)
- **AI Executive Briefing**:
  - Uses the **Gemini API** (`gemini-2.5-flash`) when `GEMINI_API_KEY` is configured, or falls back to a clean structured digest.
  - Saves both Markdown (`digests/YYYY-MM-DD.md`) and responsive HTML (`digests/YYYY-MM-DD.html`) reports.
- **Notifications**:
  - **Discord**: Rich multi-section embeds via `DISCORD_WEBHOOK_URL`.
  - **Email**: Multipart HTML + Plain Text email via **SMTP** (e.g., Gmail App Password) or **Resend API**.

---

## ☁️ Running Off-Prem via GitHub Actions (Recommended)

This repository includes a ready-to-run workflow at [`.github/workflows/daily-ai-news.yml`](.github/workflows/daily-ai-news.yml) that:
1. Runs automatically every day at **08:00 UTC** (and supports 1-click manual triggers via **Run workflow**).
2. Fetches and summarizes the latest AI news using Gemini.
3. Sends the briefing to your **Discord** channel and/or **Email**.
4. Archives the daily `.md` and `.html` reports both as a **GitHub Actions Artifact** and by committing them to [`digests/`](digests/).

### Step 1: Push to GitHub

Using the GitHub CLI (`gh`) or standard `git`:

```powershell
cd ai-news-daily

# Option A: Using GitHub CLI (creates repo and pushes in one command)
gh repo create ai-news-daily --private --source=. --remote=origin --push

# Option B: Using a repo created on github.com
git remote add origin https://github.com/<your-username>/ai-news-daily.git
git push -u origin main
```

### Step 2: Configure GitHub Repository Secrets

In your GitHub repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add whichever channels you want to use:

| Secret Name | Required? | Description |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | Recommended | Google AI Studio API key for AI executive summaries (falls back to structured digest if omitted) |
| `DISCORD_WEBHOOK_URL` | Optional | Discord channel Webhook URL (`Server Settings → Integrations → Webhooks`) |
| `RESEND_API_KEY` | Optional | Resend API key (`re_...`) if sending email via Resend |
| `SMTP_HOST` | Optional | Defaults to `smtp.gmail.com` |
| `SMTP_PORT` | Optional | Defaults to `587` |
| `SMTP_USER` | Optional | Your SMTP username / Gmail address |
| `SMTP_PASSWORD` | Optional | Your 16-character Gmail App Password or SMTP password |
| `EMAIL_FROM` | Optional | Sender address (defaults to `SMTP_USER` or Resend default) |
| `EMAIL_TO` | Optional | Comma-separated recipient email address(es) |

### Step 3: Trigger a Test Run on GitHub

1. Open your repository on GitHub and click the **Actions** tab.
2. Select **Daily AI News Briefing** in the left sidebar.
3. Click **Run workflow** → **Run workflow** to test it immediately off-prem!

---

## 💻 Running Locally or via Docker

### Local Execution
1. Copy `.env.example` to `.env` and fill in your credentials:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Run a dry-run test:
   ```powershell
   python main.py --dry-run
   ```
3. Run live:
   ```powershell
   python main.py
   ```

### Docker Execution
```bash
docker build -t ai-news-daily .
docker run --rm --env-file .env ai-news-daily
```
