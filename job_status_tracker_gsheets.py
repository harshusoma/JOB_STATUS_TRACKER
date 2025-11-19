import os
import time
import random
import re
import json
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load env variables
load_dotenv()

# ---- Google Sheets config ----
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH")
HEADLESS = os.getenv("HEADLESS", "False").lower() == "true"

WORKDAY_CACHE_PATH = "workday_cache.json"


# ============================================================
# 1. Patterns for status detection
# ============================================================

CLOSED_PATTERNS = [
    "no longer accepting applications",
    "no longer available",
    "job has expired",
    "position has been filled",
    "position filled",
    "job is closed",
    "this job is closed",
    "no longer posted",
    "no longer active",
]

LINKEDIN_REJECT_PATTERNS = [
    "no longer being considered for this job",
    "you’re no longer being considered",
    "you are no longer in consideration",
]

LINKEDIN_REVIEW_PATTERNS = [
    "your application is under review",
    "your application is being reviewed"
]

LINKEDIN_VIEWED_PATTERNS = [
    "your application has been viewed",
    "your application was viewed"
]

LINKEDIN_SUBMITTED_PATTERNS = [
    "we received your application",
    "application submitted"
]

WORKDAY_REJECT_PATTERNS = [
    "no longer in consideration",
    "not selected",
    "no longer being considered"
]

WORKDAY_INPROCESS_PATTERNS = [
    "in progress",
    "under review",
    "under consideration"
]


# ============================================================
# 2. Helpers
# ============================================================

def detect_domain(url: str) -> str:
    url = url.lower()
    if "linkedin.com" in url:
        return "linkedin"
    if "myworkdayjobs.com" in url:
        return "workday"
    if "greenhouse.io" in url:
        return "greenhouse"
    if "lever.co" in url:
        return "lever"
    if "taleo.net" in url:
        return "taleo"
    if "smartrecruiters.com" in url:
        return "smartrecruiters"
    return "generic"


def extract_workday_tenant(url: str):
    """
    Examples:
    https://spectris.wd3.myworkdayjobs.com/...  → spectris
    https://northrop.wd1.myworkdayjobs.com/...  → northrop
    """
    match = re.search(r"https://([^\.]+)\.wd\d+\.myworkdayjobs\.com", url)
    if match:
        return match.group(1)
    return None


def load_workday_cache() -> dict:
    path = Path(WORKDAY_CACHE_PATH)
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_workday_cache(cache: dict) -> None:
    with open(WORKDAY_CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


# ============================================================
# 3. Google Sheets helpers
# ============================================================

def get_gsheet():
    if not GOOGLE_SHEET_ID or not GOOGLE_CREDS_PATH:
        raise RuntimeError("GOOGLE_SHEET_ID or GOOGLE_SHEETS_CREDENTIALS_PATH missing in .env")

    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_CREDS_PATH, scope)
    client = gspread.authorize(creds)
    sh = client.open_by_key(GOOGLE_SHEET_ID)
    return sh


# ============================================================
# 4. Login functions
# ============================================================

def linkedin_login(page) -> bool:
    email = os.getenv("LINKEDIN_EMAIL")
    pwd = os.getenv("LINKEDIN_PASSWORD")

    if not email or not pwd:
        print("⚠️ No LinkedIn credentials found in .env.")
        return False

    print("🌐 Logging into LinkedIn...")
    try:
        page.goto("https://www.linkedin.com/login", timeout=45000)
        time.sleep(3)
        page.fill("#username", email)
        page.fill("#password", pwd)
        page.click("button[type=submit]")

        page.wait_for_load_state("networkidle", timeout=45000)
        time.sleep(4)

        if "feed" in page.url or "/jobs" in page.url:
            print("✅ LinkedIn login successful.")
            return True

        print("⚠️ LinkedIn login may be challenged (MFA/captcha). Continuing anyway.")
        return True
    except Exception as e:
        print(f"❌ LinkedIn login failed: {e}")
        return False


def workday_try_login(page, tenant: str, cache: dict) -> bool:
    """
    Workday login with smart password detection:
    - if tenant in cache: try cached password index first
    - otherwise: try pwd1 then pwd2
    - store result in cache[tenant] = 1 or 2 on success
    """
    email = os.getenv("WORKDAY_EMAIL")
    pwd1 = os.getenv("WORKDAY_PASSWORD_1")
    pwd2 = os.getenv("WORKDAY_PASSWORD_2")

    if not email or not pwd1 or not pwd2:
        print("⚠️ Missing Workday credentials in .env.")
        return False

    login_url = f"https://{tenant}.myworkday.com/{tenant}/login.htm"
    print(f"🌐 Workday tenant '{tenant}' login URL: {login_url}")

    def attempt_login(password: str) -> bool:
        try:
            page.goto(login_url, timeout=45000)
            time.sleep(3)
            page.fill("input[type=email], input[type=text]", email)
            page.fill("input[type=password]", password)
            page.keyboard.press("Enter")
            time.sleep(5)
            if "login" not in page.url.lower():
                return True
            return False
        except Exception:
            return False

    # decide order using cache
    order = [1, 2]
    if tenant in cache:
        cached_idx = cache[tenant]
        if cached_idx == 2:
            order = [2, 1]

    for idx in order:
        pwd = pwd1 if idx == 1 else pwd2
        print(f"🔑 Trying Workday password #{idx} for tenant {tenant}...")
        if attempt_login(pwd):
            print(f"✅ Workday login successful for tenant {tenant} with password #{idx}")
            cache[tenant] = idx
            return True

    print(f"❌ Workday login failed for tenant {tenant} with both passwords.")
    return False


