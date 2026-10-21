import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def get_schedule_for_address(street_name, house_num="1"):
    try:
        scraper = cloudscraper.create_scraper()
        url = "https://www.dtek-krem.com.ua/ua/ajax"
        
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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

        response = scraper.post(url, headers=headers, data=payload, timeout=15)
        if response.status_code == 200:
            data = response.json()
            html_content = data.get("html", "") or data.get("data", "")
            
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                text = soup.get_text()
                if "Світла немає" in text:
                    return "Відключення за графіком"
                return "Світло є (за розкладом)"
            return "Дані отримано"
        return f"Помилка ДТЕК ({response.status_code})"
    except Exception as e:
        return f"Тимчасова помилка: {str(e)}"

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    status_21 = get_schedule_for_address("шосе Сквирське", "1")
    status_22 = get_schedule_for_address("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": status_21,
        "2.2": status_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
