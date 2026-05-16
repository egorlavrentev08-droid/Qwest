# roulette.py
import asyncio
import random
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_balance, update_balance, add_roulette_log
from config import MIN_BET

# Красные и чёрные числа
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

# 10 кадров и их победители
ROULETTE_FRAMES = [
    ("🟩🟥⬛🟥⬛🟥⬛🟥⬛", "black"),   # 1 - чёрный
    ("⬛🟩🟥⬛🟥⬛🟥⬛🟥", "red"),     # 2 - красный
    ("🟥⬛🟩🟥⬛🟥⬛🟥⬛", "black"),   # 3 - чёрный
    ("⬛🟥⬛🟩🟥⬛🟥⬛🟥", "red"),     # 4 - красный
    ("🟥⬛🟥⬛🟩🟥⬛🟥⬛", "green"),   # 5 - ЗЕЛЁНЫЙ (1/37)
    ("⬛🟥⬛🟥⬛🟩🟥⬛🟥", "black"),   # 6 - чёрный
    ("🟥⬛🟥⬛🟥⬛🟩🟥⬛", "red"),     # 7 - красный
    ("⬛🟥⬛🟥⬛🟥⬛🟩🟥", "black"),   # 8 - чёрный
    ("🟥⬛🟥⬛🟥⬛🟥⬛🟩", "red"),     # 9 - красный
    ("⬛🟥⬛🟥⬛🟥⬛🟥⬛", "black"),   # 10 - чёрный
]

def get_roulette_result():
    """Возвращает (кадр, победитель) с честными вероятностями"""
    r = random.random()
    if r < 1/37:
        return ROULETTE_FRAMES[4]  # 5-й кадр (зелёный)
    other_frames = ROULETTE_FRAMES[:4] + ROULETTE_FRAMES[5:]
    return random.choice(other_frames)

def parse_roulette_bet(bet_str):
    bet_str = bet_str.lower().strip()
    if bet_str in ['black', 'red', 'green']:
        return ('color', bet_str)
    try:
        num = int(bet_str)
        if 0 <= num <= 36:
            return ('number', num)
    except:
        pass
    return None

def check_roulette_win(winner_color, bet_type, bet_value):
    if bet_type == 'color':
        if bet_value == 'green':
            return (winner_color == 'green', 35)
        return (winner_color == bet_value, 2)
    elif bet_type == 'number':
        if bet_value == 0:
            return (winner_color == 'green', 35)
        if bet_value in RED_NUMBERS:
            return (winner_color == 'red', 35)
        elif bet_value in BLACK_NUMBERS:
            return (winner_color == 'black', 35)
    return (False, 0)

def generate_animation_frames(count=8):
    frames = []
    for _ in range(count):
        length = random.choice([8, 9])
        colors = []
        start = random.choice(['🟥', '⬛'])
        for i in range(length):
            if i % 2 == 0:
                colors.append(start)
            else:
                colors.append('🟥' if start == '⬛' else '⬛')
        if random.random() < 0.3:
            pos = random.randint(0, length-1)
            colors[pos] = '🟩'
        line = ''.join(colors)
        if random.choice([True, False]):
            line = '  ' + line
        frames.append(line)
    return frames

async def roulette_animation(message, bet, bet_type, bet_value):
    final_frame, winner_color = get_roulette_result()
    anim_frames = generate_animation_frames(8)
    
    msg = await message.answer(
        f"🎡 КРУТИМ РУЛЕТКУ\n\n==========|==========\n{anim_frames[0]}\n==========|=========="
    )
    
    last_text = ""
    for i in range(1, 8):
        await asyncio.sleep(1.0)
        bar = "=" * 10
        new_text = f"🎡 КРУТИМ РУЛЕТКУ\n\n{bar}|{bar}\n{anim_frames[i]}\n{bar}|{bar}"
        if new_text != last_text:
            try:
                await msg.edit_text(new_text)
                last_text = new_text
            except:
                pass
    
    emoji = '🔴' if winner_color == 'red' else '⚫️' if winner_color == 'black' else '🟢'
    final_display = f"🎡 СТОП!\n\n==========|==========\n{final_frame}\n==========|==========\n\n🎲 ВЫПАЛО: {emoji} {winner_color.upper()}"
    
    try:
        await msg.edit_text(final_display)
    except:
        pass
    
    await asyncio.sleep(1)
    
    is_win, multiplier = check_roulette_win(winner_color, bet_type, bet_value)
    
    if is_win:
        win_amount = bet * multiplier
        new_balance = update_balance(message.from_user.id, win_amount)
        add_roulette_log(message.from_user.id, winner_color, win_amount)
        await message.answer(
            f"🎉 **ПОБЕДА!** 🎉\n\nСтавка: {bet:.2f}₽\nВыигрыш: {win_amount:.2f}₽\nМножитель: x{multiplier}\n\n💰 Новый баланс: {new_balance:.2f}₽",
            parse_mode="Markdown"
        )
    else:
        current_balance = get_balance(message.from_user.id)
        await message.answer(
            f"❌ **ПРОИГРЫШ** ❌\n\nСтавка: {bet:.2f}₽\n💰 Баланс: {current_balance:.2f}₽",
            parse_mode="Markdown"
        )

def register_roulette(dp):
    @dp.message(Command("roulette"))
    async def cmd_roulette(message: types.Message):
        try:
            parts = message.text.split()
            if len(parts) < 3:
                await message.answer("❌ Примеры:\n/roulette red 1000\n/roulette black 500\n/roulette 7 1000\n/roulette 0 500\n\n💰 Минимальная ставка: 10₽")
                return
            
            bet = float(parts[-1])
            if bet < MIN_BET:
                await message.answer(f"❌ Минимальная ставка {MIN_BET}₽")
                return
            
            balance = get_balance(message.from_user.id)
            if balance < bet:
                await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
                return
            
            bet_str = ' '.join(parts[1:-1])
            parsed = parse_roulette_bet(bet_str)
            if not parsed:
                await message.answer("❌ Неверная ставка! Пример: /roulette red 1000 или /roulette 7 500")
                return
            
            bet_type, bet_value = parsed
            update_balance(message.from_user.id, -bet)
            await roulette_animation(message, bet, bet_type, bet_value)
        except:
            await message.answer("❌ Ошибка! Использование: /roulette [цвет/число] [ставка]")
