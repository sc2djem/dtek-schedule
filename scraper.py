import os
import json
import datetime
from zoneinfo import ZoneInfo
import cloudscraper

PAGE_URL = "https://www.dtek-krem.com.ua/ua/shutdowns"

# Група на сайті ДТЕК називається GPV2.1 / GPV2.2
GROUPS = ["2.1", "2.2"]

# Київський час із автоматичним переходом літній/зимовий
KYIV = ZoneInfo("Europe/Kyiv")

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


def fmt_date(ts):
    return datetime.datetime.fromtimestamp(int(ts), KYIV).strftime("%d.%m.%Y")


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


def hours_for_group(day, group):
    """Повертає список із 24 значень для групи за один день або None."""
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


def hours_for_all_groups(day):
    result = {}
    for group in GROUPS:
        hours = hours_for_group(day, group)
        if not hours:
            return None
        result[group] = hours
    return result


def fetch_schedule(now):
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

    data = fact.get("data") or {}
    if not data:
        raise RuntimeError("fact.data порожній")

    # Дата -> ключ дня у відповіді ДТЕК
    by_date = {fmt_date(k): k for k in data.keys()}
    print("Дні у відповіді ДТЕК:", sorted(by_date.keys()))

    today_str = now.strftime("%d.%m.%Y")
    tomorrow_str = (now + datetime.timedelta(days=1)).strftime("%d.%m.%Y")

    today_key = by_date.get(today_str)
    if today_key is None and fact.get("today") is not None:
        today_key = str(fact["today"])
        today_str = fmt_date(today_key)
    if today_key is None or today_key not in data:
        raise RuntimeError(f"У відповіді немає графіка на сьогодні ({today_str})")

    today = hours_for_all_groups(data[today_key])
    if not today:
        raise RuntimeError("Немає даних на сьогодні для однієї з груп")

    tomorrow = None
    tomorrow_key = by_date.get(tomorrow_str)
    if tomorrow_key is not None:
        tomorrow_hours = hours_for_all_groups(data[tomorrow_key])
        if tomorrow_hours:
            tomorrow = {"date": tomorrow_str, **tomorrow_hours}
            print(f"Графік на завтра ({tomorrow_str}) знайдено")
    if tomorrow is None:
        print(f"Графіка на завтра ({tomorrow_str}) ще немає")

    return today_str, today, tomorrow


def main():
    now = datetime.datetime.now(KYIV)
    now_str = now.strftime("%d.%m.%Y %H:%M")

    old_data = {}
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    try:
        today_str, today, tomorrow = fetch_schedule(now)
        new_data = {
            "status": "ok",
            "updated_at": now_str,
            "today_date": today_str,
            "2.1": today["2.1"],
            "2.2": today["2.2"],
            "tomorrow": tomorrow,
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
            "today_date": old_data.get("today_date"),
            "2.1": old_data.get("2.1"),
            "2.2": old_data.get("2.2"),
            "tomorrow": old_data.get("tomorrow"),
        }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
