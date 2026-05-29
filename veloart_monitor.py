from playwright.sync_api import sync_playwright
import requests
import os
import time
from datetime import datetime, date

URL = "https://veloart.cc/rezerwacje/"
CHECK_EVERY_SECONDS = 180

TARGET_DATE = date.fromisoformat("2026-08-05")

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

last_alert = None

MONTHS = {
    "styczeń": 1, "stycznia": 1,
    "luty": 2, "lutego": 2,
    "marzec": 3, "marca": 3,
    "kwiecień": 4, "kwietnia": 4,
    "maj": 5, "maja": 5,
    "czerwiec": 6, "czerwca": 6,
    "lipiec": 7, "lipca": 7,
    "sierpień": 8, "sierpnia": 8,
    "wrzesień": 9, "września": 9,
    "październik": 10, "października": 10,
    "listopad": 11, "listopada": 11,
    "grudzień": 12, "grudnia": 12,
}


def notify(text):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text},
        timeout=20,
    )


def parse_month_year(text):
    text = text.lower().strip()
    parts = text.split()

    if len(parts) < 2:
        return None, None

    month_name = parts[0]
    year = int(parts[1])

    month = MONTHS.get(month_name)
    return month, year


def get_visible_available_dates(page):
    month_header = page.locator(".calendar-nav").inner_text(timeout=10000)
    month, year = parse_month_year(month_header)

    if not month or not year:
        return []

    days = page.locator(".calendar-days-list-cell.is-valid").evaluate_all("""
        els => els.map(el => el.innerText.trim()).filter(Boolean)
    """)

    result = []

    for d in days:
        if d.isdigit():
            result.append(date(year, month, int(d)))

    return result


def check_veloart():
    all_dates = []

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

        # cookies
        try:
            page.get_by_text("Rozumiem").click(timeout=3000)
        except Exception:
            pass

        # czekamy aż Bookero / kalendarz się pojawi
        page.wait_for_selector(".bookero-plugin-form", timeout=30000)
        page.wait_for_selector(".calendar-days-list-cell", timeout=30000)

        # zbierz aktualny miesiąc
        all_dates.extend(get_visible_available_dates(page))

        # sprawdź kilka miesięcy wstecz
        for _ in range(8):
            try:
                prev_button = page.locator(".calendar-nav button").first
                prev_button.click(timeout=3000)
                page.wait_for_timeout(2000)
                all_dates.extend(get_visible_available_dates(page))
            except Exception:
                break

        browser.close()

    unique_dates = sorted(set(all_dates))
    earlier_dates = [d for d in unique_dates if d < TARGET_DATE]

    return unique_dates, earlier_dates


notify("✅ Veloart monitor uruchomiony. Szukam terminu przed 2026-08-05.")

print("Start Veloart monitora.", flush=True)

while True:
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Sprawdzam Veloart...", flush=True)

        all_dates, earlier_dates = check_veloart()

        print("Wszystkie znalezione terminy:", [str(d) for d in all_dates], flush=True)
        print("Terminy wcześniejsze niż 2026-08-05:", [str(d) for d in earlier_dates], flush=True)

        if earlier_dates:
            signature = ",".join(str(d) for d in earlier_dates)

            if signature != last_alert:
                notify(
                    "🚨 Veloart: pojawił się wcześniejszy termin!\n\n"
                    "Najwcześniejszy: " + str(earlier_dates[0]) + "\n"
                    "Wszystkie wcześniejsze: " + ", ".join(str(d) for d in earlier_dates) + "\n\n"
                    "Usługa: Bikefitting Kompleksowy + Serwis Roweru - Warszawa\n"
                    + URL
                )

                last_alert = signature

        print("Sprawdzono Veloart.", flush=True)

    except Exception as e:
        print("Błąd Veloart:", e, flush=True)

    time.sleep(CHECK_EVERY_SECONDS)
