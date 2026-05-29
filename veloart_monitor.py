from playwright.sync_api import sync_playwright
import requests
import os
import time
import re
from datetime import datetime

URL = "https://veloart.cc/rezerwacje/"
CHECK_EVERY_SECONDS = 180

TARGET_DATETIME = datetime.fromisoformat("2026-08-05 09:00")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

last_alert = None


def notify(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    )


def check_veloart():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"]
        )

        page = browser.new_page(
            viewport={"width": 1400, "height": 1200},
            user_agent="Mozilla/5.0"
        )

        page.goto(URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(8000)

        try:
            page.get_by_text("Rozumiem").click(timeout=3000)
        except Exception:
            pass

        page.wait_for_selector(".bookero-plugin-form", timeout=30000)
        page.wait_for_selector(".calendar-nav", timeout=30000)

        # klikamy strzałkę w lewo, żeby przejść do lipca
        page.locator(".calendar-nav button").first.click(timeout=10000)
        page.wait_for_timeout(3000)

        text = page.locator("body").inner_text(timeout=10000)

        match = re.search(
            r"Najbliższy wolny termin to\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})",
            text
        )

        browser.close()

        if not match:
            return None, text

        found = datetime.fromisoformat(match.group(1) + " " + match.group(2))
        return found, text


notify("✅ Veloart monitor uruchomiony. Szukam terminu przed 2026-08-05 09:00.")
print("Start Veloart monitora.", flush=True)

while True:
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Sprawdzam Veloart...", flush=True)

        found_datetime, page_text = check_veloart()

        print("Najbliższy znaleziony termin:", found_datetime, flush=True)

        if found_datetime and found_datetime < TARGET_DATETIME:
            signature = found_datetime.isoformat()

            if signature != last_alert:
                notify(
                    "🚨 Veloart: pojawił się wcześniejszy termin!\n\n"
                    f"Nowy termin: {found_datetime.strftime('%Y-%m-%d %H:%M')}\n"
                    "Poprzedni punkt odniesienia: 2026-08-05 09:00\n\n"
                    "Usługa: Bikefitting Kompleksowy + Serwis Roweru - Warszawa\n"
                    + URL
                )
                last_alert = signature

        print("Sprawdzono Veloart.", flush=True)

    except Exception as e:
        print("Błąd Veloart:", e, flush=True)

    time.sleep(CHECK_EVERY_SECONDS)
