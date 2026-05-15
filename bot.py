import asyncio
import random
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8773046663:AAFFIQLaymzRJCP_VkIGI2hMudOAUFbroMw"
ADMIN_CODE = "14916253649"
BONUS_AMOUNT = 10000

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# БД
conn = sqlite3.connect('casino_bot.db')
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

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def get_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        cursor.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, 0))
        conn.commit()
        return 0

def update_balance(user_id, amount):
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()

def roulette_spin():
    rand = random.random()
    if rand < 0.485:
        return 'black'
    elif rand < 0.97:
        return 'red'
    else:
        return 'green'

def add_roulette_log(user_id, result, win_amount):
    cursor.execute('INSERT INTO roulette_history (user_id, result, win_amount, timestamp) VALUES (?, ?, ?, ?)',
                   (user_id, result, win_amount, datetime.now().isoformat()))
    conn.commit()

def parse_roulette_bet(bet_str):
    """Парсит ставку: число, цвет или диапазон"""
    bet_str = bet_str.lower().strip()
    
    # Цвета
    if bet_str in ['black', 'red', 'green']:
        return ('color', bet_str)
    
    # Одно число
    try:
        num = int(bet_str)
        if 0 <= num <= 36:
            return ('number', num)
    except:
        pass
    
    # Диапазон (например 4-9)
    if '-' in bet_str:
        try:
            parts = bet_str.split('-')
            start = int(parts[0])
            end = int(parts[1])
            if 0 <= start <= 36 and 0 <= end <= 36 and start < end:
                return ('range', (start, end))
        except:
            pass
    
    return None

def check_roulette_win(final, bet_type, bet_value):
    """Проверяет выигрыш по типу ставки"""
    # Цвета
    if bet_type == 'color':
        if bet_value == 'green':
            return final == 'green', 35
        else:
            return final == bet_value, 2
    
    # Одно число
    elif bet_type == 'number':
        # Конвертируем цвет в число для проверки
        number_colors = {}
        for i in range(1, 11):
            number_colors[i] = 'black' if i % 2 == 0 else 'red'
        for i in range(11, 19):
            number_colors[i] = 'red' if i % 2 == 0 else 'black'
        for i in range(19, 29):
            number_colors[i] = 'black' if i % 2 == 0 else 'red'
        for i in range(29, 37):
            number_colors[i] = 'red' if i % 2 == 0 else 'black'
        number_colors[0] = 'green'
        
        # В реальной рулетке число 0 всегда зелёное
        if bet_value == 0:
            return final == 'green', 35
        else:
            return (final == number_colors[bet_value]), 35
    
    # Диапазон
    elif bet_type == 'range':
        start, end = bet_value
        # Для простоты считаем выигрыш если число в диапазоне (упрощённо)
        # В реальной рулетке диапазоны имеют свой коэффициент
        return False, 2  # Заглушка, можно расширить
    
    return False, 0

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎰 Добро пожаловать в Казино Долина!\n\n"
        "🎲 /mines [мины] [ставка] - Мины (3-24 мины, ставка от 10)\n"
        "🎡 /roulette [цвет/число/диапазон] [ставка] - Рулетка (ставка от 500)\n"
        "   Примеры: /roulette red 1000, /roulette 7 500, /roulette 4-9 1000\n"
        "🃏 /joker [ставка] - Джокер (ставка от 100)\n"
        "💰 /bonus - Бонус 10000₽\n"
        "💳 /balance - Баланс\n"
        "📤 /pay [сумма] (ответ на сообщение) - Перевод\n"
        "📊 /log - Последние 10 выигрышей\n\n"
        f"Баланс: {get_balance(message.from_user.id):.2f}₽"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    await message.answer(f"💰 Баланс: {get_balance(message.from_user.id):.2f}₽")

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
    last_bonus = cursor.fetchone()[0]
    if last_bonus and (datetime.now() - datetime.fromisoformat(last_bonus)).days < 1:
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
            await message.answer("❌ Сумма должна быть положительной!")
            return
    except:
        await message.answer("❌ Использование: /pay [сумма] (ответ на сообщение получателя)")
        return
    
    sender_id = message.from_user.id
    receiver_id = message.reply_to_message.from_user.id
    
    if receiver_id == bot.id:
        await message.answer("❌ Нельзя переводить деньги боту!")
        return
    
    if sender_id == receiver_id:
        await message.answer("❌ Нельзя перевести самому себе!")
        return
    
    sender_balance = get_balance(sender_id)
    if sender_balance < amount:
        await message.answer(f"❌ Недостаточно средств! Баланс: {sender_balance:.2f}₽")
        return
    
    update_balance(sender_id, -amount)
    update_balance(receiver_id, amount)
    await message.answer(f"✅ Переведено {amount:.2f}₽ пользователю {receiver_id}")
    await bot.send_message(receiver_id, f"💰 Ты получил {amount:.2f}₽ от {sender_id}")

