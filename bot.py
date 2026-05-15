import asyncio
import random
import sqlite3
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

API_TOKEN = "8773046663:AAFFIQLaymzRJCP_VkIGI2hMudOAUFbroMw"
ADMIN_CODE = "14916253649"
BONUS_AMOUNT = 10000

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация БД
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
        result TEXT,
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

def get_roulette_probability():
    """Вероятность зависит от истории последних 10 спинов"""
    cursor.execute('SELECT result FROM roulette_history ORDER BY timestamp DESC LIMIT 10')
    history = [row[0] for row in cursor.fetchall()]
    
    black_count = history.count('black')
    red_count = history.count('red')
    green_count = history.count('green')
    
    # Базовая вероятность
    prob_black = 0.485
    prob_red = 0.485
    prob_green = 0.03
    
    # Корректировка на основе истории
    if len(history) >= 5:
        if black_count > red_count + 2:
            prob_black -= 0.1
            prob_red += 0.1
        elif red_count > black_count + 2:
            prob_red -= 0.1
            prob_black += 0.1
    
    return prob_black, prob_red, prob_green

def roulette_spin():
    prob_black, prob_red, prob_green = get_roulette_probability()
    
    rand = random.random()
    if rand < prob_black:
        result = 'black'
    elif rand < prob_black + prob_red:
        result = 'red'
    else:
        result = 'green'
    
    cursor.execute('INSERT INTO roulette_history (result, timestamp) VALUES (?, ?)',
                   (result, datetime.now().isoformat()))
    conn.commit()
    return result

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎰 Добро пожаловать в Казино!\n\n"
        "Доступные команды:\n"
        "🎲 /mines [мины] [ставка] - Игра Мины\n"
        "🎡 /roulette [цвет] [ставка] - Рулетка (black/red/green)\n"
        "🃏 /joker [ставка] - Игра Джокер\n"
        "💰 /bonus - Получить бонус 10000₽\n"
        "💳 /balance - Проверить баланс\n"
        "📤 /pay [сумма] (ответ на сообщение) - Перевести деньги\n\n"
        f"Твой баланс: {get_balance(message.from_user.id):.2f}₽"
    )

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    balance = get_balance(message.from_user.id)
    await message.answer(f"💰 Твой баланс: {balance:.2f}₽")

