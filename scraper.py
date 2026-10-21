import json
import datetime
import cloudscraper
from bs4 import BeautifulSoup

# Резервные шаблоны графиков для Белой Церкви на случай блокировки запросов облаком
DEFAULT_SCHEDULE_21 = ["yes"]*6 + ["no"]*3 + ["yes"]*4 + ["no"]*5 + ["yes"]*6
DEFAULT_SCHEDULE_22 = ["yes"]*8 + ["maybe_first"] + ["yes"]*4 + ["no"]*4 + ["maybe_second"] + ["yes"]*6

def parse_html_table(html_str):
    if not html_str:
        return None

    try:
        soup = BeautifulSoup(html_str, "html.parser")
        tables = soup.find_all("table")
        
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                status_cells = [
                    c for c in cells 
                    if any(k in " ".join(c.get("class", [])) for k in [
                        "cell-scheduled", "cell-non-scheduled", "cell-first-half", "cell-second-half"
                    ])
                ]
                
                if len(status_cells) >= 24:
                    hours = ["yes"] * 24
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
        print(f"Ошибка парсинга HTML: {e}")

    return None

def fetch_dtek(street_name, house_num="1", default_fallback=None):
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )
    url = "https://www.dtek-krem.com.ua/ua/ajax"
    
    headers = {
        'X-Requested-With': 'XMLHttpRequest',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.dtek-krem.com.ua/ua/shutdowns'
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
        print(f"Ответ ДТЭК для {street_name}: Статус {res.status_code}")
        
        if res.status_code == 200:
            data = res.json()
            html_content = ""
            if isinstance(data, dict):
                html_content = data.get("html", "") or data.get("data", "") or str(data)
            
            parsed = parse_html_table(html_content)
            if parsed:
                print(f"Успешно распарсен график для {street_name}")
                return parsed
            else:
                print(f"Теги ячеек не найдены в ответе для {street_name}")
    except Exception as e:
        print(f"Ошибка сети/запроса ({street_name}): {e}")

    print(f"Используется резервный шаблон для {street_name}")
    return default_fallback if default_fallback else ["yes"] * 24

def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    
    hours_21 = fetch_dtek("шосе Сквирське", "1", DEFAULT_SCHEDULE_21)
    hours_22 = fetch_dtek("вул. Кожедуба Івана", "1", DEFAULT_SCHEDULE_22)

    result = {
        "updated_at": now.strftime("%d.%m.%Y %H:%M"),
        "2.1": hours_21,
        "2.2": hours_22
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
