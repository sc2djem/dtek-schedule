import json
import datetime
import cloudscraper

def fetch_data():
    scraper = cloudscraper.create_scraper()
    
    # URL та дані запиту (потрібно підставити ваші street/house ID з DevTools сайту ДТЕК за потреби)
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    # Поточний час за Києвом (UTC+2 / UTC+3 влітку)
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = now_utc.astimezone(kyiv_tz)
    
    result = {
        "updated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "2.1": "Світло є (за розкладом)",
        "2.2": "Світло є (за розкладом)"
    }

    try:
        # Тут здійснюється запит до ДТЕК
        # response = scraper.post(url, headers=headers, data={...})
        # Приклад парсингу відповіді та заповнення статусу
        pass
    except Exception as e:
        print(f"Помилка при запиті: {e}")

    # Збереження результату в файл data.json
    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fetch_data()
