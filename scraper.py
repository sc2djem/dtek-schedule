import os
import re
import json
import time
import datetime
from zoneinfo import ZoneInfo
import cloudscraper
import requests

PAGE_URL = "https://www.dtek-krem.com.ua/ua/shutdowns"
PUBLISHED_DATA_URL = "https://sc2djem.github.io/dtek-schedule/data.json"

# Київський час із автоматичним переходом літній/зимовий
KYIV = ZoneInfo("Europe/Kyiv")

# Значення ДТЕК -> значення, які розуміє index.html і застосунок
STATUS_MAP = {
    "yes": "yes",
    "no": "no",
    "first": "maybe_first",    # світла немає перші 30 хв
    "second": "maybe_second",  # світла немає другі 30 хв
    "mfirst": "maybe_first",
    "msecond": "maybe_second",
    "maybe": "yes",            # "можливе відключення" показуємо як "світло є"
}

# Групи, які залишаються окремими полями data.json для сумісності зі старим застосунком
LEGACY_GROUPS = ("2.1", "2.2")


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
        return None
    raw = day[group_key]
    if not isinstance(raw, dict):
        print(f"Група {group}: неочікуваний формат даних")
        return None

    hours = []
    for i in range(1, 25):
        value = raw.get(str(i), "yes")
        if value not in STATUS_MAP:
            print(f"Невідоме значення '{value}' о годині {i} (група {group})")
        hours.append(STATUS_MAP.get(value, "yes"))
    return hours


def group_ids(day):
    """Усі групи, що є у відповіді, у порядку 1.1, 1.2, 2.1 ..."""
    ids = []
    for key in day.keys():
        m = re.fullmatch(r"GPV(\d+)\.(\d+)", key)
        if m:
            ids.append((int(m.group(1)), int(m.group(2))))
    return [f"{a}.{b}" for a, b in sorted(ids)]


def all_groups_hours(day):
    result = {}
    for g in group_ids(day):
        hours = hours_for_group(day, g)
        if hours:
            result[g] = hours
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
    if len(html) < 10000 and "_Incapsula_Resource" in html:
        raise RuntimeError("ДТЕК показав сторінку захисту від автоматичних запитів (Incapsula)")
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

    today_groups = all_groups_hours(data[today_key])
    print(f"Груп на сьогодні: {len(today_groups)}")
    if not today_groups:
        raise RuntimeError("У відповіді немає жодної групи (структура даних змінилась?)")

    tomorrow_groups = None
    tomorrow_key = by_date.get(tomorrow_str)
    if tomorrow_key is not None:
        tg = all_groups_hours(data[tomorrow_key])
        if tg:
            tomorrow_groups = tg
            print(f"Графік на завтра ({tomorrow_str}) знайдено, груп: {len(tg)}")
    if tomorrow_groups is None:
        print(f"Графіка на завтра ({tomorrow_str}) ще немає")

    return today_str, today_groups, tomorrow_str, tomorrow_groups


def fetch_with_retries(now, attempts=3, delay=45):
    """ДТЕК іноді на кілька хвилин показує сторінку захисту, тому пробуємо кілька разів."""
    last_error = None
    for i in range(attempts):
        try:
            return fetch_schedule(now)
        except Exception as e:
            last_error = e
            print(f"Спроба {i + 1} з {attempts} невдала: {e}")
            if i < attempts - 1:
                time.sleep(delay)
    raise last_error


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


def build_data(now_str, today_str, today_groups, tomorrow_str, tomorrow_groups):
    groups = {
        g: {"today": hours, "tomorrow": (tomorrow_groups or {}).get(g)}
        for g, hours in today_groups.items()
    }
    tomorrow_legacy = None
    if tomorrow_groups:
        tomorrow_legacy = {"date": tomorrow_str}
        for g in LEGACY_GROUPS:
            tomorrow_legacy[g] = tomorrow_groups.get(g)

    data = {
        "schema": 2,
        "status": "ok",
        "updated_at": now_str,  # час, коли графік востаннє змінився
        "today_date": today_str,
        "tomorrow": tomorrow_legacy,
        "groups": groups,
    }
    # Старі поля для групи 2.1 і 2.2 (їх читає поточний застосунок)
    for g in LEGACY_GROUPS:
        data[g] = today_groups.get(g)
    return data


def main():
    now = datetime.datetime.now(KYIV)
    now_str = now.strftime("%d.%m.%Y %H:%M")

    old_data = load_old_data()

    go, reason = should_fetch(now, old_data)
    print(f"Київ {now_str}: {reason}")
    if not go:
        return

    try:
        today_str, today_groups, tomorrow_str, tomorrow_groups = fetch_with_retries(now)
        new_data = build_data(now_str, today_str, today_groups, tomorrow_str, tomorrow_groups)
        print("OK: дані з сайту ДТЕК отримано")
    except Exception as e:
        print(f"ПОМИЛКА: {e}")
        # Лишаємо останній відомий графік, позначаємо помилку і час її початку
        new_data = dict(old_data)
        was_error = old_data.get("status") == "error"
        new_data["status"] = "error"
        new_data["error"] = str(e)
        new_data["error_since"] = (old_data.get("error_since") if was_error else None) or now_str
        new_data["error_since_ts"] = (old_data.get("error_since_ts") if was_error else None) or int(now.timestamp())
        new_data.setdefault("updated_at", "невідомо")

    if old_data and same_content(old_data, new_data):
        print("Нічого не змінилось: data.json не переписуємо")
        return

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)
    print("data.json оновлено")


if __name__ == "__main__":
    main()
