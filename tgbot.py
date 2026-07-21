# Исправленная версия tgbot.py
# ВНИМАНИЕ: секреты вынесены в переменные окружения.
import asyncio
import io
import json
import os
import random
import re
import traceback
from datetime import datetime, timedelta

from telethon import TelegramClient, events
import matplotlib.pyplot as plt

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

if not API_ID or not API_HASH or not BOT_TOKEN:
    raise RuntimeError("Set TELEGRAM_API_ID, TELEGRAM_API_HASH and TELEGRAM_BOT_TOKEN environment variables")

DATA_FILE = "casino_users.json"
STATS_FILE = "casino_stats.json"
SESSION_FILE = "casino_bot.session"
PROMO_SECRET = os.getenv("PROMO_SECRET", "")
PROMO_AMOUNT = 10**150
JACKPOT_GIF = "https://media.giphy.com/media/3o6Zt6KHxJTbC0nKd2/giphy.gif"


def ensure_json_file(path):
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump({}, f)


def load_json(path):
    ensure_json_file(path)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(temp_path, path)


users = load_json(DATA_FILE)
stats = load_json(STATS_FILE)
client = TelegramClient(SESSION_FILE, API_ID, API_HASH)

RE_BALANCE_SHORT = re.compile(r"^б$", re.IGNORECASE)
RE_SLOTS_SHORT = re.compile(r"^с\s+(\d+)$", re.IGNORECASE)
RE_COIN_SHORT = re.compile(r"^м\s+(\d+)$", re.IGNORECASE)
RE_TRANSFER_SHORT = re.compile(r"^п\s+(\d+)$", re.IGNORECASE)
RE_BALANCE = re.compile(r"^/balance$", re.IGNORECASE)
RE_SLOTS = re.compile(r"^/slots\s+(\d+)$", re.IGNORECASE)
RE_COIN = re.compile(r"^/coin\s+(\d+)$", re.IGNORECASE)
RE_DAILY = re.compile(r"^/daily$", re.IGNORECASE)
RE_PROMO = re.compile(r"^/promo\s+(.+)$", re.IGNORECASE)
RE_START = re.compile(r"^/start$", re.IGNORECASE)
RE_HELP = re.compile(r"^/help$", re.IGNORECASE)
RE_TOP = re.compile(r"^/top$", re.IGNORECASE)
RE_MYSTATS = re.compile(r"^/mystats$", re.IGNORECASE)
RE_GRAPH = re.compile(r"^/graph$", re.IGNORECASE)


def fmt_balance(n):
    if n >= 10**12:
        return f"{n:.2e}".replace("e+", "×10^")
    if n >= 10**6:
        return f"{n / 10**6:.1f}M"
    if n >= 10**3:
        return f"{n / 10**3:.1f}K"
    return str(n)


def get_user(user_id):
    return users.setdefault(str(user_id), {
        "balance": 0,
        "last_daily": None,
        "promos_used": [],
    })


def get_stats(user_id):
    return stats.setdefault(str(user_id), {
        "games": 0,
        "wins": 0,
        "losses": 0,
    })


@client.on(events.NewMessage(pattern=RE_START))
async def start(event):
    await event.reply(
        "🎰 **Казино-бот** (виртуальные монеты)\n"
        "Используй короткие команды или слеш-версии.\n"
        "/help — все команды и инструкция.\n"
        "Удачи!"
    )


@client.on(events.NewMessage(pattern=RE_HELP))
async def help_cmd(event):
    text = (
        "🎰 **КАЗИНО-БОТ: ИНСТРУКЦИЯ**\n\n"
        "💰 Ежедневный бонус 50 000 — `/daily`\n"
        "🎁 Промокоды: `/promo <код>`\n\n"
        "🎲 **Игры:**\n"
        "• `/slots <ставка>` или `с <ставка>` — слот-машина\n"
        "• `/coin <ставка>` или `м <ставка>` — орёл/решка\n\n"
        "💸 **Переводы:**\n"
        "• Ответьте на сообщение получателя и напишите `п <сумма>`\n\n"
        "📊 **Статистика:**\n"
        "• `б` или `/balance` — баланс\n"
        "• `/mystats` — статистика игр\n"
        "• `/graph` — график побед/поражений\n"
        "• `/top` — топ-10 игроков"
    )
    await event.reply(text)


@client.on(events.NewMessage(pattern=RE_BALANCE_SHORT))
@client.on(events.NewMessage(pattern=RE_BALANCE))
async def balance(event):
    user = get_user(event.sender_id)
    await event.reply(f"💼 Ваш баланс: **{fmt_balance(user['balance'])}** монет")


