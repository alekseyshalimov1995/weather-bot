import os
import json
import time
import random
import threading
import telebot
import requests
from telebot import types

# === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ (для хостинга) ===
TOKEN = os.environ.get("TELEGRAM_TOKEN")
YANDEX_KEY = os.environ.get("YANDEX_WEATHER_KEY")

USERS_FILE = "users.json"
bot = telebot.TeleBot(TOKEN)
users = {}
users_lock = threading.Lock()

# === ХРАНИЛИЩЕ ===
def load_users():
    global users
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f)
        except Exception:
            users = {}
    else:
        users = {}

def save_users():
    with users_lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

# === КЛАВИАТУРЫ ===
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🌤 Погода сейчас", "🏙 Мой город")
    kb.row("⏰ Рассылка", "ℹ️ Помощь")
    kb.row("❌ Отключить рассылку")
    return kb

def city_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    cities = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск",
              "Екатеринбург", "Рига"]
    btns = [types.InlineKeyboardButton(c, callback_data=f"city:{c}") for c in cities]
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("✏️ Другой город", callback_data="city:other"))
    return kb

def time_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    presets = ["07:00 19:00", "08:00 20:00", "09:00 21:00", "10:00 22:00"]
    btns = [types.InlineKeyboardButton(t, callback_data=f"time:{t}") for t in presets]
    kb.add(*btns)
    kb.add(types.InlineKeyboardButton("✏️ Своё время", callback_data="time:other"))
    return kb

# === ГЕОКОДИНГ ===
def get_coordinates(city_name):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": city_name, "count": 1, "language": "ru", "format": "json"}
    try:
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "results" not in data or not data["results"]:
            return None
        res = data["results"][0]
        return {
            "name": res["name"],
            "lat": str(res["latitude"]),
            "lon": str(res["longitude"]),
            "country": res.get("country", ""),
        }
    except Exception:
        return None

# === ПОГОДА ===
def get_weather(lat, lon):
    url = "https://api.weather.yandex.ru/v2/forecast"
    headers = {"X-Yandex-API-Key": YANDEX_KEY}
    params = {"lat": lat, "lon": lon, "lang": "ru_RU", "limit": 1}
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        data = r.json()
        if "fact" not in data:
            return None
        return data["fact"]
    except Exception:
        return None

# === ЮМОР ===
def get_humorous_comment(fact):
    temp = fact.get("temp", 0)
    condition = fact.get("condition", "")

    if "rain" in condition or "drizzle" in condition or "showers" in condition:
        pool = [
            "Зонт сегодня — твой лучший друг. Не забудь его. ☔",
            "Погода шепчет: «Останься дома и посмотри сериал». 🎬",
            "Дождь — это просто небо плачет от того, что ты не выспался. 😢",
        ]
    elif temp >= 25:
        pool = [
            "Жара! Мороженое и вода — обязательная программа. 🍦",
            "Сегодня можно жарить яичницу прямо на асфальте. 🍳",
            "Кондиционер официально стал твоим лучшим другом. ❄️",
        ]
    elif temp <= -5:
        pool = [
            "Мороз крепчает, а ты — нет. Одевайся как капуста! 🥶",
            "Шапка — не признак слабости, а признак выживания. 🧣",
            "На улице так холодно, что даже мысли замерзают. 🧠❄️",
        ]
    elif "snow" in condition:
        pool = [
            "Снег — это красиво, пока не надо чистить машину. 🚗❄️",
            "Зима решила напомнить, кто здесь главный. ⛄",
        ]
    else:
        pool = [
            "Погода нормальная. Скучно, но жить можно. 🙂",
            "Ни жарко, ни холодно — золотая середина. ⚖️",
            "Хорошего дня! Даже если погода против. 😉",
        ]
    return random.choice(pool)

# === СООБЩЕНИЕ ===
CONDITIONS = {
    "clear": "ясно ☀️",
    "partly-cloudy": "малооблачно 🌤",
    "cloudy": "облачно ⛅",
    "overcast": "пасмурно ☁️",
    "drizzle": "морось 🌦",
    "light-rain": "небольшой дождь 🌧",
    "rain": "дождь 🌧",
    "moderate-rain": "умеренный дождь 🌧",
    "heavy-rain": "сильный дождь ⛈",
    "showers": "ливень 🌧",
    "wet-snow": "дождь со снегом 🌨",
    "light-snow": "небольшой снег 🌨",
    "snow": "снег ❄️",
    "snow-showers": "снегопад ❄️",
    "hail": "град 🌨",
    "thunderstorm": "гроза ⛈",
    "thunderstorm-with-rain": "гроза с дождём ⛈",
    "thunderstorm-with-hail": "гроза с градом ⛈",
}