@dp.message(Command("bonus"))
async def cmd_bonus(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT last_bonus FROM users WHERE user_id = ?', (user_id,))
    last_bonus = cursor.fetchone()[0]
    
    if last_bonus and (datetime.now() - datetime.fromisoformat(last_bonus)).days < 1:
        await message.answer("❌ Бонус можно получить раз в 24 часа!")
        return
    
    update_balance(user_id, BONUS_AMOUNT)
    cursor.execute('UPDATE users SET last_bonus = ? WHERE user_id = ?',
                   (datetime.now().isoformat(), user_id))
    conn.commit()
    await message.answer(f"🎁 Ты получил бонус {BONUS_AMOUNT}₽! Баланс: {get_balance(user_id):.2f}₽")

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
    
    if sender_id == receiver_id:
        await message.answer("❌ Нельзя перевести самому себе!")
        return
    
    sender_balance = get_balance(sender_id)
    if sender_balance < amount:
        await message.answer(f"❌ Недостаточно средств! Твой баланс: {sender_balance:.2f}₽")
        return
    
    update_balance(sender_id, -amount)
    update_balance(receiver_id, amount)
    await message.answer(f"✅ Переведено {amount:.2f}₽ пользователю {receiver_id}")
    await bot.send_message(receiver_id, f"💰 Ты получил {amount:.2f}₽ от {sender_id}")

@dp.message(lambda msg: msg.text and msg.text.startswith("дай "))
async def admin_give_money(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❌ Использование: дай [код] [сумма]")
        return
    
    code, amount_str = parts[1], parts[2]
    if code != ADMIN_CODE:
        await message.answer("❌ Неверный код доступа!")
        return
    
    try:
        amount = float(amount_str)
        user_id = message.from_user.id
        update_balance(user_id, amount)
        await message.answer(f"✅ Админ выдал {amount:.2f}₽! Баланс: {get_balance(user_id):.2f}₽")
    except:
        await message.answer("❌ Неверная сумма!")

# ========== ИГРА МИНЫ ==========
class MinesGame:
    def __init__(self, user_id, bet, num_mines):
        self.user_id = user_id
        self.bet = bet
        self.num_mines = num_mines
        self.field = [[0 for _ in range(5)] for _ in range(5)]  # 0 - safe, 1 - mine
        self.revealed = [[False for _ in range(5)] for _ in range(5)]
        self.game_active = True
        self.total_multiplier = 1.0
        
        # Размещаем мины
        positions = [(i, j) for i in range(5) for j in range(5)]
        mine_positions = random.sample(positions, num_mines)
        for i, j in mine_positions:
            self.field[i][j] = 1
    
    def get_multiplier(self, revealed_count):
        """Коэффициент с матожиданием 0.92"""
        safe_cells = 25 - self.num_mines
        if revealed_count == 0:
            return 1.0
        
        prob = 1.0
        for i in range(revealed_count):
            prob *= (safe_cells - i) / (25 - i)
        
        # Корректируем для матожидания 0.92
        base_multiplier = 1 / prob
        return base_multiplier * 0.92
    
    def reveal(self, row, col):
        if not self.game_active or self.revealed[row][col]:
            return None
        
        self.revealed[row][col] = True
        revealed_count = sum(sum(row) for row in self.revealed)
        
        if self.field[row][col] == 1:  # Попал на мину
            self.game_active = False
            return {'status': 'lose', 'multiplier': 0}
        else:
            multiplier = self.get_multiplier(revealed_count)
            return {'status': 'win', 'multiplier': multiplier, 'revealed': revealed_count}
    
    def cashout(self):
        if not self.game_active:
            return 0
        revealed_count = sum(sum(row) for row in self.revealed)
        if revealed_count == 0:
            return 0
        multiplier = self.get_multiplier(revealed_count)
        win_amount = self.bet * multiplier
        update_balance(self.user_id, win_amount - self.bet)
        self.game_active = False
        return win_amount

mines_games = {}

@dp.message(Command("mines"))
async def cmd_mines(message: types.Message):
    try:
        parts = message.text.split()
        num_mines = int(parts[1])
        bet = float(parts[2])
        
        if num_mines < 1 or num_mines > 24:
            await message.answer("❌ Количество мин должно быть от 1 до 24")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        
        game = MinesGame(message.from_user.id, bet, num_mines)
        mines_games[message.from_user.id] = game
        
        # Создаем клавиатуру
        builder = InlineKeyboardBuilder()
        for i in range(5):
            row = []
            for j in range(5):
                builder.button(text="❓", callback_data=f"mine_{i}_{j}")
            builder.adjust(5)
        
        builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel"))
        
        await message.answer(
            f"💣 Игра Мины\nСтавка: {bet:.2f}₽\nМин: {num_mines}\n"
            f"💰 Возможный выигрыш: {game.get_multiplier(0):.2f}x\n\n"
            f"Открывай клетки, но не наступи на мину!",
            reply_markup=builder.as_markup()
        )
    except:
        await message.answer("❌ Использование: /mines [кол-во мин] [ставка]")

@dp.callback_query(lambda c: c.data.startswith('mine_'))
async def mines_callback(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.game_active:
        await callback.answer("Игра не активна!")
        return
    
    action = callback.data.split('_')
    if action[1] == 'cancel':
        update_balance(callback.from_user.id, game.bet)
        del mines_games[callback.from_user.id]
        await callback.message.edit_text("❌ Игра отменена. Ставка возвращена.")
        await callback.answer()
        return
    
    row, col = int(action[1]), int(action[2])
    result = game.reveal(row, col)
    
    if result['status'] == 'lose':
        del mines_games[callback.from_user.id]
        await callback.message.edit_text(f"💥 Ты наступил на мину! Ты проиграл {game.bet:.2f}₽")
    else:
        # Обновляем кнопку
        builder = InlineKeyboardBuilder()
        for i in range(5):
            for j in range(5):
                if game.revealed[i][j]:
                    text = "⭐" if game.field[i][j] == 0 else "💣"
                else:
                    text = "❓"
                builder.button(text=text, callback_data=f"mine_{i}_{j}")
            builder.adjust(5)
        
        if result['revealed'] == 25 - game.num_mines:
            # Все безопасные клетки открыты
            win = game.cashout()
            await callback.message.edit_text(f"🎉 Победа! Ты выиграл {win:.2f}₽ (x{result['multiplier']:.2f})")
            del mines_games[callback.from_user.id]
        else:
            builder.row(
                InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="mine_cashout"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel")
            )
            await callback.message.edit_text(
                f"✅ Открыто клеток: {result['revealed']}\n"
                f"💰 Текущий множитель: x{result['multiplier']:.2f}\n"
                f"💵 Возможный выигрыш: {game.bet * result['multiplier']:.2f}₽",
                reply_markup=builder.as_markup()
            )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data == "mine_cashout")
async def mines_cashout(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.game_active:
        await callback.answer("Игра не активна!")
        return
    
    win = game.cashout()
    await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!")
    del mines_games[callback.from_user.id]
    await callback.answer()

# ========== ИГРА ДЖОКЕР ==========
class JokerGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.cards = ['🎴', '🎴', '🎴']  # Изначально скрыты
        self.is_joker = [False, False, False]
        self.revealed = [False, False, False]
        self.wins = 0
        
        # Размещаем джокера (вероятность 0.333 на каждой позиции)
        for i in range(3):
            if random.random() < 0.333:
                self.is_joker[i] = True
                self.cards[i] = '🃏'
    
    def reveal(self, position):
        if self.revealed[position]:
            return None
        
        self.revealed[position] = True
        
        if self.is_joker[position]:
            multiplier = 1.3 + self.wins * 0.1
            self.wins += 1
            return {'status': 'win', 'multiplier': multiplier, 'is_joker': True}
        else:
            return {'status': 'lose', 'multiplier': 0, 'is_joker': False}
    
    def cashout(self):
        if self.wins == 0:
            return 0
        
        total_multiplier = 1.0
        for i in range(self.wins):
            total_multiplier += 0.3 + i * 0.1
        
        win_amount = self.bet * total_multiplier
        update_balance(self.user_id, win_amount - self.bet)
        return win_amount

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        balance = get_balance(message.from_user.id)
        
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        
        builder = InlineKeyboardBuilder()
        for i in range(3):
            builder.button(text="❓", callback_data=f"joker_{i}")
        builder.adjust(3)
        builder.row(InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="joker_cashout"))
        
        await message.answer(
            f"🃏 Игра Джокер\nСтавка: {bet:.2f}₽\n\n"
            f"Найди джокера! Каждый найденный джокер увеличивает множитель на 10%",
            reply_markup=builder.as_markup()
        )
    except:
        await message.answer("❌ Использование: /joker [ставка]")

@dp.callback_query(lambda c: c.data.startswith('joker_'))
async def joker_callback(callback: types.CallbackQuery):
    game = joker_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Игра не активна!")
        return
    
    if callback.data == "joker_cashout":
        win = game.cashout()
        await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    
    pos = int(callback.data.split('_')[1])
    result = game.reveal(pos)
    
    # Обновляем кнопки
    builder = InlineKeyboardBuilder()
    for i in range(3):
        if game.revealed[i]:
            text = game.cards[i]
        else:
            text = "❓"
        builder.button(text=text, callback_data=f"joker_{i}")
    builder.adjust(3)
    
    if result['status'] == 'lose':
        builder.row(InlineKeyboardButton(text="🔄 Попробовать ещё", callback_data="joker_restart"))
        await callback.message.edit_text(
            f"😔 Ты проиграл! Это была обычная карта.\n"
            f"Ставка: {game.bet:.2f}₽ проиграна",
            reply_markup=builder.as_markup()
        )
        del joker_games[callback.from_user.id]
    else:
        if all(game.revealed):
            win = game.cashout()
            await callback.message.edit_text(
                f"🎉 ПОБЕДА! Ты нашел {game.wins} джокеров!\n"
                f"💰 Выигрыш: {win:.2f}₽",
                reply_markup=builder.as_markup()
            )
            del joker_games[callback.from_user.id]
        else:
            builder.row(InlineKeyboardButton(text="💰 Забрать выигрыш", callback_data="joker_cashout"))
            await callback.message.edit_text(
                f"✅ Найден джокер! (x{result['multiplier']:.2f})\n"
                f"Найдено джокеров: {game.wins}\n"
                f"💰 Текущий выигрыш: {game.bet * (1.3 + (game.wins-1)*0.1):.2f}₽",
                reply_markup=builder.as_markup()
            )
    
    await callback.answer()

@dp.callback_query(lambda c: c.data == "joker_restart")
async def joker_restart(callback: types.CallbackQuery):
    await cmd_joker(callback.message)
    await callback.answer()

# ========== РУЛЕТКА ==========
@dp.message(Command("roulette"))
async def cmd_roulette(message: types.Message):
    try:
        parts = message.text.lower().split()
        color = parts[1]
        bet = float(parts[2])
        
        if color not in ['black', 'red', 'green']:
            await message.answer("❌ Цвет должен быть: black, red или green")
            return
        
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
            return
        
        update_balance(message.from_user.id, -bet)
        
        result = roulette_spin()
        
        if result == color:
            if result == 'green':
                win = bet * 35
            else:
                win = bet * 2
            
            update_balance(message.from_user.id, win)
            await message.answer(
                f"🎡 Рулетка!\n"
                f"Выпало: {'🔴' if result == 'red' else '⚫️' if result == 'black' else '🟢 ЗЕЛЁНЫЙ!'}\n"
                f"Ты угадал! Выигрыш: {win:.2f}₽\n"
                f"Баланс: {get_balance(message.from_user.id):.2f}₽"
            )
        else:
            await message.answer(
                f"🎡 Рулетка!\n"
                f"Выпало: {'🔴' if result == 'red' else '⚫️' if result == 'black' else '🟢'}\n"
                f"Ты проиграл {bet:.2f}₽\n"
                f"Баланс: {get_balance(message.from_user.id):.2f}₽"
            )
    except:
        await message.answer("❌ Использование: /roulette [black/red/green] [ставка]")

# ========== ЗАПУСК ==========
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
