import json
import os
import urllib.request
from playwright.sync_api import sync_playwright

URLS = [
    "https://daesung.bstage.in/shop/products/59",
    "https://daesung.bstage.in/shop/products/60",
    "https://daesung.bstage.in/shop/products/61",
    "https://daesung.bstage.in/shop/products/62",
    "https://daesung.bstage.in/shop/products/63",
    "https://daesung.bstage.in/shop/products/64",
]

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_FILE = "state.json"

SOLD_OUT_KEYWORDS = ["sold out", "out of stock", "품절", "일시품절", "매진"]


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("尚未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，略過推播。")
        return

    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        print("Telegram 推播狀態碼:", resp.status)


def fetch_rendered_text(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=20000)
    try:
        page.wait_for_load_state("networkidle", timeout=6000)
    except Exception:
        pass
    # 縮短為 1.2 秒，加快 6 件商品巡邏速度
    page.wait_for_timeout(1200)
    return page.inner_text("body").lower()


def detect_stock_status(page_text: str) -> str:
    for kw in SOLD_OUT_KEYWORDS:
        if kw in page_text:
            return "sold_out"
    return "available"


def load_states() -> dict:
    if not os.path.exists(STATE_FILE):
        return {}
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "items" in data and isinstance(data["items"], dict):
        return data["items"]
    return {}


def save_states(items_state: dict) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"items": items_state}, f, ensure_ascii=False, indent=2)


def main() -> None:
    prev_items = load_states()
    curr_items = dict(prev_items)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(locale="en-US")
        page = context.new_page()

        for url in URLS:
            prev_status = prev_items.get(url, "unknown")
            try:
                page_text = fetch_rendered_text(page, url)
                curr_status = detect_stock_status(page_text)
            except Exception as e:
                print(f"[{url}] 讀取失敗，保留前次狀態 ({prev_status})。原因: {e}")
                curr_items[url] = prev_status
                continue

            print(f"[{url}] 上次: {prev_status} -> 本次: {curr_status}")
            curr_items[url] = curr_status

            if prev_status == "sold_out" and curr_status == "available":
                send_telegram(f"🚨 商品補貨／可購買了！快去看看：\n{url}")
            elif prev_status == "unknown" and curr_status == "available":
                send_telegram(f"ℹ️ 首次監測顯示可購買：\n{url}")

        browser.close()

    save_states(curr_items)


if __name__ == "__main__":
    main()
