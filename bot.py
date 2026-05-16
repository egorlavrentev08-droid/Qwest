# bot.py
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

from config import API_TOKEN, ADMIN_CODE, BONUS_AMOUNT, MIN_BET
from database import init_db, get_balance, update_balance, get_bonus_time, set_bonus_time
from roulette import register_roulette
from mines import register_mines
from joker import register_joker

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализируем БД
init_db()

# Регистрируем игры
register_roulette(dp)
register_mines(dp)
register_joker(dp)

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        "🎰 КАЗИНО ДОЛИНА\n\n"
        "🎲 /mines [мин] [ставка] - Мины (3-24 мин)\n"
        "🎡 /roulette [цвет/число] [ставка] - Рулетка\n"
        "   Пример: /roulette red 1000 или /roulette 7 500\n"
        "🃏 /joker [ставка] - Джокер\n"
        "💰 /bonus - Бонус 10000₽ (раз в день)\n"
        "💳 /balance - Баланс\n"
        "📤 /pay [сумма] - ответом на сообщение\n"
        f"\n💰 Баланс: {balance:.2f}₽"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    await message.answer(f"💰 Баланс: {get_balance(message.from_user.id):.2f}₽")

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    last_bonus = get_bonus_time(user_id)
    
    if last_bonus:
        try:
            last_time = datetime.fromisoformat(last_bonus)
            if datetime.now() - last_time < timedelta(days=1):
                hours_left = 24 - (datetime.now() - last_time).seconds // 3600
                await message.answer(f"❌ Бонус можно получить через {hours_left} часов!")
                return
        except:
            pass
    
    new_balance = update_balance(user_id, BONUS_AMOUNT)
    set_bonus_time(user_id)
    await message.answer(f"🎁 +{BONUS_AMOUNT}₽! Баланс: {new_balance:.2f}₽")

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение получателя!")
        return
    
    try:
        amount = float(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма должна быть больше 0")
            return
    except:
        await message.answer("❌ Использование: /pay [сумма] (ответ на сообщение)")
        return
    
    sender = message.from_user.id
    receiver = message.reply_to_message.from_user.id
    
    if receiver == bot.id:
        await message.answer("❌ Нельзя переводить деньги боту!")
        return
    if sender == receiver:
        await message.answer("❌ Нельзя перевести самому себе!")
        return
    
    sender_balance = get_balance(sender)
    if sender_balance < amount:
        await message.answer(f"❌ Недостаточно средств! Баланс: {sender_balance:.2f}₽")
        return
    
    update_balance(sender, -amount)
    new_receiver_balance = update_balance(receiver, amount)
    
    await message.answer(f"✅ Переведено {amount:.2f}₽ пользователю {receiver}")
    await bot.send_message(receiver, f"💰 Вы получили {amount:.2f}₽! Баланс: {new_receiver_balance:.2f}₽")

@dp.message(Command("money"))
async def admin_money(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3 or parts[1] != ADMIN_CODE:
        return
    try:
        amount = float(parts[2])
        new_balance = update_balance(message.from_user.id, amount)
        await message.answer(f"✅ Выдано {amount:.2f}₽. Баланс: {new_balance:.2f}₽")
    except:
        pass

@dp.callback_query(lambda c: c.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    print("🎰 КАЗИНО БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
