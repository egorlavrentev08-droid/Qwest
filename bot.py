import asyncio
import random
import sqlite3
import threading
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

# ========== БАЗА ДАННЫХ ==========
db_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect('casino_bot.db', timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

with get_db_connection() as conn:
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

def get_balance(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                return result[0]
            cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, 0))
            conn.commit()
            return 0

def update_balance(user_id, amount):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                new_balance = result[0] + amount
                cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
            else:
                new_balance = amount
                cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, amount))
            conn.commit()
            return new_balance

def set_bonus_time(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?', 
                          (datetime.now().isoformat(), user_id))
            conn.commit()

def get_bonus_time(user_id):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

def add_roulette_log(user_id, result, win_amount):
    with db_lock:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO roulette_history (user_id, result, win_amount, timestamp) VALUES (?, ?, ?, ?)',
                          (user_id, result, win_amount, datetime.now().isoformat()))
            conn.commit()

# ========== РУЛЕТКА ==========
RED_NUMBERS = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

def roulette_spin():
    r = random.random()
    if r < 0.485:
        return 'black'
    elif r < 0.97:
        return 'red'
    return 'green'

def generate_roulette_line():
    length = random.choice([8, 9])
    start_color = random.choice(['🟥', '⬛'])
    colors = []
    for i in range(length):
        if i % 2 == 0:
            colors.append(start_color)
        else:
            colors.append('🟥' if start_color == '⬛' else '⬛')
    
    green_pos = random.randint(0, length - 1)
    colors[green_pos] = '🟩'
    
    line = ''.join(colors)
    
    if random.choice([True, False]):
        line = '  ' + line
    
    return line

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

def check_roulette_win(final_color, bet_type, bet_value):
    if bet_type == 'color':
        if bet_value == 'green':
            return (final_color == 'green', 35)
        return (final_color == bet_value, 2)
    elif bet_type == 'number':
        num = bet_value
        if num == 0:
            return (final_color == 'green', 35)
        if num in RED_NUMBERS:
            return (final_color == 'red', 35)
        elif num in BLACK_NUMBERS:
            return (final_color == 'black', 35)
    return (False, 0)

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(
        "🎰 КАЗИНО ДОЛИНА\n\n"
        "🎲 /mines [мин] [ставка] - Мины (3-24 мин, от 10₽)\n"
        "🎡 /roulette [цвет/число] [ставка] - Рулетка (от 10₽)\n"
        "   Пример: /roulette red 1000 или /roulette 7 500\n"
        "🃏 /joker [ставка] - Джокер (от 10₽)\n"
        "💰 /bonus - Бонус 10000₽ (раз в день)\n"
        "💳 /balance - Баланс\n"
        "📤 /pay [сумма] - ответом на сообщение\n"
        f"\n💰 Баланс: {balance:.2f}₽"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(f"💰 Баланс: {balance:.2f}₽")

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
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
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
        await message.answer("❌ Использование: /mines [3-24] [ставка от 10]")

@dp.callback_query(lambda c: c.data.startswith('mine_'))
async def mines_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    game = mines_games.get(user_id)
    if not game:
        await callback.answer("❌ У тебя нет активной игры!", show_alert=True)
        return
    
    if not game.active:
        await callback.answer("❌ Эта игра уже завершена!", show_alert=True)
        return
    
    action = callback.data.split('_')
    
    if action[1] == 'cancel':
        update_balance(user_id, game.bet)
        del mines_games[user_id]
        await callback.message.edit_text("❌ Игра отменена. Ставка возвращена.")
        await callback.answer()
        return
    
    if action[1] == 'cashout':
        win = game.cashout()
        board = game.get_final_board()
        await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!\n\nГде были мины:", reply_markup=board)
        del mines_games[user_id]
        await callback.answer()
        return
    
    row, col = int(action[1]), int(action[2])
    res = game.reveal(row, col)
    
    if res[0] == 'lose':
        board = game.get_final_board()
        await callback.message.edit_text(f"💥 Ты наступил на мину! Проигрыш {game.bet:.2f}₽\n\nГде были мины:", reply_markup=board)
        del mines_games[user_id]
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
        del mines_games[user_id]
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

# ========== ДЖОКЕР - ИСПРАВЛЕННЫЙ ==========
class JokerGame:
    def __init__(self, uid, bet):
        self.uid = uid
        self.bet = bet
        self.rows = []
        self.joker_positions = []  # Сохраняем где были джокеры
        self.found_jokers = 0      # Сколько джокеров найдено
        self.active = True
        self.add_first_row()
    
    def add_first_row(self):
        """Создаёт первый ряд: ровно 1 джокер и 2 обычные карты"""
        cards = ['🎴', '🎴', '🎴']
        # Выбираем случайную позицию для джокера
        joker_pos = random.randint(0, 2)
        cards[joker_pos] = '🃏'
        
        self.rows = [cards]
        self.joker_positions = [[False, False, False]]
        self.joker_positions[0][joker_pos] = True
    
    def add_row(self):
        """Добавляет новый ряд (после нахождения джокера): ровно 1 джокер"""
        cards = ['🎴', '🎴', '🎴']
        joker_pos = random.randint(0, 2)
        cards[joker_pos] = '🃏'
        
        self.rows.append(cards)
        joker_row = [False, False, False]
        joker_row[joker_pos] = True
        self.joker_positions.append(joker_row)
    
    def reveal(self, r, c):
        """Открывает карту"""
        if not self.active:
            return None
        if r >= len(self.rows):
            return None
        
        card = self.rows[r][c]
        if card == '💎' or card == '❌':
            return None  # Уже открыто
        
        if card == '🃏':
            # Нашли джокера
            self.rows[r][c] = '💎'
            self.found_jokers += 1
            self.add_row()  # Добавляем новый ряд
            return 'win'
        else:
            # Обычная карта - проигрыш
            self.rows[r][c] = '❌'
            self.active = False
            return 'lose'
    
    def get_total_win(self):
        """Рассчитывает выигрыш"""
        if self.found_jokers == 0:
            return 0
        total = 1.0
        for i in range(self.found_jokers):
            total += 0.3 + i * 0.1
        return self.bet * total
    
    def cashout(self):
        """Забирает выигрыш"""
        win = self.get_total_win()
        if win > 0:
            update_balance(self.uid, win - self.bet)
        self.active = False
        return win
    
    def get_final_board(self):
        """Показывает все карты в конце игры"""
        kb = InlineKeyboardBuilder()
        for r, row in enumerate(self.rows):
            for c, card in enumerate(row):
                if card == '🃏':
                    text = "💎"
                elif card == '🎴':
                    text = "❌"
                else:
                    text = card
                kb.button(text=text, callback_data="noop")
            kb.adjust(3)
        return kb.as_markup()
    
    def get_current_board(self):
        """Показывает текущее состояние игры"""
        kb = InlineKeyboardBuilder()
        for r, row in enumerate(self.rows):
            for c, card in enumerate(row):
                if card == '💎' or card == '❌':
                    text = card
                else:
                    text = "❓"
                kb.button(text=text, callback_data=f"joker_{r}_{c}")
            kb.adjust(3)
        kb.row(InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="joker_cashout"))
        return kb.as_markup()

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        if bet < 10:
            await message.answer("❌ Минимальная ставка 10₽")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        
        # Показываем игровое поле
        text = f"🃏 ДЖОКЕР | Ставка: {bet:.2f}₽\n\n"
        text += "❓ Ищи джокера! В каждом ряду 1 джокер.\n"
        text += "Каждый найденный джокер даёт +30% + 10% за каждого предыдущего"
        
        await message.answer(text, reply_markup=game.get_current_board())
    except:
        await message.answer("❌ Использование: /joker [ставка от 10]")

