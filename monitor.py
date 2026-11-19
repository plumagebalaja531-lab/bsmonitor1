import json
import os
import re
import urllib.request

URL = os.environ.get("TARGET_URL", "https://daesung.bstage.in/shop/products/59")
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
STATE_FILE = "state.json"

# 常見缺貨字眼（可依實際頁面看到的文字增減）
SOLD_OUT_KEYWORDS = "Sold out"


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


def fetch_page_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7,zh-TW;q=0.6",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    # 移除 script 與 style 標籤後擷取可見文字，降低誤判機率
    html_no_script = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text_only = re.sub(r"<[^>]+>", " ", html_no_script)
    text_clean = re.sub(r"\s+", " ", text_only).strip().lower()
    return text_clean


def detect_stock_status(clean_text: str) -> str:
    # 若頁面出現明顯缺貨字眼，視為缺貨（sold_out）
    for kw in SOLD_OUT_KEYWORDS:
        if kw in clean_text:
            return "sold_out"
    # 否則視為可能可購買（available）
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
    clean_text = fetch_page_text(URL)
    curr_status = detect_stock_status(clean_text)

    print(f"上次狀態: {prev_status} -> 本次狀態: {curr_status}")

    # 只有「原本缺貨」變成「有貨」時才發通知，避免第一次或重複通知轟炸
    if prev_status == "sold_out" and curr_status == "available":
        send_telegram(f"🚨 商品可能補貨／可購買了！快去看看：\n{URL}")
    elif prev_status == "unknown" and curr_status == "available":
        send_telegram(f"ℹ️ 首次監測：目前頁面顯示狀態為可購買（available）：\n{URL}")

    save_current_state(curr_status)


if __name__ == "__main__":
    main()