@dp.message(Command("log"))
async def cmd_log(message: types.Message):
    cursor.execute('''
        SELECT user_id, result, win_amount, timestamp 
        FROM roulette_history 
        WHERE win_amount > 0 
        ORDER BY timestamp DESC 
        LIMIT 10
    ''')
    logs = cursor.fetchall()
    
    if not logs:
        await message.answer("📊 Нет записей о выигрышах в рулетке")
        return
    
    log_text = "📊 **Последние 10 выигрышей в рулетке:**\n\n"
    for i, (user_id, result, win_amount, timestamp) in enumerate(logs, 1):
        emoji = '🔴' if result == 'red' else '⚫️' if result == 'black' else '🟢'
        log_text += f"{i}. Пользователь: `{user_id}`\n   {emoji} {result} | +{win_amount:.2f}₽\n   🕐 {timestamp[:19]}\n\n"
    
    await message.answer(log_text, parse_mode="Markdown")

@dp.message(Command("money"))
async def admin_money(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        return
    
    code = parts[1]
    if code != ADMIN_CODE:
        return
    
    try:
        amount = float(parts[2])
        user_id = message.from_user.id
        update_balance(user_id, amount)
        await message.answer(f"✅ Выдано {amount:.2f}₽")
    except:
        pass

# ========== ИГРА МИНЫ ==========
class MinesGame:
    def __init__(self, user_id, bet, num_mines):
        self.user_id = user_id
        self.bet = bet
        self.num_mines = num_mines
        self.field = [[0]*5 for _ in range(5)]
        self.revealed = [[False]*5 for _ in range(5)]
        self.active = True
        positions = [(i,j) for i in range(5) for j in range(5)]
        for i,j in random.sample(positions, num_mines):
            self.field[i][j] = 1
    
    def get_multiplier(self, revealed):
        if revealed == 0:
            return 1.0
        safe = 25 - self.num_mines
        prob = 1.0
        for i in range(revealed):
            prob *= (safe - i) / (25 - i)
        return (1/prob) * 0.92
    
    def reveal(self, row, col):
        if not self.active or self.revealed[row][col]:
            return None
        self.revealed[row][col] = True
        revealed_count = sum(sum(row) for row in self.revealed)
        if self.field[row][col] == 1:
            self.active = False
            return {'status':'lose', 'revealed': revealed_count}
        else:
            return {'status':'win', 'multiplier':self.get_multiplier(revealed_count), 'revealed':revealed_count}
    
    def cashout(self):
        if not self.active:
            return 0
        revealed = sum(sum(row) for row in self.revealed)
        if revealed == 0:
            return 0
        win = self.bet * self.get_multiplier(revealed)
        update_balance(self.user_id, win - self.bet)
        self.active = False
        return win
    
    def get_final_board(self):
        builder = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                if self.field[i][j] == 1:
                    text = "💣"
                else:
                    text = "⭐"
                builder.button(text=text, callback_data="noop")
            builder.adjust(5)
        return builder.as_markup()

mines_games = {}

@dp.message(Command("mines"))
async def cmd_mines(message: types.Message):
    try:
        parts = message.text.split()
        num_mines = int(parts[1])
        bet = float(parts[2])
        
        if num_mines < 3 or num_mines > 24:
            await message.answer("❌ Количество мин должно быть от 3 до 24")
            return
        if bet < 10:
            await message.answer("❌ Ставка должна быть от 10₽")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        game = MinesGame(message.from_user.id, bet, num_mines)
        mines_games[message.from_user.id] = game
        
        builder = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                builder.button(text="❓", callback_data=f"mine_{i}_{j}")
            builder.adjust(5)
        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel"))
        
        await message.answer(
            f"💣 **Игра Мины**\n"
            f"Ставка: {bet:.2f}₽\n"
            f"Мин: {num_mines}\n"
            f"Множитель: x{game.get_multiplier(0):.2f}\n\n"
            f"Открывай клетки, но не наступи на мину!",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    except:
        await message.answer("❌ Использование: /mines [3-24] [ставка от 10]")

@dp.callback_query(lambda c: c.data.startswith('mine_'))
async def mines_callback(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.active:
        await callback.answer("Игра не активна!")
        return
    
    action = callback.data.split('_')
    
    if len(action) > 1 and action[1] == 'cancel':
        update_balance(callback.from_user.id, game.bet)
        del mines_games[callback.from_user.id]
        await callback.message.edit_text("❌ Игра отменена. Ставка возвращена.")
        await callback.answer()
        return
    
    if len(action) > 1 and action[1] == 'cashout':
        win = game.cashout()
        final_board = game.get_final_board()
        await callback.message.edit_text(
            f"💰 Ты забрал {win:.2f}₽!\n\n"
            f"**Вот где были мины:**",
            reply_markup=final_board,
            parse_mode="Markdown"
        )
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    try:
        row, col = int(action[1]), int(action[2])
    except:
        await callback.answer()
        return
    
    res = game.reveal(row, col)
    
    if res['status'] == 'lose':
        final_board = game.get_final_board()
        await callback.message.edit_text(
            f"💥 **Ты наступил на мину!**\n"
            f"Проигрыш: {game.bet:.2f}₽\n\n"
            f"**Вот где были мины:**",
            reply_markup=final_board,
            parse_mode="Markdown"
        )
        del mines_games[callback.from_user.id]
        await callback.answer()
        return
    
    builder = InlineKeyboardBuilder()
    for i in range(5):
        for j in range(5):
            if game.revealed[i][j]:
                text = "⭐" if game.field[i][j]==0 else "💣"
            else:
                text = "❓"
            builder.button(text=text, callback_data=f"mine_{i}_{j}")
        builder.adjust(5)
    
    if res['revealed'] == 25 - game.num_mines:
        win = game.cashout()
        final_board = game.get_final_board()
        await callback.message.edit_text(
            f"🎉 **ПОБЕДА!**\n"
            f"Ты открыл все безопасные клетки!\n"
            f"Выигрыш: {win:.2f}₽ (x{res['multiplier']:.2f})\n\n"
            f"**Вот где были мины:**",
            reply_markup=final_board,
            parse_mode="Markdown"
        )
        del mines_games[callback.from_user.id]
    else:
        builder.row(
            InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="mine_cashout"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel")
        )
        await callback.message.edit_text(
            f"✅ **Открыто клеток:** {res['revealed']}\n"
            f"📈 **Множитель:** x{res['multiplier']:.2f}\n"
            f"💵 **Возможный выигрыш:** {game.bet * res['multiplier']:.2f}₽\n\n"
            f"Продолжай открывать клетки или забери выигрыш!",
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
    
    await callback.answer()

# ========== ИГРА ДЖОКЕР ==========
class JokerGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.rows = []
        self.add_row()
    
    def add_row(self):
        row = []
        for _ in range(3):
            if random.random() < 0.3333:
                row.append(('🃏', False))
            else:
                row.append(('🎴', False))
        self.rows.append(row)
    
    def reveal(self, row_idx, col_idx):
        if row_idx >= len(self.rows):
            return None
        card, revealed = self.rows[row_idx][col_idx]
        if revealed:
            return None
        self.rows[row_idx][col_idx] = (card, True)
        if card == '🃏':
            self.add_row()
            return {'status':'win'}
        else:
            return {'status':'lose'}
    
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
            update_balance(self.user_id, win - self.bet)
        return win

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        if bet < 100:
            await message.answer("❌ Ставка должна быть от 100₽")
            return
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        update_balance(message.from_user.id, -bet)
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        await show_joker_board(message, message.from_user.id, game, is_edit=False)
    except:
        await message.answer("❌ Использование: /joker [ставка от 100]")

async def show_joker_board(msg, user_id, game, is_edit=True, callback_query=None):
    builder = InlineKeyboardBuilder()
    for ridx, row in enumerate(game.rows):
        for cidx, (card, rev) in enumerate(row):
            text = card if rev else "❓"
            builder.button(text=text, callback_data=f"joker_{ridx}_{cidx}")
        builder.adjust(3)
    builder.row(InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="joker_cashout"))
    
    jokers = 0
    for row in game.rows:
        for card, rev in row:
            if rev and card == '🃏':
                jokers += 1
    
    text = f"🃏 **Игра Джокер**\nСтавка: {game.bet:.2f}₽\n\n"
    if jokers > 0:
        total_mult = 1.0
        for i in range(jokers):
            total_mult += 0.3 + i * 0.1
        text += f"✅ Найдено джокеров: {jokers}\n"
        text += f"📈 Множитель: x{total_mult:.2f}\n"
        text += f"💰 Выигрыш: {game.bet * total_mult:.2f}₽"
    else:
        text += "❓ Ищи джокеров!\nКаждый найденный джокер даёт +30% + 10% за каждого предыдущего"
    
    if is_edit and callback_query:
        await callback_query.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    elif is_edit and not callback_query:
        await msg.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        await msg.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

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
            await callback.message.edit_text("❌ Ты не нашёл ни одного джокера! Проигрыш.")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    
    parts = callback.data.split('_')
    ridx, cidx = int(parts[1]), int(parts[2])
    res = game.reveal(ridx, cidx)
    
    if res is None:
        await callback.answer("Эта карта уже открыта!")
        return
    
    if res['status'] == 'lose':
        await callback.message.edit_text(
            f"😔 **Обычная карта!**\n"
            f"Ты проиграл {game.bet:.2f}₽"
        )
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    else:
        await show_joker_board(callback.message, callback.from_user.id, game, is_edit=True, callback_query=callback)
        await callback.answer("🎉 ДЖОКЕР! Добавлен новый ряд!")

# ========== РУЛЕТКА С КРАСИВОЙ АНИМАЦИЕЙ ==========
def get_random_roulette_line():
    """Генерирует случайную линию рулетки с зелёным в случайном месте"""
    colors = ['⬛', '🟥', '⬛', '🟥', '⬛', '🟥', '⬛', '🟥']
    green_pos = random.randint(0, 7)
    colors[green_pos] = '🟩'
    return ''.join(colors)

async def roulette_animation(message, bet, bet_type, bet_value):
    """Красивая анимация рулетки на 8 секунд"""
    
    # Генерируем последовательность для анимации (40 кадров)
    animation_frames = []
    for _ in range(40):
        animation_frames.append(get_random_roulette_line())
    
    # Финальный результат
    final_color = roulette_spin()
    
    # Отправляем начальное сообщение
    msg = await message.answer(
        f"🎡 КРУТИМ РУЛЕТКУ\n\n"
        f"==========|==========\n"
        f"{animation_frames[0]}\n"
        f"==========|=========="
    )
    
    # Анимация: сначала быстро, потом замедление
    for i, frame in enumerate(animation_frames):
        if i < 15:
            delay = 0.1      # быстро
        elif i < 25:
            delay = 0.15     # средне
        elif i < 32:
            delay = 0.25     # медленно
        elif i < 37:
            delay = 0.4      # очень медленно
        else:
            delay = 0.6      # финальное замедление
        
        await msg.edit_text(
            f"🎡 КРУТИМ РУЛЕТКУ\n\n"
            f"==========|==========\n"
            f"{frame}\n"
            f"==========|=========="
        )
        await asyncio.sleep(delay)
    
    # Финальный результат с указателем
    final_line = get_random_roulette_line()
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
        add_roulette_log(message.from_user.id, final_color, win_amount)
        
        # Красивое сообщение о победе
        await message.answer(
            f"🎉 **ПОБЕДА!** 🎉\n\n"
            f"Ставка: {bet:.2f}₽\n"
            f"Выигрыш: {win_amount:.2f}₽\n"
            f"Множитель: x{multiplier}\n\n"
            f"💰 Новый баланс: {get_balance(message.from_user.id):.2f}₽",
            parse_mode="Markdown"
        )
    else:
        add_roulette_log(message.from_user.id, final_color, 0)
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
                "❌ **Примеры использования:**\n\n"
                "🎨 На цвет:\n/roulette red 1000\n/roulette black 500\n/roulette green 200\n\n"
                "🔢 На число:\n/roulette 7 1000\n/roulette 0 500\n\n"
                "📊 На диапазон:\n/roulette 4-9 1000\n\n"
                "💰 Минимальная ставка: 500₽"
            )
            return
        
        bet = float(parts[-1])
        if bet < 500:
            await message.answer("❌ Минимальная ставка в рулетке - 500₽")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        bet_str = ' '.join(parts[1:-1])
        parsed = parse_roulette_bet(bet_str)
        
        if not parsed:
            await message.answer(
                "❌ Неверный формат ставки!\n\n"
                "Примеры:\n"
                "/roulette red 1000\n"
                "/roulette 7 500\n"
                "/roulette 4-9 1000"
            )
            return
        
        bet_type, bet_value = parsed
        
        # Списываем ставку
        update_balance(message.from_user.id, -bet)
        
        # Запускаем анимацию
        await roulette_animation(message, bet, bet_type, bet_value)
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}\n\nИспользование: /roulette [ставка] [сумма]")

@dp.callback_query(lambda c: c.data == "noop")
async def noop_callback(callback: types.CallbackQuery):
    await callback.answer()

# ========== ЗАПУСК ==========
async def main():
    print("🎰 Казино бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
