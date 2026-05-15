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
# Красные числа в рулетке
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

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

def parse_roulette_bet(bet_str):
    """Парсит ставку: цвет или число"""
    bet_str = bet_str.lower().strip()
    
    # Цвета
    if bet_str in ['black', 'red', 'green']:
        return ('color', bet_str)
    
    # Число
    try:
        num = int(bet_str)
        if 0 <= num <= 36:
            return ('number', num)
    except:
        pass
    
    return None

def check_roulette_win(final_color, bet_type, bet_value):
    """Проверяет выигрыш и возвращает (win, multiplier)"""
    
    if bet_type == 'color':
        if bet_value == 'green':
            return (final_color == 'green', 35)
        else:
            return (final_color == bet_value, 2)
    
    elif bet_type == 'number':
        num = bet_value
        
        # Зеро (0) - всегда зелёное
        if num == 0:
            return (final_color == 'green', 35)
        
        # Проверяем цвет числа
        if num in RED_NUMBERS:
            return (final_color == 'red', 35)
        elif num in BLACK_NUMBERS:
            return (final_color == 'black', 35)
    
    return (False, 0)

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎰 КАЗИНО ДОЛИНА\n\n"
        "🎲 /mines [мин] [ставка] - Мины (3-24 мин, от 10₽)\n"
        "🎡 /roulette [цвет/число] [ставка] - Рулетка (от 500₽)\n"
        "   Пример: /roulette red 1000 или /roulette 7 500\n"
        "🃏 /joker [ставка] - Джокер (от 100₽)\n"
        "💰 /bonus - Бонус 10000₽ (раз в день)\n"
        "💳 /balance - Баланс\n"
        "📤 /pay [сумма] - ответом на сообщение\n"
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
            await message.answer("❌ Бонус можно получить раз в 24 часа!")
            return
    
    update_balance(user_id, BONUS_AMOUNT)
    cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', (datetime.now().isoformat(), user_id))
    conn.commit()
    
    await message.answer(f"🎁 +{BONUS_AMOUNT}₽! Баланс: {get_balance(user_id):.2f}₽")

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
    if get_balance(sender) < amount:
        await message.answer(f"❌ Недостаточно средств! Баланс: {get_balance(sender):.2f}₽")
        return
    
    update_balance(sender, -amount)
    update_balance(receiver, amount)
    await message.answer(f"✅ Переведено {amount:.2f}₽ пользователю {receiver}")
    await bot.send_message(receiver, f"💰 Вы получили {amount:.2f}₽ от {sender}")

