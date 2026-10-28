import os
import json
import datetime
from zoneinfo import ZoneInfo
import cloudscraper
import requests

PAGE_URL = "https://www.dtek-krem.com.ua/ua/shutdowns"
PUBLISHED_DATA_URL = "https://sc2djem.github.io/dtek-schedule/data.json"

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

    # Діагностика: які групи реально є у відповіді (лише для журналу)
    print("Ключі fact:", sorted(fact.keys()))
    print("preset на сторінці:", "DisconSchedule.preset" in html)
    for date_str, key in sorted(by_date.items()):
        groups_in_day = sorted(data[key].keys())
        print(f"Групи за {date_str} ({len(groups_in_day)}): {groups_in_day}")

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


def tomorrow_published(old_data, now):
    t = old_data.get("tomorrow")
    if not t:
        return False
    return t.get("date") == (now + datetime.timedelta(days=1)).strftime("%d.%m.%Y")


def should_fetch(now, old_data):
    """Вирішує, чи треба ходити на сайт ДТЕК у цьому запуску (за київським часом).

    Запуски приходять від cron-job.org за розкладом; тут лише додаткові правила.
    """
    # Примусовий запуск: галочка при ручному запуску або зміна файлів
    if os.environ.get("FORCE_RUN") == "true" or os.environ.get("GITHUB_EVENT_NAME") == "push":
        return True, "примусовий запуск"

    t = now.hour * 60 + now.minute

    # Ніч: після 22:30 і до 06:00 без оновлень.
    # Єдиний виняток: після півночі, бо "завтра" стало "сьогодні".
    if t > 22 * 60 + 30 or t < 6 * 60:
        if old_data.get("today_date") != now.strftime("%d.%m.%Y"):
            return True, "ніч: одне оновлення, бо настала нова доба"
        return False, "ніч (22:30-06:00): без оновлень"

    # Вечір з 19:00 до 22:30
    if t >= 19 * 60:
        if not tomorrow_published(old_data, now):
            return True, "вечір: чекаємо графік на завтра, кожні 15 хв"
        if now.minute % 30 < 15:
            return True, "вечір, графік на завтра вже є: кожні 30 хв"
        return False, "вечір, графік на завтра вже є: пропуск (кожні 30 хв)"

    return True, "день: кожні 30 хв"


def load_old_data():
    """Останній відомий графік: спочатку з файлу в репозиторії, потім з опублікованої сторінки."""
    if os.path.exists("data.json"):
        try:
            with open("data.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    try:
        res = requests.get(
            PUBLISHED_DATA_URL,
            params={"t": int(datetime.datetime.now().timestamp())},
            timeout=15,
        )
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"Не вдалося завантажити попередній data.json: {e}")
    return {}


IGNORED_KEYS = {"updated_at", "checked_at"}


def same_content(a, b):
    def strip(d):
        return {k: v for k, v in d.items() if k not in IGNORED_KEYS}
    return strip(a) == strip(b)


def main():
    now = datetime.datetime.now(KYIV)
    now_str = now.strftime("%d.%m.%Y %H:%M")

    old_data = load_old_data()

    go, reason = should_fetch(now, old_data)
    print(f"Київ {now_str}: {reason}")
    if not go:
        return

    try:
        today_str, today, tomorrow = fetch_schedule(now)
        new_data = {
            "status": "ok",
            "updated_at": now_str,  # час, коли графік востаннє змінився
            "today_date": today_str,
            "2.1": today["2.1"],
            "2.2": today["2.2"],
            "tomorrow": tomorrow,
        }
        print("OK: дані з сайту ДТЕК отримано")
    except Exception as e:
        print(f"ПОМИЛКА: {e}")
        # Лишаємо останній успішний графік, але позначаємо помилку
        new_data = {
            "status": "error",
            "error": str(e),
            "updated_at": old_data.get("updated_at", "невідомо"),
            "today_date": old_data.get("today_date"),
            "2.1": old_data.get("2.1"),
            "2.2": old_data.get("2.2"),
            "tomorrow": old_data.get("tomorrow"),
        }

    if old_data and same_content(old_data, new_data):
        print("Графік не змінився: data.json не переписуємо")
        return

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print("data.json оновлено")


if __name__ == "__main__":
    main()