def build_message(chat_id):
    u = users.get(str(chat_id))
    if not u:
        return None
    fact = get_weather(u["lat"], u["lon"])
    if not fact:
        return "⚠️ Не удалось получить погоду. Попробуйте позже."
    desc = CONDITIONS.get(fact.get("condition", ""), fact.get("condition", ""))
    humor = get_humorous_comment(fact)
    return (
        f"🌍 Погода в {u['name']}\n"
        f"🌡 Температура: {fact['temp']}°C (ощущается как {fact['feels_like']}°C)\n"
        f"☁️ {desc.capitalize()}\n"
        f"💨 Ветер: {fact['wind_speed']} м/с\n"
        f"💧 Влажность: {fact['humidity']}%\n\n"
        f"{humor}"
    )

def save_city(chat_id, coords):
    if chat_id not in users:
        users[chat_id] = {"times": []}
    users[chat_id].update({
        "name": coords["name"],
        "lat": coords["lat"],
        "lon": coords["lon"],
        "country": coords["country"],
    })
    save_users()

def save_times(chat_id, times_list):
    valid = []
    for t in times_list:
        hh, mm = t.split(":")
        hh, mm = int(hh), int(mm)
        if 0 <= hh <= 23 and 0 <= mm <= 59:
            valid.append(f"{hh:02d}:{mm:02d}")
        else:
            raise ValueError
    users[chat_id]["times"] = sorted(set(valid))
    users[chat_id].pop("last_sent", None)
    save_users()

# === КОМАНДА /start ===
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = str(message.chat.id)
    if chat_id in users:
        u = users[chat_id]
        times = ", ".join(u.get("times", [])) or "не задано"
        bot.send_message(
            message.chat.id,
            f"Привет! Твой город: {u['name']}.\n"
            f"Время рассылки: {times}.\n\n"
            f"Пользуйся кнопками внизу 👇",
            reply_markup=main_menu()
        )
    else:
        bot.send_message(
            message.chat.id,
            "Привет! Я присылаю погоду по расписанию.\n\n"
            "Для начала выбери город 👇",
            reply_markup=main_menu()
        )
        bot.send_message(message.chat.id, "Выбери город:", reply_markup=city_inline())

# === КНОПКИ ГЛАВНОГО МЕНЮ ===
@bot.message_handler(func=lambda m: m.text == "🌤 Погода сейчас")
def btn_weather(message):
    chat_id = str(message.chat.id)
    if chat_id not in users or "lat" not in users[chat_id]:
        bot.send_message(message.chat.id, "Сначала выбери город:", reply_markup=city_inline())
        return
    text = build_message(chat_id)
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

@bot.message_handler(func=lambda m: m.text == "🏙 Мой город")
def btn_city(message):
    bot.send_message(message.chat.id, "Выбери город:", reply_markup=city_inline())

@bot.message_handler(func=lambda m: m.text == "⏰ Рассылка")
def btn_time(message):
    chat_id = str(message.chat.id)
    if chat_id not in users or "lat" not in users[chat_id]:
        bot.send_message(message.chat.id, "Сначала выбери город:", reply_markup=city_inline())
        return
    bot.send_message(message.chat.id, "Выбери время рассылки:", reply_markup=time_inline())

@bot.message_handler(func=lambda m: m.text == "ℹ️ Помощь")
def btn_help(message):
    bot.send_message(
        message.chat.id,
        "Я умею:\n"
        "🌤 — присылать погоду прямо сейчас\n"
        "🏙 — менять город\n"
        "⏰ — настраивать время рассылки (можно несколько)\n"
        "❌ — отключать ежедневную рассылку\n\n"
        "Просто нажимай кнопки внизу 👇",
        reply_markup=main_menu()
    )

@bot.message_handler(func=lambda m: m.text == "❌ Отключить рассылку")
def btn_stop(message):
    chat_id = str(message.chat.id)
    if chat_id not in users:
        bot.send_message(message.chat.id, "Сначала выбери город.", reply_markup=main_menu())
        return

    if not users[chat_id].get("times"):
        bot.send_message(message.chat.id, "У тебя и так нет активной рассылки. 🙂",
                         reply_markup=main_menu())
        return

    users[chat_id]["times"] = []
    users[chat_id].pop("last_sent", None)
    save_users()

    bot.send_message(
        message.chat.id,
        "✅ Рассылка отключена. Погоду можно запросить в любой момент кнопкой «🌤 Погода сейчас».\n\n"
        "Захочешь вернуть — нажми «⏰ Рассылка».",
        reply_markup=main_menu()
    )

# === КОМАНДЫ (для совместимости) ===
@bot.message_handler(commands=['weather'])
def cmd_weather(message):
    btn_weather(message)

