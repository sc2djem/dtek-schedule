import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def parse_dtek_exact_html(html_content):
    hours_status = ["yes"] * 24
    if not html_content:
        return hours_status

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Шукаємо активну таблицю з графіком
        active_table = soup.find("div", class_=lambda c: c and "discon-fact-table" in c and "active" in c)
        if not active_table:
            active_table = soup

        # Знаходимо всі клітинки рядка з годинами
        rows = active_table.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            
            # Фільтруємо лише клітинки, які мають класи стану (cell-scheduled, cell-non-scheduled тощо)
            status_cells = [c for c in cells if any(k in " ".join(c.get("class", [])) for k in ["cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"])]
            
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
        print(f"Помилка разбору DOM: {e}")

    return hours_status

def get_schedule(street_name):
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
        'data[2][value]': '1'
    }

    try:
        res = scraper.post(url, headers=headers, data=payload, timeout=12)
        if res.status_code == 200:
            data = res.json()
            html_content = ""
            if isinstance(data, dict):
                html_content = data.get("html", "") or data.get("data", "")
            return parse_dtek_exact_html(html_content)
    except Exception as e:
        print(f"Помилка запиту ({street_name}): {e}")

    return ["yes"] * 24

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = get_schedule("шосе Сквирське")
    hours_22 = get_schedule("вул. Кожедуба Івана")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