def greenhouse_login(page) -> bool:
    """
    Placeholder: Most Greenhouse applications don’t require candidate login.
    If you later use Greenhouse Candidate Portal, implement login here.
    """
    return False


def lever_login(page) -> bool:
    """
    Placeholder: Implement Lever candidate login here if needed later.
    """
    return False


# ============================================================
# 5. Status classification
# ============================================================

def classify_status(text: str, domain: str) -> str:
    t = text.lower()

    # LinkedIn – application level
    if domain == "linkedin":
        for p in LINKEDIN_REJECT_PATTERNS:
            if p in t:
                return "APPLICATION REJECTED (LinkedIn)"
        for p in LINKEDIN_REVIEW_PATTERNS:
            if p in t:
                return "APPLICATION UNDER REVIEW (LinkedIn)"
        for p in LINKEDIN_VIEWED_PATTERNS:
            if p in t:
                return "APPLICATION VIEWED (LinkedIn)"
        for p in LINKEDIN_SUBMITTED_PATTERNS:
            if p in t:
                return "APPLICATION SUBMITTED (LinkedIn)"
        for p in CLOSED_PATTERNS:
            if p in t:
                return "JOB CLOSED (LinkedIn)"
        return "UNKNOWN (LinkedIn)"

    # Workday – application + posting
    if domain == "workday":
        for p in WORKDAY_REJECT_PATTERNS:
            if p in t:
                return "APPLICATION REJECTED (Workday)"
        for p in WORKDAY_INPROCESS_PATTERNS:
            if p in t:
                return "APPLICATION IN PROCESS (Workday)"
        for p in CLOSED_PATTERNS:
            if p in t:
                return "JOB CLOSED (Workday)"
        return "UNKNOWN (Workday)"

    # Greenhouse / Lever / generic posting status
    for p in CLOSED_PATTERNS:
        if p in t:
            return f"JOB CLOSED ({domain})"

    return f"UNKNOWN ({domain})"


# ============================================================
# 6. Sheet processing
# ============================================================

def find_columns(header_row):
    """
    header_row: list of strings from first row
    returns (url_col_idx, decision_col_idx) 0-based
    """
    url_idx = None
    decision_idx = None
    for i, h in enumerate(header_row):
        name = (h or "").strip().lower()
        if name == "url":
            url_idx = i
        if name == "decision":
            decision_idx = i
    return url_idx, decision_idx


def process_worksheet(ws, page, workday_cache: dict) -> int:
    """
    ws: gspread Worksheet
    Returns number of updated rows.
    """
    values = ws.get_all_values()
    if not values:
        return 0

    header = values[0]
    url_idx, decision_idx = find_columns(header)
    if url_idx is None or decision_idx is None:
        print(f"⚠️ Sheet '{ws.title}': missing 'URL' or 'Decision' column – skipping.")
        return 0

    updated = 0

    for i in range(1, len(values)):  # start from second row
        row = values[i]
        sheet_row_idx = i + 1  # 1-based in Sheets

        if len(row) <= max(url_idx, decision_idx):
            continue

        url = row[url_idx].strip() if len(row) > url_idx and row[url_idx] else ""
        decision_val = row[decision_idx].strip() if len(row) > decision_idx and row[decision_idx] else ""

        if not url:
            continue

        # skip already filled decisions (remove this condition to force-refresh all)
        if decision_val:
            continue

        domain = detect_domain(url)
        print(f"[{ws.title}] Row {sheet_row_idx} → visiting ({domain}): {url}")

        # Workday: attempt tenant-specific login using cache
        if domain == "workday":
            tenant = extract_workday_tenant(url)
            if tenant:
                workday_try_login(page, tenant, workday_cache)

        # Greenhouse / Lever: currently posting-level only (hooks available above)

        try:
            page.goto(url, timeout=45000)
            time.sleep(5)
            content = page.content()
            status = classify_status(content, domain)
        except Exception as e:
            status = f"ERROR: {type(e).__name__}"

        print(f"   → Status: {status}")
        ws.update_cell(sheet_row_idx, decision_idx + 1, status)
        updated += 1

        time.sleep(random.uniform(3, 6))

    return updated


# ============================================================
# 7. MAIN
# ============================================================

def main():
    sh = get_gsheet()
    worksheets = sh.worksheets()

    workday_cache = load_workday_cache()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=HEADLESS)
        page = browser.new_page()

        linkedin_logged_in = linkedin_login(page)
        print(f"LinkedIn logged in: {linkedin_logged_in}")

        total_updated = 0
        for ws in worksheets:
            print(f"\n===== Processing sheet: {ws.title} =====")
            updated = process_worksheet(ws, page, workday_cache)
            print(f"Sheet '{ws.title}' → updated {updated} rows.")
            total_updated += updated

        browser.close()

    save_workday_cache(workday_cache)
    print(f"\n🎉 DONE – total rows updated: {total_updated}")


if __name__ == "__main__":
    main()
