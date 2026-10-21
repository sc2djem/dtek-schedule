import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def get_hours_status_for_address(street_name, house_num="1"):
    # Типовий масив з 24 годин: 'yes' (є світло), 'no' (немає), 'maybe_first', 'maybe_second'
    hours_data = ["yes"] * 24
    
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
            
            if html_content:
                soup = BeautifulSoup(html_content, "html.parser")
                
                # Знаходимо всі клітинки таблиці годин
                # ДТЕК використовує атрибути data-hour або класи no/yes/maybe
                rows = soup.find_all("tr")
                for row in rows:
                    cells = row.find_all(["td", "th"])
                    for cell in cells:
                        hour_attr = cell.get("data-hour")
                        if hour_attr is not None:
                            try:
                                h = int(hour_attr)
                                classes = cell.get("class", [])
                                class_str = " ".join(classes) if isinstance(classes, list) else str(classes)
                                
                                if "no" in class_str or "off" in class_str:
                                    hours_data[h] = "no"
                                elif "maybe" in class_str or "first" in class_str:
                                    hours_data[h] = "maybe_first"
                                elif "second" in class_str:
                                    hours_data[h] = "maybe_second"
                                else:
                                    hours_data[h] = "yes"
                            except ValueError:
                                pass
    except Exception as e:
        print(f"Помилка при зборі {street_name}: {e}")

    return hours_data

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_hours_status_for_address("шосе Сквирське", "1")
    hours_22 = get_hours_status_for_address("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