@client.on(events.NewMessage(pattern=RE_SLOTS_SHORT))
@client.on(events.NewMessage(pattern=RE_SLOTS))
async def slots(event):
    await play_slots(event, int(event.pattern_match.group(1)))


async def play_slots(event, bet):
    if bet <= 0:
        await event.reply("❌ Ставка должна быть положительной.")
        return

    user_id = str(event.sender_id)
    user_data = get_user(user_id)
    balance = user_data["balance"]
    if balance < bet:
        await event.reply(f"❌ Недостаточно монет. Баланс: **{fmt_balance(balance)}**")
        return

    user_stats = get_stats(user_id)
    symbols = ["🍒", "🍋", "🍊", "🍇", "🔔", "💎", "7️⃣"]
    a, b, c = random.choices(symbols, k=3)
    result_line = f"{a} | {b} | {c}"

    if a == b == c:
        mult = 10
    elif a == b or b == c or a == c:
        mult = 2
    else:
        mult = 0

    user_stats["games"] += 1
    if mult > 0:
        change = bet * mult
        balance += change
        user_stats["wins"] += 1
        txt = f"🎰 {result_line}\n🎉 Выигрыш! +{fmt_balance(change)} (x{mult})"
        if a == b == c == "7️⃣":
            await event.reply(file=JACKPOT_GIF)
            txt += "\n🔥 **ДЖЕКПОТ!** 🔥"
    else:
        balance -= bet
        user_stats["losses"] += 1
        txt = f"🎰 {result_line}\n😞 Проигрыш. -{fmt_balance(bet)}"

    user_data["balance"] = max(0, balance)
    save_json(DATA_FILE, users)
    save_json(STATS_FILE, stats)
    await event.reply(f"{txt}\n💰 Баланс: **{fmt_balance(user_data['balance'])}**")


@client.on(events.NewMessage(pattern=RE_COIN_SHORT))
@client.on(events.NewMessage(pattern=RE_COIN))
async def coin(event):
    await play_coin(event, int(event.pattern_match.group(1)))


async def play_coin(event, bet):
    if bet <= 0:
        await event.reply("❌ Ставка должна быть положительной.")
        return

    user_id = str(event.sender_id)
    user_data = get_user(user_id)
    balance = user_data["balance"]
    if balance < bet:
        await event.reply(f"❌ Недостаточно монет. Баланс: **{fmt_balance(balance)}**")
        return

    user_stats = get_stats(user_id)
    user_stats["games"] += 1
    side = random.choice(["орел", "решка"])

    if random.random() < 0.5:
        win = bet * 2
        balance += win
        user_stats["wins"] += 1
        txt = f"🪙 {side}\n🎉 Победа! +{fmt_balance(win)}"
    else:
        balance -= bet
        user_stats["losses"] += 1
        txt = f"🪙 {side}\n😞 Поражение. -{fmt_balance(bet)}"

    user_data["balance"] = max(0, balance)
    save_json(DATA_FILE, users)
    save_json(STATS_FILE, stats)
    await event.reply(f"{txt}\n💰 Баланс: **{fmt_balance(user_data['balance'])}**")


@client.on(events.NewMessage(pattern=RE_TRANSFER_SHORT))
async def transfer(event):
    try:
        reply_msg = await event.message.get_reply_message()
        if not reply_msg:
            await event.reply("❌ Вы должны **ответить (reply)** на сообщение получателя.")
            return

        amount = int(event.pattern_match.group(1))
        if amount <= 0:
            await event.reply("❌ Сумма должна быть положительной.")
            return

        from_id = str(event.sender_id)
        to_id = str(reply_msg.sender_id)
        if from_id == to_id:
            await event.reply("❌ Нельзя перевести самому себе.")
            return

        from_data = get_user(from_id)
        to_data = get_user(to_id)
        if from_data["balance"] < amount:
            await event.reply(f"❌ Недостаточно средств. Ваш баланс: {fmt_balance(from_data['balance'])}")
            return

        try:
            sender_entity = await client.get_entity(int(from_id))
            sender_name = sender_entity.first_name or "Отправитель"
        except Exception:
            sender_name = "Отправитель"

        try:
            receiver_entity = await client.get_entity(int(to_id))
            receiver_name = receiver_entity.first_name or "Получатель"
        except Exception:
            receiver_name = "Получатель"

        from_data["balance"] -= amount
        to_data["balance"] += amount
        save_json(DATA_FILE, users)

        msg = (
            "💸 **Перевод выполнен!**\n"
            f"• {sender_name} ➡️ {receiver_name}\n"
            f"• Сумма: **{fmt_balance(amount)}** монет\n"
            f"• Ваш новый баланс: **{fmt_balance(from_data['balance'])}**"
        )
        await event.reply(msg)
    except Exception:
        print("Transfer error:", traceback.format_exc())
        await event.reply("❌ Ошибка при переводе. Попробуйте позже.")


