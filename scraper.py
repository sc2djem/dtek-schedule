import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def get_dtek_schedule_for_street(street_name, house_num="1"):
    # Типовий масив на 24 години: 'yes', 'no', 'maybe_first', 'maybe_second'
    hours_status = ["yes"] * 24
    
    scraper = cloudscraper.create_scraper()
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    try:
        # 1. Отримуємо ID будинку
        payload_house = {
            'method': 'getHomeNum',
            'data[0][name]': 'city',
            'data[0][value]': 'м. Біла Церква',
            'data[1][name]': 'street',
            'data[1][value]': street_name,
            'data[2][name]': 'house',
            'data[2][value]': house_num
        }

        res = scraper.post(url, headers=headers, data=payload_house, timeout=15)
        if res.status_code != 200:
            return hours_status

        data = res.json()
        html_content = ""

        # Перевіряємо, де ДТЕК повернув результат
        if isinstance(data, dict):
            html_content = data.get("html", "") or data.get("data", "")
            
            # Якщо у відповіді прийшов список будинків із їх ідентифікаторами (house_id)
            if not html_content and "subscribes" in data:
                html_content = str(data["subscribes"])
            elif not html_content and isinstance(data.get("data"), list) and len(data["data"]) > 0:
                first_item = data["data"][0]
                if isinstance(first_item, dict) and "id" in first_item:
                    house_id = first_item["id"]
                    # Викликаємо безпосередньо розклад за house_id
                    res_sched = scraper.post(url, headers=headers, data={
                        'method': 'getSchedule',
                        'house_id': house_id
                    }, timeout=15)
                    if res_sched.status_code == 200:
                        sched_data = res_sched.json()
                        html_content = sched_data.get("html", "") or sched_data.get("data", "")

        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            
            # Парсимо клітинки графіку за атрибутами або CSS-класами ДТЕК
            cells = soup.find_all(attrs={"data-hour": True})
            if cells:
                for cell in cells:
                    try:
                        h = int(cell["data-hour"])
                        if 0 <= h < 24:
                            classes = cell.get("class", [])
                            cls = " ".join(classes) if isinstance(classes, list) else str(classes)
                            
                            if "no" in cls or "off" in cls:
                                hours_status[h] = "no"
                            elif "maybe" in cls or "first" in cls:
                                hours_status[h] = "maybe_first"
                            elif "second" in cls:
                                hours_status[h] = "maybe_second"
                    except (ValueError, KeyError):
                        pass
            else:
                # Резервний аналіз за CSS-класами осередків таблиці
                table_cells = soup.find_all(["td", "div"], class_=True)
                valid_cells = [c for c in table_cells if any(k in " ".join(c.get("class", [])) for k in ["cell", "hour", "schedule"])]
                for i, cell in enumerate(valid_cells[:24]):
                    cls = " ".join(cell.get("class", []))
                    if "no" in cls:
                        hours_status[i] = "no"
                    elif "maybe" in cls:
                        hours_status[i] = "maybe_first"

    except Exception as e:
        print(f"Помилка збору для {street_name}: {e}")

    return hours_status

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_dtek_schedule_for_street("шосе Сквирське", "1")
    hours_22 = get_dtek_schedule_for_street("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
