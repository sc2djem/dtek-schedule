import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def get_dtek_exact_table(street_name, house_num="1"):
    hours_status = ["yes"] * 24
    scraper = cloudscraper.create_scraper()
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    try:
        # Крок 1: Отримуємо ID будинку
        payload_home = {
            'method': 'getHomeNum',
            'data[0][name]': 'city',
            'data[0][value]': 'м. Біла Церква',
            'data[1][name]': 'street',
            'data[1][value]': street_name,
            'data[2][name]': 'house',
            'data[2][value]': house_num
        }

        res_home = scraper.post(url, headers=headers, data=payload_home, timeout=12)
        if res_home.status_code != 200:
            return hours_status

        home_data = res_home.json()
        house_id = None

        # Витягуємо ID будинку з відповіді
        if isinstance(home_data, dict):
            if "data" in home_data and isinstance(home_data["data"], list) and len(home_data["data"]) > 0:
                house_id = home_data["data"][0].get("id")
            elif "subscribes" in home_data and isinstance(home_data["subscribes"], list) and len(home_data["subscribes"]) > 0:
                house_id = home_data["subscribes"][0].get("house_id")

        # Якщо ID знайшли — робимо прямий запит графіку
        html_content = ""
        if house_id:
            res_sched = scraper.post(url, headers=headers, data={
                'method': 'getSchedule',
                'house_id': house_id
            }, timeout=12)
            if res_sched.status_code == 200:
                sched_json = res_sched.json()
                html_content = sched_json.get("html", "") or sched_json.get("data", "")
        else:
            # Якщо ДТЕК віддав HTML одразу в першій відповіді
            html_content = home_data.get("html", "") or home_data.get("data", "")

        # Крок 2: Парсимо отриману таблицю з DOM-класів на скріншоті
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")
            rows = soup.find_all("tr")
            
            for row in rows:
                cells = row.find_all("td")
                # Шукаємо саме ті класи, які видно на скріншоті
                status_cells = [c for c in cells if any(k in " ".join(c.get("class", [])) for k in [
                    "cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"
                ])]
                
                if len(status_cells) >= 24:
                    for i in range(24):
                        cls = " ".join(status_cells[i].get("class", []))
                        if "cell-scheduled" in cls:
                            hours_status[i] = "no"
                        elif "cell-first-half" in cls:
                            hours_status[i] = "maybe_first"
                        elif "cell-second-half" in cls:
                            hours_status[i] = "maybe_second"
                        elif "cell-non-scheduled" in cls:
                            hours_status[i] = "yes"
                    return hours_status

    except Exception as e:
        print(f"Помилка завантаження {street_name}: {e}")

    return hours_status

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_dtek_exact_table("шосе Сквирське", "1")
    hours_22 = get_dtek_exact_table("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
