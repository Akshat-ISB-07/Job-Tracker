"""
Job Tracker — scrapes company career pages, diffs against seen jobs,
and sends a Gmail notification for any new listings.
"""

import json
import os
import smtplib
import hashlib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# ── Config ────────────────────────────────────────────────────────────────────

SEEN_JOBS_FILE = Path("seen_jobs.json")

# Gmail credentials — set these as GitHub Secrets (or local env vars)
GMAIL_USER   = os.environ["GMAIL_USER"]    # your.email@gmail.com
GMAIL_PASS   = os.environ["GMAIL_PASS"]    # Gmail App Password (16 chars)
NOTIFY_EMAIL = os.environ.get("NOTIFY_EMAIL", GMAIL_USER)  # where to send alerts

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── URL list ──────────────────────────────────────────────────────────────────
# Each entry needs:
#   url       — the careers page to scrape
#   company   — display name
#   selector  — CSS selector that matches individual job listing elements
#   title_sel — CSS selector for the job title *within* each listing element
#   link_sel  — CSS selector for the <a> tag (or None to use the listing itself)
#
# Examples for popular ATS platforms are pre-filled. Adjust selectors to match
# the exact markup of each page (use browser DevTools → Inspect).

URLS = [
   {
        "company": "Alvarez & Marsal",
        "url": "https://careers.alvarezandmarsal.com/search/jobs/in/country/india",
        "selector": "div.jobs-section__item.padded-v-small",
        "title_sel": "h2.heading-4 a",
        "link_sel": "h2.heading-4 a",
    },
    # ── Add more companies below ──────────────────────────────────────────────
    # {
    #     "company": "Linear",
    #     "url": "https://linear.app/careers",
    #     "selector": ".career-item",
    #     "title_sel": ".career-title",
    #     "link_sel": "a",
    # },
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_seen() -> dict:
    if SEEN_JOBS_FILE.exists():
        return json.loads(SEEN_JOBS_FILE.read_text())
    return {}


def save_seen(seen: dict) -> None:
    SEEN_JOBS_FILE.write_text(json.dumps(seen, indent=2))


def job_id(company: str, title: str, link: str) -> str:
    """Stable hash so we recognise the same job across runs."""
    raw = f"{company}|{title.strip().lower()}|{link.strip()}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def scrape(entry: dict) -> list[dict]:
    """Return a list of {id, title, link, company} dicts for one URL entry."""
    try:
        resp = requests.get(entry["url"], headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except Exception as exc:
        print(f"  ⚠️  {entry['company']}: fetch failed — {exc}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select(entry["selector"])

    if not items:
        print(f"  ⚠️  {entry['company']}: 0 elements matched '{entry['selector']}' — check selector")

    jobs = []
    for el in items:
        # title
        title_el = el.select_one(entry["title_sel"]) if entry["title_sel"] else el
        title = title_el.get_text(strip=True) if title_el else el.get_text(strip=True)

        # link
        if entry["link_sel"]:
            a = el.select_one(entry["link_sel"])
        else:
            a = el if el.name == "a" else el.find("a")
        href = a["href"] if a and a.get("href") else entry["url"]
        if href.startswith("/"):
            from urllib.parse import urlparse
            base = urlparse(entry["url"])
            href = f"{base.scheme}://{base.netloc}{href}"

        jid = job_id(entry["company"], title, href)
        jobs.append({"id": jid, "title": title, "link": href, "company": entry["company"]})

    return jobs


# ── Email ─────────────────────────────────────────────────────────────────────

def send_email(new_jobs: list[dict]) -> None:
    subject = f"🆕 {len(new_jobs)} new job(s) found — {datetime.now().strftime('%b %d, %Y')}"

    # Group by company for readability
    by_company: dict[str, list] = {}
    for j in new_jobs:
        by_company.setdefault(j["company"], []).append(j)

    # Plain-text body
    text_lines = [f"Found {len(new_jobs)} new job listing(s):\n"]
    for company, jobs in by_company.items():
        text_lines.append(f"{company} ({len(jobs)})")
        for j in jobs:
            text_lines.append(f"  • {j['title']}\n    {j['link']}")
        text_lines.append("")
    text_body = "\n".join(text_lines)

    # HTML body
    html_rows = ""
    for company, jobs in by_company.items():
        html_rows += f"<h3 style='margin:16px 0 6px'>{company}</h3><ul>"
        for j in jobs:
            html_rows += (
                f"<li style='margin:4px 0'>"
                f"<a href='{j['link']}' style='color:#5046e5'>{j['title']}</a>"
                f"</li>"
            )
        html_rows += "</ul>"

    html_body = f"""
    <html><body style="font-family:sans-serif;max-width:600px;margin:auto;padding:20px">
      <h2 style="color:#111">🆕 {len(new_jobs)} new job listing(s)</h2>
      {html_rows}
      <p style="color:#888;font-size:12px;margin-top:32px">
        Sent by your GitHub Actions job tracker · {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
      </p>
    </body></html>
    """

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, NOTIFY_EMAIL, msg.as_string())

    print(f"  ✉️  Email sent to {NOTIFY_EMAIL}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    seen   = load_seen()
    new_jobs: list[dict] = []

    for entry in URLS:
        print(f"Checking {entry['company']} …")
        jobs = scrape(entry)
        print(f"  Found {len(jobs)} listing(s) on page")

        for job in jobs:
            if job["id"] not in seen:
                new_jobs.append(job)
                seen[job["id"]] = {
                    "title":     job["title"],
                    "link":      job["link"],
                    "company":   job["company"],
                    "first_seen": datetime.utcnow().isoformat(),
                }

    print(f"\n{len(new_jobs)} new job(s) found across all companies.")

    if new_jobs:
        send_email(new_jobs)

    save_seen(seen)
    print("seen_jobs.json updated ✓")


if __name__ == "__main__":
    main()
