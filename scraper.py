import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def parse_dtek_dom(html_content):
    """
    Чистий парсинг DOM-дерева ДТЕК:
    Шукає всі <td> з класами cell-scheduled, cell-non-scheduled, cell-first-half, cell-second-half
    """
    hours = ["yes"] * 24
    if not html_content:
        return hours

    soup = BeautifulSoup(html_content, "html.parser")

    # Шукаємо всі таблиці або блоки з графіком
    tables = soup.find_all("table")
    
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            
            # Відбираємо саме клітинки зі статусами відключень
            status_cells = [
                c for c in cells 
                if any(cls in " ".join(c.get("class", [])) for cls in [
                    "cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"
                ])
            ]
            
            # Якщо знайшли рядок з 24 годинами
            if len(status_cells) >= 24:
                for i in range(24):
                    classes_str = " ".join(status_cells[i].get("class", []))
                    
                    if "cell-scheduled" in classes_str:
                        hours[i] = "no"
                    elif "cell-first-half" in classes_str:
                        hours[i] = "maybe_first"
                    elif "cell-second-half" in classes_str:
                        hours[i] = "maybe_second"
                    elif "cell-non-scheduled" in classes_str:
                        hours[i] = "yes"
                return hours

    return hours

def fetch_schedule_from_dtek(street_name, house_num="1"):
    scraper = cloudscraper.create_scraper()
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Крок 1: Запит адреси
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
        res = scraper.post(url, headers=headers, data=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            
            # Отримуємо сирий HTML з відповіді ДТЕК
            html_content = ""
            if isinstance(data, dict):
                html_content = data.get("html", "") or data.get("data", "") or str(data)

            # Парсимо DOM-дерево
            parsed_hours = parse_dtek_dom(html_content)
            return parsed_hours

    except Exception as e:
        print(f"Помилка запиту для {street_name}: {e}")

    return ["yes"] * 24

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    # Прямий парсинг DOM для двох адрес у Білій Церкві
    hours_21 = fetch_schedule_from_dtek("шосе Сквирське", "1")
    hours_22 = fetch_schedule_from_dtek("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