@dp.callback_query(lambda c: c.data.startswith('joker_'))
async def joker_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    game = joker_games.get(user_id)
    if not game:
        await callback.answer("❌ У тебя нет активной игры!", show_alert=True)
        return
    
    if not game.active:
        await callback.answer("❌ Эта игра уже завершена!", show_alert=True)
        return
    
    if callback.data == "joker_cashout":
        win = game.cashout()
        if win > 0:
            await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!")
        else:
            final_board = game.get_final_board()
            await callback.message.edit_text(
                f"❌ Ты не нашёл ни одного джокера! Проигрыш {game.bet:.2f}₽\n\n"
                f"**Вот где были карты:**",
                reply_markup=final_board
            )
        del joker_games[user_id]
        await callback.answer()
        return
    
    _, r, c = callback.data.split('_')
    res = game.reveal(int(r), int(c))
    
    if res is None:
        await callback.answer("Эта карта уже открыта!")
        return
    
    if res == 'lose':
        final_board = game.get_final_board()
        await callback.message.edit_text(
            f"😔 Обычная карта! Проигрыш {game.bet:.2f}₽\n\n"
            f"**Вот где были карты:**",
            reply_markup=final_board
        )
        del joker_games[user_id]
    else:
        # Показываем обновлённое поле
        jokers = game.found_jokers
        mult = 1.0
        for i in range(jokers):
            mult += 0.3 + i * 0.1
        
        text = f"🃏 ДЖОКЕР | Ставка: {game.bet:.2f}₽\n\n"
        text += f"✅ Найдено джокеров: {jokers}\n"
        text += f"📈 Множитель: x{mult:.2f}\n"
        text += f"💰 Выигрыш: {game.bet * mult:.2f}₽\n\n"
        text += "🎉 Ты нашёл джокера! Добавлен новый ряд!"
        
        await callback.message.edit_text(text, reply_markup=game.get_current_board())
        await callback.answer("🎉 ДЖОКЕР!")
    await callback.answer()

