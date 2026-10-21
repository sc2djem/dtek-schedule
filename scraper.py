import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def parse_dtek_html(html_content):
    # Початковий масив на 24 години: 'yes', 'no', 'maybe_first', 'maybe_second'
    hours_status = ["yes"] * 24
    if not html_content:
        return hours_status

    soup = BeautifulSoup(html_content, "html.parser")
    
    # Шукаємо всі елементи/клітинки, що відповідають годинам
    # ДТЕК використовує атрибути data-hour (0..23) або класи в таблицях
    cells = soup.find_all(attrs={"data-hour": True})
    
    if cells:
        for cell in cells:
            try:
                h = int(cell["data-hour"])
                if 0 <= h < 24:
                    classes = cell.get("class", [])
                    class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                    
                    if "no" in class_str or "off" in class_str:
                        hours_status[h] = "no"
                    elif "maybe-first" in class_str or "first" in class_str:
                        hours_status[h] = "maybe_first"
                    elif "maybe-second" in class_str or "second" in class_str:
                        hours_status[h] = "maybe_second"
                    elif "maybe" in class_str:
                        hours_status[h] = "maybe_first"
            except (ValueError, KeyError):
                pass
    else:
        # Якщо data-hour відсутній, шукаємо по тегах td/div з відповідними класами
        all_cells = soup.find_all(["td", "div"], class_=True)
        hour_counter = 0
        for cell in all_cells:
            classes = cell.get("class", [])
            class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
            if any(k in class_str for k in ["cell", "hour", "schedule-cell"]):
                if hour_counter < 24:
                    if "no" in class_str:
                        hours_status[hour_counter] = "no"
                    elif "maybe" in class_str:
                        hours_status[hour_counter] = "maybe_first"
                    hour_counter += 1

    return hours_status

def get_hours_for_address(street_name, house_num="1"):
    try:
        scraper = cloudscraper.create_scraper()
        url = "https://www.dtek-krem.com.ua/ua/ajax"
        
        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
            return parse_dtek_html(html_content)
    except Exception as e:
        print(f"Error fetching {street_name}: {e}")

    return ["yes"] * 24

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_hours_for_address("шосе Сквирське", "1")
    hours_22 = get_hours_for_address("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
