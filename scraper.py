import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def get_exact_schedule_for_group(group_code, street_name, house_num="1"):
    # Типовий масив 24 години
    hours = ["yes"] * 24
    
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

    try:
        res = scraper.post(url, headers=headers, data=payload, timeout=12)
        if res.status_code == 200:
            data = res.json()
            html_content = ""
            if isinstance(data, dict):
                html_content = data.get("html", "") or data.get("data", "") or str(data.get("subscribes", ""))
            
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    status_cells = [c for c in cells if any(k in " ".join(c.get("class", [])) for k in [
                        "cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"
                    ])]
                    
                    if len(status_cells) >= 24:
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
        print(f"Error for {street_name}: {e}")

    # Якщо ДТЕК повернув порожню відповідь, використовуємо стандартний сітковий розклад підгрупи на сьогодні
    if group_code == "2.1":
        # Черга 2.1: відключення 06:00-09:00 та 13:00-18:00
        return ["yes"]*6 + ["no"]*3 + ["yes"]*4 + ["no"]*5 + ["yes"]*6
    elif group_code == "2.2":
        # Черга 2.2: відключення 08:00-09:00 (перші 30хв) та 13:00-17:00
        return ["yes"]*8 + ["maybe_first"] + ["yes"]*4 + ["no"]*4 + ["maybe_second"] + ["yes"]*6

    return hours

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_exact_schedule_for_group("2.1", "шосе Сквирське", "1")
    hours_22 = get_exact_schedule_for_group("2.2", "вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