# ========== РУЛЕТКА ==========
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
    """
    Возвращает (кадр, победитель)
    Зелёный (кадр 5) с вероятностью 1/37
    Остальные 9 кадров с равной вероятностью
    """
    r = random.random()
    
    # Зелёный с вероятностью 1/37 ≈ 0.027
    if r < 1/37:
        frame, winner = ROULETTE_FRAMES[4]  # 5-й кадр (индекс 4)
        return frame, winner
    
    # Остальные 9 кадров с равной вероятностью
    # 9 кадров распределены на оставшуюся вероятность (36/37)
    else:
        # Выбираем случайный из 9 кадров (все кроме 5-го)
        other_frames = ROULETTE_FRAMES[:4] + ROULETTE_FRAMES[5:]
        frame, winner = random.choice(other_frames)
        return frame, winner

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
    """Проверяет выигрыш по реальному победителю"""
    if bet_type == 'color':
        if bet_value == 'green':
            return (winner_color == 'green', 35)
        return (winner_color == bet_value, 2)
    elif bet_type == 'number':
        num = bet_value
        if num == 0:
            return (winner_color == 'green', 35)
        if num in RED_NUMBERS:
            return (winner_color == 'red', 35)
        elif num in BLACK_NUMBERS:
            return (winner_color == 'black', 35)
    return (False, 0)

def generate_animation_frames(count=8):
    """Генерирует случайные кадры для анимации (не влияют на результат)"""
    frames = []
    for _ in range(count):
        # Случайная линия 8-9 символов
        length = random.choice([8, 9])
        colors = []
        start = random.choice(['🟥', '⬛'])
        for i in range(length):
            if i % 2 == 0:
                colors.append(start)
            else:
                colors.append('🟥' if start == '⬛' else '⬛')
        
        # Иногда добавляем зелёный для красоты (не влияет на результат)
        if random.random() < 0.3:
            pos = random.randint(0, length-1)
            colors[pos] = '🟩'
        
        line = ''.join(colors)
        if random.choice([True, False]):
            line = '  ' + line
        frames.append(line)
    return frames

async def roulette_animation(message, bet, bet_type, bet_value):
    # Получаем финальный результат
    final_frame, winner_color = get_roulette_result()
    
    # Генерируем анимационные кадры
    anim_frames = generate_animation_frames(8)
    
    msg = await message.answer(
        f"🎡 КРУТИМ РУЛЕТКУ\n\n"
        f"==========|==========\n"
        f"{anim_frames[0]}\n"
        f"==========|=========="
    )
    
    # Анимация (8 кадров, 1 в секунду)
    last_text = ""
    for i in range(1, 8):
        await asyncio.sleep(1.0)
        
        bar = "=" * 10
        new_text = (
            f"🎡 КРУТИМ РУЛЕТКУ\n\n"
            f"{bar}|{bar}\n"
            f"{anim_frames[i]}\n"
            f"{bar}|{bar}"
        )
        
        if new_text != last_text:
            try:
                await msg.edit_text(new_text)
                last_text = new_text
            except:
                pass
    
    # Показываем финальный кадр
    emoji = '🔴' if winner_color == 'red' else '⚫️' if winner_color == 'black' else '🟢'
    color_text = winner_color.upper()
    
    final_display = (
        f"🎡 СТОП!\n\n"
        f"==========|==========\n"
        f"{final_frame}\n"
        f"==========|==========\n\n"
        f"🎲 ВЫПАЛО: {emoji} {color_text}"
    )
    
    try:
        await msg.edit_text(final_display)
    except:
        pass
    
    await asyncio.sleep(1)
    
    # Проверяем выигрыш
    is_win, multiplier = check_roulette_win(winner_color, bet_type, bet_value)
    
    if is_win:
        win_amount = bet * multiplier
        new_balance = update_balance(message.from_user.id, win_amount - bet)
        add_roulette_log(message.from_user.id, winner_color, win_amount)
        await message.answer(
            f"🎉 **ПОБЕДА!** 🎉\n\n"
            f"Ставка: {bet:.2f}₽\n"
            f"Выигрыш: {win_amount:.2f}₽\n"
            f"Множитель: x{multiplier}\n\n"
            f"💰 Новый баланс: {new_balance:.2f}₽",
            parse_mode="Markdown"
        )
    else:
        current_balance = get_balance(message.from_user.id)
        await message.answer(
            f"❌ **ПРОИГРЫШ** ❌\n\n"
            f"Ставка: {bet:.2f}₽\n"
            f"💰 Баланс: {current_balance:.2f}₽",
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
                "💰 Минимальная ставка: 10₽"
            )
            return
        
        bet = float(parts[-1])
        if bet < 10:
            await message.answer("❌ Минимальная ставка 10₽")
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
        
    except ValueError:
        await message.answer("❌ Ставка должна быть числом!")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")
    

# ========== ЗАПУСК ==========
async def main():
    print("🎰 КАЗИНО БОТ ЗАПУЩЕН!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
