import asyncio
import random
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8773046663:AAFFIQLaymzRJCP_VkIGI2hMudOAUFbroMw"
ADMIN_CODE = "14916253649"
BONUS_AMOUNT = 10000

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# БД
conn = sqlite3.connect('casino_bot.db', check_same_thread=False)
cursor = conn.cursor()

# Создаём таблицы
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0,
        last_bonus TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS roulette_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        result TEXT,
        win_amount REAL,
        timestamp TEXT
    )
''')
conn.commit()

# ========== ФУНКЦИИ БАЛАНСА ==========
def get_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, 0))
    conn.commit()
    return 0

def update_balance(user_id, amount):
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()

# ========== РУЛЕТКА ==========
def roulette_spin():
    r = random.random()
    if r < 0.485:
        return 'black'
    elif r < 0.97:
        return 'red'
    return 'green'

def get_random_line():
    colors = ['⬛', '🟥', '⬛', '🟥', '⬛', '🟥', '⬛', '🟥']
    colors[random.randint(0, 7)] = '🟩'
    return ''.join(colors)

def check_win(final, bet_type, bet_val):
    if bet_type == 'color':
        if bet_val == 'green':
            return final == 'green', 35
        return final == bet_val, 2
    if bet_type == 'number':
        if bet_val == 0:
            return final == 'green', 35
        red_nums = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
        black_nums = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}
        if bet_val in red_nums:
            return final == 'red', 35
        if bet_val in black_nums:
            return final == 'black', 35
        return False, 0
    return False, 0

def parse_bet(bet_str):
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

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎰 КАЗИНО ДОЛИНА\n\n"
        "/mines [мин] [ставка] - Мины (3-24 мин, от 10₽)\n"
        "/roulette [цвет/число] [ставка] - Рулетка (от 500₽)\n"
        "/joker [ставка] - Джокер (от 100₽)\n"
        "/bonus - Бонус 10000₽ (раз в день)\n"
        "/balance - Баланс\n"
        "/pay [сумма] - ответом на сообщение\n"
        f"\n💰 Баланс: {get_balance(message.from_user.id):.2f}₽"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    await message.answer(f"💰 Баланс: {get_balance(message.from_user.id):.2f}₽")

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    
    if row and row[0]:
        last = datetime.fromisoformat(row[0])
        if datetime.now() - last < timedelta(days=1):
            await message.answer("❌ Бонус раз в 24 часа!")
            return
    
    update_balance(user_id, BONUS_AMOUNT)
    cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
    conn.commit()
    
    await message.answer(f"🎁 +{BONUS_AMOUNT}₽! Баланс: {get_balance(user_id):.2f}₽")

@dp.message(Command("pay"))
async def cmd_pay(message: types.Message):
    if not message.reply_to_message:
        await message.answer("❌ Ответь на сообщение получателя")
        return
    
    try:
        amount = float(message.text.split()[1])
        if amount <= 0:
            await message.answer("❌ Сумма > 0")
            return
    except:
        await message.answer("❌ /pay [сумма]")
        return
    
    sender = message.from_user.id
    receiver = message.reply_to_message.from_user.id
    
    if receiver == bot.id:
        await message.answer("❌ Нельзя боту")
        return
    if sender == receiver:
        await message.answer("❌ Себе нельзя")
        return
    if get_balance(sender) < amount:
        await message.answer("❌ Не хватает")
        return
    
    update_balance(sender, -amount)
    update_balance(receiver, amount)
    await message.answer(f"✅ Переведено {amount:.2f}₽")
    await bot.send_message(receiver, f"💰 +{amount:.2f}₽ от {sender}")

@dp.message(Command("money"))
async def admin_money(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3 or parts[1] != ADMIN_CODE:
        return
    try:
        amount = float(parts[2])
        update_balance(message.from_user.id, amount)
        await message.answer(f"✅ +{amount:.2f}₽")
    except:
        pass

# ========== МИНЫ ==========
class MinesGame:
    def __init__(self, uid, bet, mines):
        self.uid = uid
        self.bet = bet
        self.mines = mines
        self.field = [[0]*5 for _ in range(5)]
        self.revealed = [[False]*5 for _ in range(5)]
        self.active = True
        
        pos = [(i,j) for i in range(5) for j in range(5)]
        for i,j in random.sample(pos, mines):
            self.field[i][j] = 1
    
    def mult(self, opened):
        if opened == 0:
            return 1.0
        safe = 25 - self.mines
        p = 1.0
        for i in range(opened):
            p *= (safe - i) / (25 - i)
        return (1/p) * 0.92
    
    def reveal(self, row, col):
        if not self.active or self.revealed[row][col]:
            return None
        self.revealed[row][col] = True
        opened = sum(sum(r) for r in self.revealed)
        if self.field[row][col] == 1:
            self.active = False
            return ('lose', opened)
        return ('win', opened, self.mult(opened))
    
    def cashout(self):
        if not self.active:
            return 0
        opened = sum(sum(r) for r in self.revealed)
        if opened == 0:
            return 0
        win = self.bet * self.mult(opened)
        update_balance(self.uid, win - self.bet)
        self.active = False
        return win
    
    def final_board(self):
        kb = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                kb.button(text="💣" if self.field[i][j] else "⭐", callback_data="noop")
            kb.adjust(5)
        return kb.as_markup()

mines_games = {}

@dp.message(Command("mines"))
async def cmd_mines(message: types.Message):
    try:
        parts = message.text.split()
        mines = int(parts[1])
        bet = float(parts[2])
        
        if mines < 3 or mines > 24:
            await message.answer("❌ Мины 3-24")
            return
        if bet < 10:
            await message.answer("❌ Ставка от 10₽")
            return
        if get_balance(message.from_user.id) < bet:
            await message.answer("❌ Не хватает")
            return
        
        update_balance(message.from_user.id, -bet)
        game = MinesGame(message.from_user.id, bet, mines)
        mines_games[message.from_user.id] = game
        
        kb = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                kb.button(text="❓", callback_data=f"m_{i}_{j}")
            kb.adjust(5)
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="m_cancel"))
        
        await message.answer(
            f"💣 МИНЫ | Ставка: {bet:.2f}₽ | Мин: {mines}\nМножитель: x{game.mult(0):.2f}",
            reply_markup=kb.as_markup()
        )
    except:
        await message.answer("❌ /mines [3-24] [ставка]")

@dp.callback_query(lambda c: c.data.startswith('m_'))
async def mines_cb(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.active:
        await callback.answer("Игра не активна")
        return
    
    data = callback.data.split('_')
    
    if data[1] == 'cancel':
        update_balance(callback.from_user.id, game.bet)
        del mines_games[callback.from_user.id]
        await callback.message.edit_text("❌ Отмена, ставка возвращена")
        await callback.answer()
        return
    
    if data[1] == 'cashout':
        win = game.cashout()
        board = game.final_board()
        await callback.message.edit_text(f"💰 Забрал {win:.2f}₽\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    row, col = int(data[1]), int(data[2])
    res = game.reveal(row, col)
    
    if res[0] == 'lose':
        board = game.final_board()
        await callback.message.edit_text(f"💥 МИНА! Проигрыш {game.bet:.2f}₽\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    opened, mult = res[1], res[2]
    kb = InlineKeyboardBuilder()
    for i in range(5):
        for j in range(5):
            if game.revealed[i][j]:
                kb.button(text="⭐" if game.field[i][j]==0 else "💣", callback_data=f"m_{i}_{j}")
            else:
                kb.button(text="❓", callback_data=f"m_{i}_{j}")
        kb.adjust(5)
    
    if opened == 25 - game.mines:
        win = game.cashout()
        board = game.final_board()
        await callback.message.edit_text(f"🎉 ПОБЕДА! +{win:.2f}₽\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
    else:
        kb.row(
            InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="m_cashout"),
            InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="m_cancel")
        )
        await callback.message.edit_text(
            f"✅ Открыто: {opened} | Множитель: x{mult:.2f}\n💰 Выигрыш: {game.bet*mult:.2f}₽",
            reply_markup=kb.as_markup()
        )
    await callback.answer()

# ========== ДЖОКЕР ==========
class JokerGame:
    def __init__(self, uid, bet):
        self.uid = uid
        self.bet = bet
        self.rows = [[('🎴', False)]*3]
        self._add_row()
    
    def _add_row(self):
        row = []
        for _ in range(3):
            row.append(('🃏', False) if random.random() < 0.333 else ('🎴', False))
        self.rows.append(row)
    
    def reveal(self, r, c):
        if r >= len(self.rows):
            return None
        card, rev = self.rows[r][c]
        if rev:
            return None
        self.rows[r][c] = (card, True)
        if card == '🃏':
            self._add_row()
            return 'win'
        return 'lose'
    
    def total_win(self):
        jokers = sum(1 for row in self.rows for card, rev in row if rev and card == '🃏')
        if jokers == 0:
            return 0
        total = 1.0
        for i in range(jokers):
            total += 0.3 + i * 0.1
        return self.bet * total
    
    def cashout(self):
        win = self.total_win()
        if win > 0:
            update_balance(self.uid, win - self.bet)
        return win

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        if bet < 100:
            await message.answer("❌ Ставка от 100₽")
            return
        if get_balance(message.from_user.id) < bet:
            await message.answer("❌ Не хватает")
            return
        update_balance(message.from_user.id, -bet)
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        await show_joker(message, game)
    except:
        await message.answer("❌ /joker [ставка от 100]")

async def show_joker(msg, game, edit=True, cb=None):
    kb = InlineKeyboardBuilder()
    for r, row in enumerate(game.rows):
        for c, (card, rev) in enumerate(row):
            kb.button(text=card if rev else "❓", callback_data=f"jk_{r}_{c}")
        kb.adjust(3)
    kb.row(InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="jk_cashout"))
    
    jokers = sum(1 for row in game.rows for card, rev in row if rev and card == '🃏')
    text = f"🃏 ДЖОКЕР | Ставка: {game.bet:.2f}₽\n"
    if jokers > 0:
        mult = 1.0
        for i in range(jokers):
            mult += 0.3 + i * 0.1
        text += f"✅ Джокеров: {jokers} | Множитель: x{mult:.2f}\n💰 Выигрыш: {game.bet*mult:.2f}₽"
    else:
        text += "❓ Ищи джокера! +30% за каждого"
    
    if edit and cb:
        await cb.message.edit_text(text, reply_markup=kb.as_markup())
    elif edit:
        await msg.edit_text(text, reply_markup=kb.as_markup())
    else:
        await msg.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith('jk_'))
async def joker_cb(callback: types.CallbackQuery):
    game = joker_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Игра не активна")
        return
    
    if callback.data == "jk_cashout":
        win = game.cashout()
        await callback.message.edit_text(f"💰 Забрал {win:.2f}₽" if win > 0 else "❌ Проигрыш")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    
    _, r, c = callback.data.split('_')
    res = game.reveal(int(r), int(c))
    
    if res is None:
        await callback.answer("Уже открыто")
        return
    
    if res == 'lose':
        await callback.message.edit_text(f"😔 Обычная карта! Проигрыш {game.bet:.2f}₽")
        del joker_games[callback.from_user.id]
    else:
        await show_joker(callback.message, game, edit=True, cb=callback)
        await callback.answer("🎉 ДЖОКЕР! +1 ряд")
    await callback.answer()

# ========== РУЛЕТКА С АНИМАЦИЕЙ ==========
async def roulette_anim(msg, bet, bet_type, bet_val):
    frames = [get_random_line() for _ in range(35)]
    final = roulette_spin()
    
    m = await msg.answer(f"🎡\n==========|==========\n{frames[0]}\n==========|==========")
    
    for i, f in enumerate(frames):
        if i < 12:
            delay = 0.08
        elif i < 22:
            delay = 0.15
        elif i < 28:
            delay = 0.3
        else:
            delay = 0.5
        await m.edit_text(f"🎡\n==========|==========\n{f}\n==========|==========")
        await asyncio.sleep(delay)
    
    emoji = '🔴' if final == 'red' else '⚫️' if final == 'black' else '🟢'
    await m.edit_text(f"🎡 СТОП!\n==========|==========\n{get_random_line()}\n==========|==========\n\n{emoji} {final.upper()}")
    await asyncio.sleep(1)
    
    win, mult = check_win(final, bet_type, bet_val)
    if win:
        win_amount = bet * mult
        update_balance(msg.chat.id, win_amount - bet)
        await msg.answer(f"🎉 ПОБЕДА! +{win_amount:.2f}₽ (x{mult})\n💰 Баланс: {get_balance(msg.chat.id):.2f}₽")
    else:
        await msg.answer(f"❌ ПРОИГРЫШ -{bet:.2f}₽\n💰 Баланс: {get_balance(msg.chat.id):.2f}₽")

@dp.message(Command("roulette"))
async def cmd_roulette(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer("❌ /roulette [black/red/green/число] [ставка от 500]")
            return
        
        bet = float(parts[-1])
        if bet < 500:
            await message.answer("❌ Ставка от 500₽")
            return
        if get_balance(message.from_user.id) < bet:
            await message.answer("❌ Не хватает")
            return
        
        bet_str = ' '.join(parts[1:-1])
        parsed = parse_bet(bet_str)
        if not parsed:
            await message.answer("❌ Ставка: black/red/green или число 0-36")
            return
        
        update_balance(message.from_user.id, -bet)
        await roulette_anim(message, bet, parsed[0], parsed[1])
    except:
        await message.answer("❌ /roulette [цвет/число] [ставка]")

@dp.callback_query(lambda c: c.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    print("🎰 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
