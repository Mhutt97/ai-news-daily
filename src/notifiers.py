"""Notification delivery channels: Discord Webhook and Email (SMTP or Resend API)."""

from __future__ import annotations

from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import smtplib
import urllib.request

from src.config import Settings


def send_discord_digest(md_digest: str, settings: Settings) -> bool:
    """Send the Markdown digest to a Discord channel via Webhook embeds."""
    if not settings.discord_webhook_url:
        print("[info] DISCORD_WEBHOOK_URL not configured; skipping Discord delivery.")
        return False

    # Split Markdown by '## ' headings into clean Discord embeds
    sections = md_digest.split("\n## ")
    header = sections[0].strip()
    embeds: list[dict] = []

    COLORS = [0x3B82F6, 0x8B5CF6, 0x10B981, 0xF59E0B]

    for idx, sec in enumerate(sections[1:]):
        lines = sec.strip().splitlines()
        if not lines:
            continue
        sec_title = lines[0].strip()
        sec_body = "\n".join(lines[1:]).strip()
        if len(sec_body) > 3900:
            sec_body = sec_body[:3890].rsplit("\n", 1)[0] + "\n…"
        embeds.append(
            {
                "title": sec_title[:256],
                "description": sec_body or "No items.",
                "color": COLORS[idx % len(COLORS)],
            }
        )

    if not embeds:
        embeds.append(
            {
                "title": "Daily AI News Briefing",
                "description": md_digest[:3900],
                "color": 0x3B82F6,
            }
        )

    # Send embeds one or two at a time to stay under Discord's 6000 total char limit per request
    first_Line = header.splitlines()[0].lstrip("# ").strip() if header else "Daily AI News Briefing"
    for batch_idx in range(0, len(embeds), 2):
        batch = embeds[batch_idx : batch_idx + 2]
        payload: dict = {"embeds": batch}
        if batch_idx == 0:
            payload["content"] = f"**{first_Line}**"
        req = urllib.request.Request(
            settings.discord_webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AINewsDailyBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Discord webhook returned HTTP {resp.status}")

    print("[ok] Sent daily AI briefing to Discord webhook.")
    return True


def send_email_digest(md_digest: str, html_digest: str, settings: Settings) -> bool:
    """Send the daily AI briefing via Resend API or SMTP."""
    if not settings.has_email:
        print("[info] Email credentials not configured; skipping Email delivery.")
        return False

    today_str = datetime.now().strftime("%Y-%m-%d")
    subject = f"🤖 Daily AI News Briefing — {today_str}"
    recipients = [addr.strip() for addr in settings.email_to.split(",") if addr.strip()]

    # Option A: Resend REST API
    if settings.resend_api_key:
        sender = settings.email_from or "AI News Daily <onboarding@resend.dev>"
        payload = {
            "from": sender,
            "to": recipients,
            "subject": subject,
            "html": html_digest,
            "text": md_digest,
        }
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.resend_api_key}",
                "Content-Type": "application/json",
                "User-Agent": "AINewsDailyBot/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"Resend API returned HTTP {resp.status}")
        print(f"[ok] Sent daily AI briefing via Resend ({len(recipients)} recipient(s)).")
        return True

    # Option B: Standard SMTP (e.g., Gmail App Password)
    sender = settings.email_from or settings.smtp_user
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText(md_digest, "plain", "utf-8"))
    msg.attach(MIMEText(html_digest, "html", "utf-8"))

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(sender, recipients, msg.as_string())

    print(f"[ok] Sent daily AI briefing via SMTP ({len(recipients)} recipient(s)).")
    return True
