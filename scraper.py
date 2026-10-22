import os
import re
import json
import datetime
import cloudscraper

PAGE_URL = "https://www.dtek-krem.com.ua/ua/shutdowns"

# Група на сайті ДТЕК називається GPV2.1 / GPV2.2
GROUPS = ["2.1", "2.2"]

# Значення ДТЕК -> значення, які розуміє index.html
STATUS_MAP = {
    "yes": "yes",
    "no": "no",
    "first": "maybe_first",    # світла немає перші 30 хв
    "second": "maybe_second",  # світла немає другі 30 хв
    "mfirst": "maybe_first",
    "msecond": "maybe_second",
    "maybe": "yes",            # "можливе відключення" показуємо як "світло є"
}


def extract_json_after(html, marker):
    """Знаходить 'marker = {...}' у HTML і повертає розібраний JSON."""
    pos = html.find(marker)
    if pos == -1:
        return None
    start = html.find("{", pos)
    if start == -1:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[start:])
        return obj
    except Exception as e:
        print(f"Не вдалося розібрати JSON після '{marker}': {e}")
        return None


def hours_for_group(fact, group):
    """Повертає список із 24 значень для групи на сьогодні або None."""
    data = fact.get("data") or {}
    if not data:
        print("fact.data порожній")
        return None

    today_key = str(fact.get("today", ""))
    if today_key not in data:
        # якщо ключа 'today' немає, беремо найновіший день
        today_key = max(data.keys(), key=lambda k: int(k))
    day = data[today_key]

    group_key = f"GPV{group}"
    if group_key not in day:
        print(f"Групи {group_key} немає у відповіді. Є: {list(day.keys())}")
        return None

    raw = day[group_key]
    hours = []
    for i in range(1, 25):
        value = raw.get(str(i), "yes")
        if value not in STATUS_MAP:
            print(f"Невідоме значення '{value}' о годині {i}")
        hours.append(STATUS_MAP.get(value, "yes"))
    return hours


def fetch_schedule():
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "desktop": True}
    )
    res = scraper.get(PAGE_URL, timeout=30)
    html = res.text
    print(f"HTTP {res.status_code}, розмір відповіді {len(html)} байт")

    if "Just a moment" in html or "cf-chl" in html:
        raise RuntimeError("Cloudflare блокує запит (сторінка-перевірка)")
    if res.status_code != 200:
        raise RuntimeError(f"Сайт ДТЕК відповів кодом {res.status_code}")

    fact = extract_json_after(html, "DisconSchedule.fact")
    if not fact:
        print("Початок відповіді:", html[:300].replace("\n", " "))
        raise RuntimeError("На сторінці не знайдено DisconSchedule.fact")

    result = {}
    for group in GROUPS:
        hours = hours_for_group(fact, group)
        if not hours:
            raise RuntimeError(f"Немає даних для групи {group}")
        result[group] = hours
    return result


def main():
    kyiv_tz = datetime.timezone(datetime.timedelta(hours=3))
    now = datetime.datetime.now(datetime.timezone.utc).astimezone(kyiv_tz)
    now_str = now.strftime("%d.%m.%Y %H:%M")

    old_data = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    try:
        schedule = fetch_schedule()
        new_data = {
            "status": "ok",
            "updated_at": now_str,
            "2.1": schedule["2.1"],
            "2.2": schedule["2.2"],
        }
        print("OK: графік оновлено")
    except Exception as e:
        print(f"ПОМИЛКА: {e}")
        # Лишаємо останній успішний графік, але позначаємо помилку
        new_data = {
            "status": "error",
            "error": str(e),
            "checked_at": now_str,
            "updated_at": old_data.get("updated_at", "невідомо"),
            "2.1": old_data.get("2.1"),
            "2.2": old_data.get("2.2"),
        }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
