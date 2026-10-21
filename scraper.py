import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

def parse_html_table(html_str):
    # За замовчуванням 24 години "yes"
    hours = ["yes"] * 24
    if not html_str:
        return hours

    soup = BeautifulSoup(html_str, "html.parser")

    # 1. Пошук за точними класи ДТЕК з вашого скріншота DevTools
    rows = soup.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        status_cells = [c for c in cells if any(k in " ".join(c.get("class", [])) for k in ["cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"])]
        
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

    # 2. Альтернативний пошук за атрибутом data-hour
    data_cells = soup.find_all(attrs={"data-hour": True})
    if data_cells:
        for cell in data_cells:
            try:
                h = int(cell["data-hour"])
                if 0 <= h < 24:
                    cls = " ".join(cell.get("class", []))
                    if "no" in cls or "off" in cls or "scheduled" in cls:
                        hours[h] = "no"
                    elif "first" in cls:
                        hours[h] = "maybe_first"
                    elif "second" in cls:
                        hours[h] = "maybe_second"
            except (ValueError, KeyError):
                pass
        return hours

    return hours

def get_dtek_schedule(street_name, house_num="1"):
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
        res = scraper.post(url, headers=headers, data=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            html_content = ""
            
            if isinstance(data, dict):
                # Збираємо весь HTML, який прийшов від ДТЕК
                html_content = data.get("html", "") or data.get("data", "") or str(data.get("subscribes", ""))
                
            return parse_html_table(html_content)
    except Exception as e:
        print(f"Помилка запиту ({street_name}): {e}")

    return ["yes"] * 24

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    # Викликаємо парсинг для обох вулиць у м. Біла Церква
    hours_21 = get_dtek_schedule("шосе Сквирське", "1")
    hours_22 = get_dtek_schedule("вул. Кожедуба Івана", "1")

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