@dp.message(Command("money"))
async def admin_money(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3 or parts[1] != ADMIN_CODE:
        return
    try:
        amount = float(parts[2])
        update_balance(message.from_user.id, amount)
        await message.answer(f"✅ Выдано {amount:.2f}₽")
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
        
        positions = [(i,j) for i in range(5) for j in range(5)]
        for i,j in random.sample(positions, mines):
            self.field[i][j] = 1
    
    def get_multiplier(self, opened):
        if opened == 0:
            return 1.0
        safe = 25 - self.mines
        prob = 1.0
        for i in range(opened):
            prob *= (safe - i) / (25 - i)
        return (1/prob) * 0.92
    
    def reveal(self, row, col):
        if not self.active or self.revealed[row][col]:
            return None
        self.revealed[row][col] = True
        opened = sum(sum(r) for r in self.revealed)
        if self.field[row][col] == 1:
            self.active = False
            return ('lose', opened)
        return ('win', opened, self.get_multiplier(opened))
    
    def cashout(self):
        if not self.active:
            return 0
        opened = sum(sum(r) for r in self.revealed)
        if opened == 0:
            return 0
        win = self.bet * self.get_multiplier(opened)
        update_balance(self.uid, win - self.bet)
        self.active = False
        return win
    
    def get_final_board(self):
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
            await message.answer("❌ Количество мин от 3 до 24")
            return
        if bet < 10:
            await message.answer("❌ Минимальная ставка 10₽")
            return
        if get_balance(message.from_user.id) < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {get_balance(message.from_user.id):.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        game = MinesGame(message.from_user.id, bet, mines)
        mines_games[message.from_user.id] = game
        
        kb = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                kb.button(text="❓", callback_data=f"mine_{i}_{j}")
            kb.adjust(5)
        kb.row(InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel"))
        
        await message.answer(
            f"💣 МИНЫ | Ставка: {bet:.2f}₽ | Мин: {mines}\n"
            f"Множитель: x{game.get_multiplier(0):.2f}\n\n"
            f"Открывай клетки!",
            reply_markup=kb.as_markup()
        )
    except:
        await message.answer("❌ Использование: /mines [3-24] [ставка]")

@dp.callback_query(lambda c: c.data.startswith('mine_'))
async def mines_callback(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.active:
        await callback.answer("Игра не активна!")
        return
    
    action = callback.data.split('_')
    
    if action[1] == 'cancel':
        update_balance(callback.from_user.id, game.bet)
        del mines_games[callback.from_user.id]
        await callback.message.edit_text("❌ Игра отменена. Ставка возвращена.")
        await callback.answer()
        return
    
    if action[1] == 'cashout':
        win = game.cashout()
        board = game.get_final_board()
        await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    row, col = int(action[1]), int(action[2])
    res = game.reveal(row, col)
    
    if res[0] == 'lose':
        board = game.get_final_board()
        await callback.message.edit_text(f"💥 Ты наступил на мину! Проигрыш {game.bet:.2f}₽\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    opened, mult = res[1], res[2]
    kb = InlineKeyboardBuilder()
    for i in range(5):
        for j in range(5):
            if game.revealed[i][j]:
                kb.button(text="⭐" if game.field[i][j]==0 else "💣", callback_data=f"mine_{i}_{j}")
            else:
                kb.button(text="❓", callback_data=f"mine_{i}_{j}")
        kb.adjust(5)
    
    if opened == 25 - game.mines:
        win = game.cashout()
        board = game.get_final_board()
        await callback.message.edit_text(f"🎉 ПОБЕДА! Ты выиграл {win:.2f}₽ (x{mult:.2f})\n\nГде были мины:", reply_markup=board)
        del mines_games[callback.from_user.id]
    else:
        kb.row(
            InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="mine_cashout"),
            InlineKeyboardButton(text="❌ ОТМЕНА", callback_data="mine_cancel")
        )
        await callback.message.edit_text(
            f"✅ Открыто клеток: {opened}\n"
            f"📈 Множитель: x{mult:.2f}\n"
            f"💰 Возможный выигрыш: {game.bet * mult:.2f}₽",
            reply_markup=kb.as_markup()
        )
    await callback.answer()

# ========== ДЖОКЕР ==========
class JokerGame:
    def __init__(self, uid, bet):
        self.uid = uid
        self.bet = bet
        self.rows = []
        self.add_row()
    
    def add_row(self):
        row = []
        for _ in range(3):
            if random.random() < 0.333:
                row.append(('🃏', False))
            else:
                row.append(('🎴', False))
        self.rows.append(row)
    
    def reveal(self, r, c):
        if r >= len(self.rows):
            return None
        card, rev = self.rows[r][c]
        if rev:
            return None
        self.rows[r][c] = (card, True)
        if card == '🃏':
            self.add_row()
            return 'win'
        return 'lose'
    
    def get_total_win(self):
        jokers = 0
        for row in self.rows:
            for card, rev in row:
                if rev and card == '🃏':
                    jokers += 1
        if jokers == 0:
            return 0
        total = 1.0
        for i in range(jokers):
            total += 0.3 + i * 0.1
        return self.bet * total
    
    def cashout(self):
        win = self.get_total_win()
        if win > 0:
            update_balance(self.uid, win - self.bet)
        return win

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        if bet < 100:
            await message.answer("❌ Минимальная ставка 100₽")
            return
        if get_balance(message.from_user.id) < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {get_balance(message.from_user.id):.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        await show_joker_board(message, game, is_edit=False)
    except:
        await message.answer("❌ Использование: /joker [ставка от 100]")

async def show_joker_board(msg, game, is_edit=True, callback=None):
    kb = InlineKeyboardBuilder()
    for r, row in enumerate(game.rows):
        for c, (card, rev) in enumerate(row):
            kb.button(text=card if rev else "❓", callback_data=f"joker_{r}_{c}")
        kb.adjust(3)
    kb.row(InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="joker_cashout"))
    
    jokers = 0
    for row in game.rows:
        for card, rev in row:
            if rev and card == '🃏':
                jokers += 1
    
    text = f"🃏 ДЖОКЕР | Ставка: {game.bet:.2f}₽\n\n"
    if jokers > 0:
        mult = 1.0
        for i in range(jokers):
            mult += 0.3 + i * 0.1
        text += f"✅ Найдено джокеров: {jokers}\n"
        text += f"📈 Множитель: x{mult:.2f}\n"
        text += f"💰 Выигрыш: {game.bet * mult:.2f}₽"
    else:
        text += "❓ Ищи джокеров!\nКаждый даёт +30% +10% за каждого предыдущего"
    
    if callback:
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    elif is_edit:
        await msg.edit_text(text, reply_markup=kb.as_markup())
    else:
        await msg.answer(text, reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith('joker_'))
async def joker_callback(callback: types.CallbackQuery):
    game = joker_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Игра не активна!")
        return
    
    if callback.data == "joker_cashout":
        win = game.cashout()
        if win > 0:
            await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!")
        else:
            await callback.message.edit_text(f"❌ Ты не нашёл ни одного джокера! Проигрыш {game.bet:.2f}₽")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    
    _, r, c = callback.data.split('_')
    res = game.reveal(int(r), int(c))
    
    if res is None:
        await callback.answer("Эта карта уже открыта!")
        return
    
    if res == 'lose':
        await callback.message.edit_text(f"😔 Обычная карта! Проигрыш {game.bet:.2f}₽")
        del joker_games[callback.from_user.id]
    else:
        await show_joker_board(callback.message, game, is_edit=True, callback=callback)
        await callback.answer("🎉 ДЖОКЕР! Добавлен новый ряд!")
    await callback.answer()

# ========== РУЛЕТКА С АНИМАЦИЕЙ ==========
async def roulette_animation(message, bet, bet_type, bet_value):
    # Генерируем кадры анимации
    frames = []
    for _ in range(40):
        frames.append(get_random_line())
    
    final_color = roulette_spin()
    
    # Отправляем начальное сообщение
    msg = await message.answer(
        f"🎡 КРУТИМ РУЛЕТКУ\n\n"
        f"==========|==========\n"
        f"{frames[0]}\n"
        f"==========|=========="
    )
    
    # Анимация с замедлением
    for i, frame in enumerate(frames):
        if i < 12:
            delay = 0.08
        elif i < 22:
            delay = 0.12
        elif i < 28:
            delay = 0.2
        elif i < 34:
            delay = 0.35
        else:
            delay = 0.55
        
        await msg.edit_text(
            f"🎡 КРУТИМ РУЛЕТКУ\n\n"
            f"==========|==========\n"
            f"{frame}\n"
            f"==========|=========="
        )
        await asyncio.sleep(delay)
    
    # Финальный результат
    final_line = get_random_line()
    emoji = '🔴' if final_color == 'red' else '⚫️' if final_color == 'black' else '🟢'
    
    await msg.edit_text(
        f"🎡 СТОП!\n\n"
        f"==========|==========\n"
        f"{final_line}\n"
        f"==========|==========\n\n"
        f"🎲 ВЫПАЛО: {emoji} {final_color.upper()}"
    )
    
    await asyncio.sleep(1)
    
    # Проверяем выигрыш
    is_win, multiplier = check_roulette_win(final_color, bet_type, bet_value)
    
    if is_win:
        win_amount = bet * multiplier
        update_balance(message.from_user.id, win_amount - bet)
        await message.answer(
            f"🎉 **ПОБЕДА!** 🎉\n\n"
            f"Ставка: {bet:.2f}₽\n"
            f"Выигрыш: {win_amount:.2f}₽\n"
            f"Множитель: x{multiplier}\n\n"
            f"💰 Новый баланс: {get_balance(message.from_user.id):.2f}₽",
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"❌ **ПРОИГРЫШ** ❌\n\n"
            f"Ставка: {bet:.2f}₽\n"
            f"💰 Баланс: {get_balance(message.from_user.id):.2f}₽",
            parse_mode="Markdown"
        )

@dp.message(Command("roulette"))
async def cmd_roulette(message: types.Message):
    try:
        parts = message.text.split()
        if len(parts) < 3:
            await message.answer(
                "❌ **Примеры:**\n"
                "/roulette red 1000\n"
                "/roulette black 500\n"
                "/roulette green 200\n"
                "/roulette 7 1000\n"
                "/roulette 0 500\n\n"
                "💰 Минимальная ставка: 500₽"
            )
            return
        
        bet = float(parts[-1])
        if bet < 500:
            await message.answer("❌ Минимальная ставка 500₽")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        # Собираем ставку (все части кроме последней - суммы)
        bet_str = ' '.join(parts[1:-1])
        parsed = parse_roulette_bet(bet_str)
        
        if not parsed:
            await message.answer("❌ Неверная ставка! Пример: /roulette red 1000 или /roulette 7 500")
            return
        
        bet_type, bet_value = parsed
        
        # Списываем ставку
        update_balance(message.from_user.id, -bet)
        
        # Запускаем анимацию
        await roulette_animation(message, bet, bet_type, bet_value)
        
    except ValueError:
        await message.answer("❌ Ставка должна быть числом! Пример: /roulette red 1000")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")

@dp.callback_query(lambda c: c.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    print("🎰 КАЗИНО БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
