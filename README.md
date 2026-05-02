# Job Tracker

Monitors company career pages for new listings and emails you when something new appears.
Runs automatically via GitHub Actions — no server needed.

---

## Setup (5 steps)

### 1. Create a Gmail App Password

Gmail requires an App Password (not your regular password) for SMTP access.

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Search for **"App Passwords"** → create one named "Job Tracker"
4. Copy the 16-character password

### 2. Fork / clone this repo

```bash
git clone https://github.com/YOUR_USERNAME/job-tracker.git
cd job-tracker
```

### 3. Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name    | Value                              |
|----------------|------------------------------------|
| `GMAIL_USER`   | your.email@gmail.com               |
| `GMAIL_PASS`   | the 16-char App Password from step 1 |
| `NOTIFY_EMAIL` | email where you want alerts (can be same as GMAIL_USER) |

### 4. Add your URLs to `tracker.py`

Open `tracker.py` and edit the `URLS` list. For each company you want to track:

```python
{
    "company": "Linear",
    "url": "https://linear.app/careers",
    "selector": ".career-item",       # CSS selector for each job row
    "title_sel": ".career-title",     # selector for the title inside the row
    "link_sel": "a",                  # selector for the <a> tag (or None)
}
```

**How to find the right CSS selectors:**
1. Open the careers page in Chrome/Firefox
2. Right-click a job title → **Inspect**
3. Find the repeating element that wraps each job listing
4. Copy its class name (e.g. `.job-listing`, `a.position`)

### 5. Push and enable Actions

```bash
git add .
git commit -m "init"
git push
```

Then go to your repo → **Actions tab** → enable workflows if prompted.
Click **"Run workflow"** to trigger an immediate test run.

---

## How it works

```
GitHub Actions (every 6 hours)
        ↓
tracker.py fetches each careers page
        ↓
Parses job listings with BeautifulSoup
        ↓
Compares against seen_jobs.json (committed in repo)
        ↓
New jobs? → sends HTML email via Gmail SMTP
        ↓
Updates seen_jobs.json and commits it back
```

---

## Customising the schedule

Edit `.github/workflows/track.yml`:

```yaml
- cron: "0 */6 * * *"   # every 6 hours (default)
- cron: "0 9,17 * * *"  # 9 AM and 5 PM UTC
- cron: "0 9 * * 1-5"   # weekdays at 9 AM UTC
```

Use [crontab.guru](https://crontab.guru) to build your schedule.

---

## Common ATS selectors

| Platform    | `selector`                    | `title_sel`         | `link_sel` |
|-------------|-------------------------------|---------------------|------------|
| Greenhouse  | `.opening a`                  | (None — text of a)  | None       |
| Lever       | `.posting h5`                 | `h5`                | `a`        |
| Ashby       | `a[data-testid="job-listing"]`| `h3`                | None       |
| Workable    | `li.jobs-item a`              | `.title`            | None       |

These are starting points — verify with DevTools as markup can change.

---

## Local testing

```bash
pip install requests beautifulsoup4

export GMAIL_USER="you@gmail.com"
export GMAIL_PASS="your-app-password"
export NOTIFY_EMAIL="you@gmail.com"

python tracker.py
```

On the first run every job on the page is "new" (since `seen_jobs.json` is empty).
Subsequent runs only alert you to listings that weren't there before.
