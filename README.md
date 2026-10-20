# KSP Stock Watcher 📱🔔

A Python bot that monitors a retailer's product search page and sends an **instant Telegram alert** the moment a matching product goes on sale.

I built it to catch the iPhone 17 Pro launch on [KSP](https://www.ksp.co.il), one of Israel's largest electronics retailers, and it let me order one among the very first buyers.

## How it works

1. **Renders the page in a headless browser** (Playwright + Chromium), since the product listing is loaded dynamically with JavaScript.
2. **Scrolls the page** to trigger lazy-loaded product cards.
3. **Searches the rendered HTML** for configurable keywords (model, storage, colors).
4. **Sends a Telegram message** through the Telegram Bot API as soon as there's a match, then stops.

### Polite by design
- Checks `robots.txt` before starting and exits if scraping is disallowed.
- Enforces a minimum polling interval (30s) between checks.
- Uses exponential backoff (up to 5 minutes) when a request fails.

## Tech stack
- **Python 3**
- **Playwright** for rendering JavaScript-heavy pages
- **Requests + BeautifulSoup** for the lightweight fetch / debug mode
- **Telegram Bot API** for notifications

## Setup

```bash
pip install -r requirements.txt
playwright install chromium
```

Create a Telegram bot with [@BotFather](https://t.me/BotFather) and set your credentials as environment variables (they are never stored in the code):

```bash
# Windows (PowerShell)
$env:KSP_TELEGRAM_TOKEN="your-bot-token"
$env:KSP_TELEGRAM_CHAT_ID="your-chat-id"

# macOS / Linux
export KSP_TELEGRAM_TOKEN="your-bot-token"
export KSP_TELEGRAM_CHAT_ID="your-chat-id"
```

## Usage

```bash
python ksp_watcher.py          # watch until the product appears
python ksp_watcher.py --once   # run a single check (testing)
python ksp_watcher.py --debug  # save a raw HTML snapshot to debug_ksp.html
```

Edit `SEARCH_PATH` and `CHECK_KEYWORDS` at the top of `ksp_watcher.py` to watch for a different product.
