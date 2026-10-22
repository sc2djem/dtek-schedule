import os
import json
import datetime
import requests
import cloudscraper
from bs4 import BeautifulSoup

def send_telegram_notification(message):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Помилка Telegram: {e}")

def parse_html_table(html_str):
    if not html_str:
        return None

    try:
        soup = BeautifulSoup(html_str, "html.parser")
        tables = soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                status_cells = [
                    c for c in cells 
                    if any(k in " ".join(c.get("class", [])) for k in [
                        "cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"
                    ])
                ]
                
                if len(status_cells) >= 24:
                    hours = ["yes"] * 24
                    for i in range(24):
                        cls = " ".join(status_cells[i].get("class", []))
                        if "cell-scheduled" in cls:
                            hours[i] = "no"
                        elif "cell-first-half" in cls:
                            hours[i] = "maybe_first"
                        elif "cell-second-half" in cls:
                            hours[i] = "maybe_second"
                        elif "cell-non-scheduled" in cls:
                            hours[i] = "yes"
                    return hours
    except Exception as e:
        print(f"Помилка парсингу: {e}")

    return None

def fetch_dtek(scraper, street_name, house_num):
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
        'Referer': 'https://www.dtek-krem.com.ua/ua/shutdowns',
        'Origin': 'https://www.dtek-krem.com.ua'
    }

    payload = {
        'method': 'getHomeNum',
        'data[0][name]': 'city',
        'data[0][value]': 'м. Біла Церква',
        'data[1][name]': 'street',
        'data[1][value]': street_name,
        'data[2][name]': 'house',
        'data[2][value]': house_num
    }

    try:
        res = scraper.post(url, headers=headers, data=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            html_content = ""
            if isinstance(data, dict):
                html_content = data.get("html", "") or data.get("data", "") or str(data)
            
            parsed = parse_html_table(html_content)
            if parsed:
                return parsed
    except Exception as e:
        print(f"Помилка запиту ({street_name} {house_num}): {e}")

    return None

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    # Створюємо єдину сесію зі збереженням кук
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    # 1. Завантажуємо головну сторінку для отримання захисних кук Cloudflare
    try:
        scraper.get("https://www.dtek-krem.com.ua/ua/shutdowns", timeout=15)
    except Exception as e:
        print(f"Помилка ініціалізації кук: {e}")

    # 2. Виконуємо безпосередній парсинг
    hours_21 = fetch_dtek(scraper, "шосе Сквирське", "1")
    hours_22 = fetch_dtek(scraper, "вул. Кожедуба Івана", "135А")

    # Якщо парсинг повернув None (блокування), зберігаємо значення за замовчуванням
    if not hours_21:
        hours_21 = ["yes"] * 24
    if not hours_22:
        hours_22 = ["yes"] * 24

    new_result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    old_data = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    changes = []
    if old_data.get("2.1") and old_data["2.1"] != hours_21 and hours_21 != ["yes"] * 24:
        changes.append("<b>Група 2.1 (шосе Сквирське)</b>: графік змінився!")
    if old_data.get("2.2") and old_data["2.2"] != hours_22 and hours_22 != ["yes"] * 24:
        changes.append("<b>Група 2.2 (вул. Кожедуба Івана)</b>: графік змінився!")

    if changes:
        msg = f"⚡ <b>Оновлення графіку ДТЕК (м. Біла Церква)</b>\n<i>Час: {now.strftime('%d.%m.%Y %H:%M')}</i>\n\n"
        msg += "\n".join(changes)
        msg += "\n\n🔗 <a href='https://sc2djem.github.io/dtek-schedule/'>Переглянути новий графік</a>"
        send_telegram_notification(msg)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(new_result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
