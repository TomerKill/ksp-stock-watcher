#!/usr/bin/env python3
# ksp_watcher.py
# Monitors a retailer search page and sends a Telegram alert once a matching product appears.
# Requires: requests, beautifulsoup4, playwright

import time
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import urljoin, urlparse
import sys
import os

# ====== CONFIG ======
BASE_URL = "https://www.ksp.co.il/"
SEARCH_PATH = "/web/cat/245..573..61633?search=iphone%2017%20pro" # search page or a specific product path
CHECK_KEYWORDS = ["Apple iPhone 17 Pro 256","orange","deep blue","silver"]
INTERVAL_SECONDS = 40   # polite default; never go below MIN_INTERVAL
MIN_INTERVAL = 30

# Telegram
TELEGRAM_TOKEN = os.environ.get("KSP_TELEGRAM_TOKEN", "<PASTE_TOKEN_HERE>")
TELEGRAM_CHAT_ID = os.environ.get("KSP_TELEGRAM_CHAT_ID", "<PASTE_CHAT_ID_HERE>")

HEADERS = {
    "User-Agent": "StockWatcherBot/1.0 (+https://yourdomain.example) - respectful checker"
}
session = requests.Session()
session.headers.update(HEADERS)

def check_with_playwright(url, keywords):
    kw_low = [k.lower() for k in keywords]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="he-IL",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900}
        )
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # Wait for the network to go idle
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except:
            pass

        # Wait for product cards to render (adjust selector if the site changes)
        product_selector = 'a[href^="/web/item/"], div.product, a[data-product-id]'
        try:
            page.wait_for_selector(product_selector, timeout=15000)
        except:
            print("[WARN] No product selector found within 15s - there may be no results or the page is slow.")

        # Scroll through the page to trigger lazy-loaded content
        try:
            page.evaluate("""
                () => new Promise(resolve => {
                    let total = 0;
                    const step = () => {
                        window.scrollBy(0, 1200);
                        total += 1200;
                        if (total < document.body.scrollHeight * 1.2) {
                            setTimeout(step, 200);
                        } else {
                            resolve();
                        }
                    };
                    step();
                })
            """)
            page.wait_for_load_state("networkidle", timeout=5000)
        except:
            pass

        html = page.content().lower()
        ctx.close()
        browser.close()

        if '/web/item/' in html and not any(k in html for k in kw_low):
            print("[INFO] Product cards found, but no keyword matched.")

        return (True, 200) if any(k in html for k in kw_low) else (False, 200)


def allowed_by_robots(base_url, path="/"):
    try:
        robots_url = urljoin(base_url, "/robots.txt")
        r = session.get(robots_url, timeout=10)
        if r.status_code != 200:
            return True
        txt = r.text
        lines = [l.strip() for l in txt.splitlines() if l.strip() and not l.strip().startswith("#")]
        user = None
        disallows = []
        for line in lines:
            if line.lower().startswith("user-agent:"):
                user = line.split(":", 1)[1].strip()
            elif line.lower().startswith("disallow:") and (user == "*" or user is None):
                val = line.split(":", 1)[1].strip()
                disallows.append(val)
        for d in disallows:
            if d == "/":
                return False
            if path.startswith(d):
                return False
        return True
    except Exception:
        return True

def telegram_notify(text):
    if not TELEGRAM_TOKEN or "<PASTE" in TELEGRAM_TOKEN:
        print("[WARN] Telegram token not configured, can't send msg.")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=15)
        return r.status_code == 200
    except Exception as e:
        print("Telegram send failed:", e)
        return False

def check_page_for_keywords(full_url, keywords):
    try:
        r = session.get(full_url, timeout=20)
        if r.status_code == 429:
            print("Got 429 Too Many Requests — backing off.")
            return None, 429
        if r.status_code >= 400:
            print(f"HTTP error {r.status_code}")
            return None, r.status_code
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text(separator="\n")
        for kw in keywords:
            if kw.lower() in text.lower():
                return True, r.status_code
        return False, r.status_code
    except requests.RequestException as e:
        print("Request failed:", e)
        return None, None

def main(once=False):
    if INTERVAL_SECONDS < MIN_INTERVAL:
        print(f"Interval {INTERVAL_SECONDS}s below safe minimum ({MIN_INTERVAL}s). Exiting.")
        sys.exit(1)

    parsed = urlparse(BASE_URL)
    if not parsed.scheme:
        print("BASE_URL must include scheme (https://).")
        sys.exit(1)

    if not allowed_by_robots(BASE_URL, SEARCH_PATH):
        print("robots.txt disallows scraping. Exiting.")
        sys.exit(1)

    full_url = urljoin(BASE_URL, SEARCH_PATH)
    print("Starting watcher for:", full_url)
    backoff = 1
    while True:
        found, status = check_with_playwright(full_url, CHECK_KEYWORDS)
        if found is True:
            msg = f"Product matching {CHECK_KEYWORDS} found at {full_url}\nHTTP {status}"
            print(msg)
            telegram_notify(msg)
            break
        elif found is False:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Not found yet (HTTP {status})")
            backoff = 1
        else:
            print("Fetch problem - backing off for", backoff, "seconds")
            time.sleep(backoff)
            backoff = min(backoff * 2, 300)
            continue

        if once:
            break
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true", help="Save a raw HTML snapshot of the page (requests) for debugging")
    parser.add_argument("--once", action="store_true", help="Run a single check and exit (for testing)")
    args = parser.parse_args()

    if args.debug:
        full_url = urljoin(BASE_URL, SEARCH_PATH)
        print("DEBUG fetching (requests):", full_url)
        r = session.get(full_url, timeout=20)
        print("HTTP:", r.status_code, "len:", len(r.text))
        with open("debug_ksp.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        low = r.text.lower()
        print("contains 'iphone'?", "iphone" in low)
        print("Saved to debug_ksp.html")
        sys.exit(0)

    main(once=args.once)
