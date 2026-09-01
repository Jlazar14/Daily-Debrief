#!/usr/bin/env python3
"""
Daily Debrief — sends Jackson a morning brief via Telegram.
Runs unattended on GitHub Actions. No dependencies beyond the standard library.

Data sources:
  - Weather: Open-Meteo (no API key required)
  - Markets: Stooq (no API key required)
  - Schoolwork: assignments.json in this repo (kept in sync with the Assignment Tracker)
  - Delivery: Telegram Bot API, using TELEGRAM_BOT_TOKEN from GitHub Actions secrets
"""

import json
import os
import sys
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

CHAT_ID = "6804789036"
LAT, LON = 40.1164, -88.2434  # Champaign-Urbana, IL
ASSIGNMENTS_FILE = os.path.join(os.path.dirname(__file__), "assignments.json")


def http_get_json(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def http_get_text(url):
    req = urllib.request.Request(url, headers={"User-Agent": "daily-debrief/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8")


def get_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weathercode"
        "&temperature_unit=fahrenheit&timezone=America%2FChicago"
    )
    try:
        data = http_get_json(url)
        daily = data["daily"]
        high = round(daily["temperature_2m_max"][0])
        low = round(daily["temperature_2m_min"][0])
        pop = daily["precipitation_probability_max"][0]
        code = daily["weathercode"][0]

        sky = {
            0: "clear sky", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
            45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
            61: "light rain", 63: "rain", 65: "heavy rain", 71: "light snow", 73: "snow",
            75: "heavy snow", 80: "rain showers", 81: "rain showers", 82: "violent rain showers",
            95: "thunderstorms", 96: "thunderstorms", 99: "severe thunderstorms",
        }.get(code, "mixed conditions")

        if high >= 90:
            tip = "Very hot — light clothes, sunscreen, hydrate."
        elif high >= 75:
            tip = "Warm — shorts weather."
        elif high >= 55:
            tip = "Mild — a light layer should do."
        elif high >= 35:
            tip = "Chilly — bring a real jacket."
        else:
            tip = "Cold — bundle up."
        if pop and pop >= 40:
            tip += " Bring an umbrella/rain layer too."

        return f"{sky.capitalize()}, high {high}°F / low {low}°F, {pop}% chance of rain. {tip}"
    except Exception as e:
        return f"(weather unavailable: {e})"


def get_markets():
    symbols = {"%5EGSPC": "S&P 500", "%5EDJI": "Dow", "%5EIXIC": "Nasdaq"}
    parts = []
    for symbol, label in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            meta = data["chart"]["result"][0]["meta"]
            price = meta["regularMarketPrice"]
            pct = meta["regularMarketChangePercent"]
            sign = "+" if pct >= 0 else ""
            parts.append(f"{label} {sign}{pct:.2f}% ({price:,.2f})")
        except Exception:
            parts.append(f"{label}: unavailable")
    return "Latest — " + ", ".join(parts)


def get_due_soon(days_ahead=3):
    try:
        with open(ASSIGNMENTS_FILE) as f:
            items = json.load(f)
    except Exception as e:
        return [], f"(assignments file error: {e})"

    today = date.today()
    window = today + timedelta(days=days_ahead)
    due = []
    for item in items:
        try:
            d = date.fromisoformat(item["due"])
        except Exception:
            continue
        if today <= d <= window:
            due.append((d, item))
    due.sort(key=lambda pair: pair[0])
    return due, None


def format_due_line(d, item, today):
    days = (d - today).days
    when = "today" if days == 0 else ("tomorrow" if days == 1 else d.strftime("%b %-d"))
    time_part = f" · {item['dueTime']}" if item.get("dueTime") else ""
    return f"{item['course']}: {item['title']} (due {when}{time_part})"


def send_telegram(token, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"Telegram send failed: {result}")
    return result


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)

    # The workflow fires at both 13:00 and 14:00 UTC to cover CDT/CST (Daylight
    # Saving switches in November). Only actually send during the 8 o'clock
    # hour in Chicago local time, so exactly one of those two firings sends.
    now_chicago = datetime.now(ZoneInfo("America/Chicago"))
    force = os.environ.get("FORCE_SEND") == "1"
    if not force and now_chicago.hour != 8:
        print(f"Skipping — local Chicago time is {now_chicago.strftime('%H:%M')}, not the 8am window.")
        return

    today = date.today()
    weekday_str = today.strftime("%A, %B %-d")

    weather = get_weather()
    markets = get_markets()
    due, due_err = get_due_soon()

    if due_err:
        due_lines = due_err
    elif not due:
        due_lines = "Nothing due in the next 3 days."
    else:
        due_lines = "\n".join(format_due_line(d, item, today) for d, item in due)

    message = (
        f"Daily Debrief — {weekday_str}\n\n"
        f"WEATHER\n{weather}\n\n"
        f"SCHOOLWORK (next 3 days)\n{due_lines}\n\n"
        f"MARKETS\n{markets}\n\n"
        f"— Sent automatically via GitHub Actions."
    )

    send_telegram(token, message)
    print("Sent successfully.")


if __name__ == "__main__":
    main()