@bot.message_handler(commands=['city'])
def cmd_city(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Выбери город:", reply_markup=city_inline())
        return
    coords = get_coordinates(parts[1].strip())
    if not coords:
        bot.send_message(message.chat.id, f"Не нашёл город «{parts[1]}».")
        return
    save_city(str(message.chat.id), coords)
    bot.send_message(message.chat.id,
                     f"✅ Город: {coords['name']}, {coords['country']}\n\nТеперь выбери время:",
                     reply_markup=time_inline())

@bot.message_handler(commands=['time'])
def cmd_time(message):
    parts = message.text.split()[1:]
    if not parts:
        bot.send_message(message.chat.id, "Выбери время:", reply_markup=time_inline())
        return
    chat_id = str(message.chat.id)
    if chat_id not in users:
        bot.send_message(message.chat.id, "Сначала выбери город.")
        return
    try:
        save_times(chat_id, parts)
    except Exception:
        bot.send_message(message.chat.id, "❌ Неверный формат. Пример: /time 08:00 20:00")
        return
    bot.send_message(message.chat.id, f"✅ Время: {', '.join(users[chat_id]['times'])}",
                     reply_markup=main_menu())

# === ИНЛАЙН: ВЫБОР ГОРОДА ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("city:"))
def cb_city(call):
    chat_id = str(call.message.chat.id)
    value = call.data.split(":", 1)[1]

    if value == "other":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "Напиши название города (например: Сочи):",
            reply_markup=types.ForceReply(selective=True)
        )
        return

    coords = get_coordinates(value)
    if not coords:
        bot.answer_callback_query(call.id, "Город не найден", show_alert=True)
        return

    save_city(chat_id, coords)
    bot.answer_callback_query(call.id, "Город сохранён")
    bot.send_message(
        call.message.chat.id,
        f"✅ Город: {coords['name']}, {coords['country']}\n\nТеперь выбери время рассылки:",
        reply_markup=time_inline()
    )

# === ИНЛАЙН: ВЫБОР ВРЕМЕНИ ===
@bot.callback_query_handler(func=lambda call: call.data.startswith("time:"))
def cb_time(call):
    chat_id = str(call.message.chat.id)
    value = call.data.split(":", 1)[1]

    if value == "other":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "Напиши время в формате ЧЧ:ММ через пробел.\nНапример: 08:00 20:00",
            reply_markup=types.ForceReply(selective=True)
        )
        return

    if chat_id not in users:
        bot.answer_callback_query(call.id, "Сначала выбери город", show_alert=True)
        return

    try:
        save_times(chat_id, value.split())
    except Exception:
        bot.answer_callback_query(call.id, "Ошибка времени", show_alert=True)
        return

    bot.answer_callback_query(call.id, "Время сохранено")
    bot.send_message(
        call.message.chat.id,
        f"✅ Время рассылки: {', '.join(users[chat_id]['times'])}",
        reply_markup=main_menu()
    )

# === ОТВЕТЫ НА ForceReply ===
@bot.message_handler(
    func=lambda m: m.reply_to_message and m.reply_to_message.text
    and "Напиши название города" in m.reply_to_message.text,
    content_types=['text']
)
def reply_city(message):
    chat_id = str(message.chat.id)
    city_query = message.text.strip()
    coords = get_coordinates(city_query)
    if not coords:
        bot.send_message(message.chat.id,
                         f"Не нашёл город «{city_query}». Попробуй ещё раз:")
        return
    save_city(chat_id, coords)
    bot.send_message(
        message.chat.id,
        f"✅ Город: {coords['name']}, {coords['country']}\n\nТеперь выбери время рассылки:",
        reply_markup=time_inline()
    )

@bot.message_handler(
    func=lambda m: m.reply_to_message and m.reply_to_message.text
    and "Напиши время" in m.reply_to_message.text,
    content_types=['text']
)
def reply_time(message):
    chat_id = str(message.chat.id)
    if chat_id not in users:
        bot.send_message(message.chat.id, "Сначала выбери город.")
        return
    try:
        save_times(chat_id, message.text.split())
    except Exception:
        bot.send_message(message.chat.id,
                         "❌ Неверный формат. Пример: 08:00 20:00")
        return
    bot.send_message(
        message.chat.id,
        f"✅ Время рассылки: {', '.join(users[chat_id]['times'])}",
        reply_markup=main_menu()
    )

# === ПЛАНИРОВЩИК ===
def scheduler_loop():
    while True:
        try:
            now = time.strftime("%H:%M")
            today = time.strftime("%Y-%m-%d")

            for chat_id in list(users.keys()):
                u = users.get(chat_id, {})
                if now in u.get("times", []):
                    key = f"{today} {now}"
                    if u.get("last_sent") == key:
                        continue
                    try:
                        text = build_message(chat_id)
                        if text:
                            bot.send_message(int(chat_id), text)
                            u["last_sent"] = key
                            save_users()
                    except Exception:
                        pass
        except Exception:
            pass
        time.sleep(20)

# === ЗАПУСК ===
if __name__ == "__main__":
    load_users()
    threading.Thread(target=scheduler_loop, daemon=True).start()
    bot.polling(none_stop=True)