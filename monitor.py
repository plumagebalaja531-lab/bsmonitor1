import json
import os
from playwright.sync_api import sync_playwright

URL = os.environ.get("TARGET_URL", "https://daesung.bstage.in/shop/products/59")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_FILE = "state.json"

SOLD_OUT_KEYWORDS = ["sold out", "out of stock", "품절", "일시품절", "매진"]


def send_telegram(message: str) -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("尚未設定 TELEGRAM_BOT_TOKEN 或 TELEGRAM_CHAT_ID，略過推播。")
        return

    import urllib.request
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


def fetch_rendered_text(url: str) -> str:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="en-US")
        page.goto(url, wait_until="networkidle", timeout=30000)
        # 多等 3 秒確保底部 Sold out 按鈕完全渲染出來
        page.wait_for_timeout(3000)
        body_text = page.inner_text("body").lower()
        browser.close()
    return body_text


def detect_stock_status(page_text: str) -> str:
    for kw in SOLD_OUT_KEYWORDS:
        if kw in page_text:
            return "sold_out"
    return "available"


def load_previous_state() -> str:
    if not os.path.exists(STATE_FILE):
        return "unknown"
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("status", "unknown")


def save_current_state(status: str) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"status": status}, f, ensure_ascii=False, indent=2)


def main() -> None:
    prev_status = load_previous_state()
    page_text = fetch_rendered_text(URL)
    curr_status = detect_stock_status(page_text)

    print(f"上次狀態: {prev_status} -> 本次狀態: {curr_status}")

    if prev_status == "sold_out" and curr_status == "available":
        send_telegram(f"🚨 商品補貨／可購買了！快去搶購：\n{URL}")
    elif prev_status == "unknown" and curr_status == "available":
        send_telegram(f"ℹ️ 首次監測：目前頁面顯示狀態為可購買：\n{URL}")

    save_current_state(curr_status)


if __name__ == "__main__":
    main()
