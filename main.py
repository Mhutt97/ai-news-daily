"""CLI entry point for AI News Daily."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

from src.config import Settings
from src.dashboard import generate_dashboard_files
from src.notifiers import send_discord_digest, send_email_digest
from src.sources import fetch_all_news
from src.summarizer import generate_and_save_digest, markdown_to_html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch latest AI news, generate a daily digest, and deliver via Discord & Email."
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=None,
        help="Lookback window in hours (defaults to LOOKBACK_HOURS in .env or 24).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch news and save local Markdown/HTML digests without sending notifications.",
    )
    parser.add_argument(
        "--notify-from-file",
        type=str,
        default=None,
        help="Send an existing Markdown digest file to Discord and Email without re-fetching.",
    )
    return parser.parse_args()


def main() -> int:
    # Ensure UTF-8 stdout on Windows consoles
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    args = parse_args()
    settings = Settings.from_env(lookback_override=args.hours)

    if args.notify_from_file:
        md_path = Path(args.notify_from_file).resolve()
        if not md_path.exists():
            print(f"[error] File not found: {md_path}")
            return 1
        md_digest = md_path.read_text(encoding="utf-8")
        html_digest = markdown_to_html(md_digest)
        html_path = md_path.with_suffix(".html")
        html_path.write_text(html_digest, encoding="utf-8")
    else:
        print(
            f"[info] Fetching AI news from the last {settings.lookback_hours} hours "
            f"(max {settings.max_items_per_source} items/source)..."
        )
        items = fetch_all_news(
            lookback_hours=settings.lookback_hours,
            max_items_per_source=settings.max_items_per_source,
        )
        print(f"[info] Retrieved {len(items)} unique AI news items across all categories.")

        md_digest, html_digest, md_path, html_path = generate_and_save_digest(
            items, settings
        )
        dashboard_path, _cards = generate_dashboard_files(items, settings)
        print(f"[ok] Saved Markdown digest:   {md_path}")
        print(f"[ok] Saved HTML email digest: {html_path}")
        print(f"[ok] Saved Web Dashboard:     {dashboard_path}")
        if os.getenv("GITHUB_ACTIONS") == "true":
            subprocess.run(
                ["git", "add", "docs/index.html", "docs/data.json"], check=False
            )

    if args.dry_run:
        print("\n--- DRY RUN PREVIEW (First 45 lines) ---")
        preview_lines = md_digest.splitlines()[:45]
        print("\n".join(preview_lines))
        if len(md_digest.splitlines()) > 45:
            print(f"\n... ({len(md_digest.splitlines()) - 45} more lines in {md_path})")
        return 0

    if settings.has_discord:
        try:
            send_discord_digest(md_digest, settings)
        except Exception as exc:
            print(f"[error] Discord delivery failed: {exc}")

    if settings.has_email:
        try:
            send_email_digest(md_digest, html_digest, settings)
        except Exception as exc:
            print(f"[error] Email delivery failed: {exc}")

    if not settings.has_discord and not settings.has_email:
        print(
            "[info] No Discord or Email credentials found in .env yet. "
            "Copy .env.example to .env and add DISCORD_WEBHOOK_URL or SMTP/Resend settings to enable live delivery."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
