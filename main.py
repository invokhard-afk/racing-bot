import os
import json
import time
import random
import sqlite3
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import BadRequest

BOT_TOKEN =
open ("token.txt"). read() .strip()

CARS = [
    dict(key="kopeika", name="ВАЗ-2101 Копейка", emoji="🛞", price=0,         speed=20, accel=15, grip=12, need=1),
    dict(key="oka",      name="Ока",              emoji="🐸", price=3000,      speed=18, accel=23, grip=16, need=1),
    dict(key="lavrka",   name="ВАЗ-2107 Лаврка",  emoji="🚗", price=14000,     speed=29, accel=24, grip=19, need=3),
    dict(key="sobaka",   name="ВАЗ-2109 Собака",  emoji="🐕", price=48000,     speed=35, accel=31, grip=25, need=5),
    dict(key="niva",     name="Нива 4x4",         emoji="🌲", price=95000,     speed=37, accel=33, grip=40, need=7),
    dict(key="e30",      name="BMW E30 Тройка",   emoji="💨", price=230000,    speed=53, accel=43, grip=45, need=9),
    dict(key="w124",     name="Mercedes W124",    emoji="👑", price=460000,    speed=59, accel=47, grip=51, need=12),
    dict(key="supra",    name="Toyota Supra A80", emoji="🔥", price=950000,    speed=73, accel=63, grip=59, need=15),
    dict(key="gtr",      name="Nissan GT-R R35",  emoji="🥷", price=2100000,   speed=89, accel=79, grip=75, need=18),
    dict(key="chiron",   name="Bugatti Chiron",   emoji="🏎", price=6500000,   speed=100, accel=97, grip=91, need=22),
]

UP = {
    "eng": dict(name="Мотор", emoji="⚙️", base=2000, mult=2.00, max=10),
    "tir": dict(name="Шины",  emoji="🛞", base=1500, mult=1.95, max=10),
    "nit": dict(name="Нитро", emoji="🔥", base=3000, mult=2.10, max=10),
}
UP_ORDER = ["eng", "tir", "nit"]
WORK_COOLDOWN = 45 * 60


def car(key):
    for c in CARS:
        if c["key"] == key:
            return c
    return CARS[0]


def up_cost(kind, level):
    u = UP[kind]
    return int(u["base"] * u["mult"] ** level)


def stats(c, eng, tir, nit):
    return (c["speed"] + 6 * eng + 2 * tir,
            c["accel"] + 3 * eng + 5 * nit,
            c["grip"] + 5 * tir + 3 * nit)


def power(c, eng, tir, nit):
    s, a, g = stats(c, eng, tir, nit)
    return round(s * 0.45 + a * 0.35 + g * 0.20, 1)


def level_of(u):
    return 1 + u["eng"] + u["tir"] + u["nit"] + len(json.loads(u["owned"]))


def money(n):
    return f"{int(n):,}".replace(",", " ")


def connect():
    con = sqlite3.connect("cars.db")
    con.row_factory = sqlite3.Row
    con.execute("""CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY, money INT, car TEXT,
        eng INT, tir INT, nit INT, owned TEXT,
        wins INT, losses INT, last_work INT)""")
    con.commit()
    return con


def get_user(uid):
    con = connect()
    row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if row is None:
        con.execute("INSERT INTO users VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (uid, 1500, "kopeika", 0, 0, 0, "[]", 0, 0, 0))
        con.commit()
        row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    con.close()
    return row


def save_user(uid, **kw):
    con = connect()
    cols = ", ".join(f"{k}=?" for k in kw.keys())
    con.execute(f"UPDATE users SET {cols} WHERE id=?", (*kw.values(), uid))
    con.commit()
    con.close()


def kb(*rows):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d)] for t, d in rows])


def menu_kb():
    return kb(
        ("🚗 Гараж", "garage"), ("🏎 Гонка", "race"),
        ("⚙️ Тюнинг", "tune"), ("💼 Смена", "work"),
        ("🛒 Магазин", "shop"), ("🏆 Рейтинг", "rank"),
        ("ℹ️ Помощь", "help"))