@client.on(events.NewMessage(pattern=RE_DAILY))
async def daily(event):
    user_id = str(event.sender_id)
    now = datetime.now()
    user_data = get_user(user_id)
    last_daily = user_data.get("last_daily")

    if last_daily:
        try:
            last = datetime.fromisoformat(last_daily)
            if now - last < timedelta(hours=24):
                rem = timedelta(hours=24) - (now - last)
                hours, remainder = divmod(int(rem.total_seconds()), 3600)
                minutes = remainder // 60
                await event.reply(f"⏳ Бонус доступен через {hours} ч {minutes} мин")
                return
        except ValueError:
            pass

    bonus = 50000
    user_data["balance"] += bonus
    user_data["last_daily"] = now.isoformat()
    save_json(DATA_FILE, users)
    await event.reply(
        f"🎁 Ежедневный бонус: **{fmt_balance(bonus)}**\n"
        f"💰 Баланс: **{fmt_balance(user_data['balance'])}**"
    )


@client.on(events.NewMessage(pattern=RE_PROMO))
async def promo(event):
    code = event.pattern_match.group(1).strip()
    user_id = str(event.sender_id)
    user_data = get_user(user_id)

    promos = {"STARTBONUS": 25000}
    if PROMO_SECRET:
        promos[PROMO_SECRET] = PROMO_AMOUNT

    if code not in promos:
        await event.reply("❌ Неверный промокод.")
        return

    if code in user_data.get("promos_used", []):
        await event.reply("⚠️ Этот промокод уже использован.")
        return

    amount = promos[code]
    user_data["balance"] += amount
    user_data.setdefault("promos_used", []).append(code)
    save_json(DATA_FILE, users)
    await event.reply(
        f"🎁 Промокод активирован! +{fmt_balance(amount)}\n"
        f"💰 Баланс: **{fmt_balance(user_data['balance'])}**"
    )


@client.on(events.NewMessage(pattern=RE_TOP))
async def top_players(event):
    sorted_users = sorted(
        users.items(),
        key=lambda item: item[1].get("balance", 0),
        reverse=True,
    )
    top10 = sorted_users[:10]
    if not top10:
        await event.reply("🏆 Топ игроков пока пуст.")
        return

    text = "🏆 **ТОП-10 БОГАТЕЙШИХ ИГРОКОВ МИРА**\n\n"
    for i, (uid, data) in enumerate(top10, 1):
        try:
            user_entity = await client.get_entity(int(uid))
            name = user_entity.first_name or "Игрок"
        except Exception:
            name = f"id{uid}"
        text += f"{i}. {name} — {fmt_balance(data.get('balance', 0))}\n"

    await event.reply(text)


@client.on(events.NewMessage(pattern=RE_MYSTATS))
async def mystats(event):
    user_stats = get_stats(event.sender_id)
    total = user_stats["games"]
    if total == 0:
        await event.reply("📊 Вы ещё не сыграли ни одной игры.")
        return

    winrate = user_stats["wins"] / total * 100
    text = (
        "📊 **Ваша статистика:**\n"
        f"• Игр сыграно: {total}\n"
        f"• Побед: {user_stats['wins']}\n"
        f"• Поражений: {user_stats['losses']}\n"
        f"• Винрейт: {winrate:.1f}%"
    )
    await event.reply(text)


@client.on(events.NewMessage(pattern=RE_GRAPH))
async def graph_stats(event):
    user_stats = get_stats(event.sender_id)
    if user_stats["games"] == 0:
        await event.reply("❌ Нет данных для графика. Сыграйте хотя бы одну игру.")
        return

    labels = ["Победы", "Поражения"]
    sizes = [user_stats["wins"], user_stats["losses"]]
    explode = (0.05, 0) if user_stats["wins"] > 0 else (0, 0.05)

    plt.figure(figsize=(4, 4))
    plt.pie(sizes, explode=explode, labels=labels, autopct="%1.1f%%", startangle=140)
    plt.title("Ваши игры")
    plt.axis("equal")

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight")
    buf.seek(0)
    plt.close()

    await client.send_file(
        event.chat_id,
        buf,
        caption="📈 График побед/поражений",
        force_document=False,
    )
    buf.close()


async def main():
    await client.start(bot_token=BOT_TOKEN)
    print("🎰 Казино-бот запущен! Напишите /help.")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