def screen(uid, key):
    u = get_user(uid)
    c = car(u["car"])
    eng, tir, nit = u["eng"], u["tir"], u["nit"]
    owned = json.loads(u["owned"])
    lvl = level_of(u)
    p = power(c, eng, tir, nit)
    head = f"💰 {money(u['money'])} ₽   ·   ⭐️ Ур. {lvl}\n\n"

    if key == "menu":
        text = (f"Maшина: {c['emoji']} <b>{c['name']}</b>\n"
                f"Мощность: <b>{p}</b>\n\n"
                "Зарабатывай на сменах, тюнишь движок и обгоняй соперников.")
        return f"<b>🏎 Гонки Улиц</b>\n\n{head}{text}", menu_kb()

    if key == "garage":
        s, a, g = stats(c, eng, tir, nit)
        rows = []
        for k in UP_ORDER:
            lv = (eng, tir, nit)[UP_ORDER.index(k)]
            rows.append((f"{UP[k]['emoji']} {UP[k]['name']} {lv}/{UP[k]['max']}", f"open_{k}"))
        text = (f"{c['emoji']} <b>{c['name']}</b>\n\n"
                f"🏁 Мощность: <b>{p}</b>\n"
                f"⚡️ Скорость: {s} · 🚀 Разгон: {a} · 🤝 Сцепление: {g}\n\n"
                f"⚙️ Мotor {eng}/10 · 🛞 Шины {tir}/10 · 🔥 Нитро {nit}/10\n\n"
                f"🏆 Побед: {u['wins']} · 💀 Поражений: {u['losses']}")
        return f"<b>🚗 Гараж</b>\n\n{head}{text}", InlineKeyboardMarkup(
            inline_keyboard=rows + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]])

    if key == "tune":
        rows = []
        for k in UP_ORDER:
            u2 = UP[k]
            logo = u2["emoji"]
            lv = (eng, tir, nit)[UP_ORDER.index(k)]
            cost = "МАКС" if lv >= u2["max"] else f"{money(up_cost(k, lv))} ₽"
            rows.append((f"{logo} {u2['name']} {lv}/{u2['max']} — {cost}", f"up_{k}"))
        text = ("Каждый уровень заметно поднимает характеристики.\n"
                "Мотор → скорость и разгон · Шины → сцепление · Нитро → разгон.")
        return f"<b>⚙️ Тюнинг</b>\n\n{head}{text}", InlineKeyboardMarkup(
            inline_keyboard=rows + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]])

    if key == "shop":
        lines, rows = [], []
        for c2 in CARS:
            have = (c2["key"] in owned) or (c2["key"] == u["car"])
            mark = "✅" if have else ("🔒" if c2["need"] > lvl else "🆕")
            pw = power(c2, eng, tir, nit)
            lines.append(f"{mark} {c2['emoji']} <b>{c2['name']}</b> — {money(c2['price'])} ₽ (мощн. {pw})")
            if (not have) and c2["need"] <= lvl:
                rows.append((f"Купить: {invoke_name}", f"buy_{c2['key']}"))
        text = "\n".join(lines)
        buttons = InlineKeyboardMarkup(
            inline_keyboard=rows[:6] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu")]])
        return f"<b>🛒 Магазин</b>\n\n{head}{text}", buttons

    if key == "rank":
        con = connect()
        top = con.execute("SELECT * FROM users ORDER BY wins DESC, money DESC LIMIT 10").fetchall()
        con.close()
        lines = []
        for i, r in enumerate(top, 1):
            lines.append(f"{i}. {car(r['car'])['name']} — 🏆 {r['wins']} · 💰 {money(r['money'])} ₽")
        text = "\n".join(lines) if lines else "Пока пусто. Будь первым!"
        return f"<b>🏆 Рейтинг</b>\n\n{head}{text}", kb(("⬅️ Назад", "menu"))

    text = ("<b>Смена</b> — заработать деньги (кулдаун 45 мин).\n"
            "<b>Тюнинг</b> — прокачка мотора, шин и нитро.\n"
            "<b>Магазин</b> — новая машина, нужен нужный уровень.\n"
            "<b>Гонка</b> — плати взнос, побеждай сильного соперника за дvojную ставку.\n"
            "<b>Рейтинг</b> — таблица лидеров по победам.")
    return f"<b>ℹ️ Помощь</b>\n\n{head}{text}", kb(("⬅️ Назад", "menu"))


def make_opponent(player_power):
    pool = [c for c in CARS if power(c, 0, 0, 0) * 0.5 <= player_power <= power(c, 0, 0, 0) * 1.5]
    if not pool:
        pool = list(CARS)
    c = random.choice(pool)
    e, t, n = random.randint(0, 8), random.randint(0, 6), random.randint(0, 5)
    return c, e, t, n, power(c, e, t, n)


async def send(target, text, buttons):
    try:
        if isinstance(target, CallbackQuery):
            await target.message.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
        else:
            await target.answer(text, parse_mode=ParseMode.HTML, reply_markup=buttons)
    except BadRequest:
        pass


dp = Dispatcher()
bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


@dp.message(CommandStart())
async def cmd_start(m: Message):
    get_user(m.from_user.id)
    await send(m, *screen(m.from_user.id, "menu"))


@dp.message(Command("help"))
async def cmd_help(m: Message):
    await send(m, *screen(m.from_user.id, "help"))


@dp.message(Command("work"))
async def cmd_work(m: Message):
    uid = m.from_user.id
    u = get_user(uid)
    left = WORK_COOLDOWN - (int(time.time()) - u["last_work"])
    if left > 0:
        h, mm = divmod(left // 60 + 1, 60)
        return await send(m, f"⏳ Ты ещё на работе. Отдых через <b>{h} ч {mm} мин</b>.\n\n"
                             f"💰 Баланс: {money(u['money'])} ₽", menu_kb())
    pay = 400 + level_of(u) * 120 + random.randint(0, 250)
    save_user(uid, money=u["money"] + pay, last_work=int(time.time()))
    await send(m, f"💼 Смена отработана!\nЗаработал <b>{money(ppay)} ₽</b>.\n"
                   "Теперь можно тюнить или в магазин 🛠", menu_kb())


@dp.callback_query(F.data == "work")
async def cb_work(cb: CallbackQuery):
    await cmd_work(cb.message)


@dp.callback_query(F.data.startswith("open_"))
async def cb_open(cb: CallbackQuery):
    await send(cb, *screen(cb.from_user.id, "tune"))


@dp.callback_query(F.data.startswith("up_"))
async def cb_upgrade(cb: CallbackQuery):
    uid, kind = cb.from_user.id, cb.data[3:]
    if kind not in UP:
        return
    u = get_user(uid)
    lv = (u["eng"], u["tir"], u["nit"])[UP_ORDER.index(kind)]
    if lv >= UP[kind]["max"]:
        return await cb.answer("Максимальный уровень 🏆", show_alert=True)
    cost = up_cost(kind, lv)
    if u["money"] < cost:
        return await cb.answer(f"Не хватает {money(cost - u['money'])} ₽", show_alert=True)
    save_user(uid, money=u["money"] - cost, **{kind: lv + 1})
    await cb.answer(f"{UP[kind]['emoji']} {UP[kind]['name']} → {lv + 1}")
    await send(cb, *screen(uid, "tune"))


@dp.callback_query(F.data.startswith("buy_"))
async def cb_buy(cb: CallbackQuery):
    uid, key = cb.from_user.id, cb.data[4:]
    u = get_user(uid)
    c = car(key)
    owned = json.loads(u["owned"])
    if key in owned:
        return await cb.answer("Уже куплена", show_alert=True)
    if level_of(u) < c["need"]:
        return await cb.answer(f"Нужен {c['need']} уровень", show_alert=True)
    if u["money"] < c["price"]:
        return await cb.answer(f"Не хватает {money(c['price'] - u['money'])} ₽", show_alert=True)
    owned.append(key)
    save_user(uid, money=u["money"] - c["price"], car=key, owned=json.dumps(owned))
    await cb.answer("Поздравляю с покупкой! 🎉")
    await send(cb, *screen(uid, "garage"))


@dp.callback_query(F.data.startswith("race"))
async def cb_race(cb: CallbackQuery):
    if cb.data == "race":
        await send(cb, *race_screen(cb.from_user.id))
        return
    key, e, t, n = cb.data.split("_")[1:]
    await send(cb, *race_screen(cb.from_user.id))


def race_screen(uid):
    u = get_user(uid)
    p = power(car(u["car"]), u["eng"], u["tir"], u["nit"])
    c, e, t, n, op = make_opponent(p)
    lvl = level_of(u)
    entry = 150 + lvl * 40
    prize = 500 + lvl * 150
    text = (f"🔴 Ты: <b>{car(u['car'])['name']}</b> — мощность <b>{p}</b>\n"
            f"⚫️ Соперник: <(strong)>{c['name']}</(strong)> — мощность <b>{op}</b>\n"
            f"⚫️ Соперник:…
