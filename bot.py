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

def roulette_spin():
    # Честная рулетка
    rand = random.random()
    if rand < 0.485:
        return 'black'
    elif rand < 0.97:
        return 'red'
    else:
        return 'green'

# ========== КОМАНДЫ ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "🎰 Добро пожаловать в Казино!\n\n"
        "🎲 /mines [мины] [ставка] - Мины (3-24 мины, ставка от 10)\n"
        "🎡 /roulette [номер/цвет/диапазон] [ставка] - Рулетка (ставка от 500)\n"
        "🃏 /joker [ставка] - Джокер (ставка от 100)\n"
        "💰 /bonus - Бонус 10000₽\n"
        "💳 /balance - Баланс\n"
        "📤 /pay [сумма] (ответ на сообщение) - Перевод\n\n"
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
        await message.answer("❌ Бонус раз в 24 часа!")
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
            await message.answer("❌ Сумма >0")
            return
    except:
        await message.answer("❌ /pay [сумма] (ответ на сообщение)")
        return
    sender = message.from_user.id
    receiver = message.reply_to_message.from_user.id
    if sender == receiver:
        await message.answer("❌ Себе нельзя")
        return
    if get_balance(sender) < amount:
        await message.answer(f"❌ Не хватает! Баланс: {get_balance(sender):.2f}₽")
        return
    update_balance(sender, -amount)
    update_balance(receiver, amount)
    await message.answer(f"✅ Переведено {amount:.2f}₽ → {receiver}")
    await bot.send_message(receiver, f"💰 Получено {amount:.2f}₽ от {sender}")

@dp.message(lambda msg: msg.text and msg.text.startswith("дай "))
async def admin_give(message: types.Message):
    parts = message.text.split()
    if len(parts) != 3 or parts[1] != ADMIN_CODE:
        await message.answer("❌ Неверный код")
        return
    try:
        amount = float(parts[2])
        update_balance(message.from_user.id, amount)
        await message.answer(f"✅ Выдано {amount:.2f}₽")
    except:
        await message.answer("❌ Ошибка суммы")

# ========== ИГРА МИНЫ ==========
class MinesGame:
    def __init__(self, user_id, bet, num_mines):
        self.user_id = user_id
        self.bet = bet
        self.num_mines = num_mines
        self.field = [[0]*5 for _ in range(5)]
        self.revealed = [[False]*5 for _ in range(5)]
        self.active = True
        # ставим мины
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
            return {'status':'lose'}
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

mines_games = {}

@dp.message(Command("mines"))
async def cmd_mines(message: types.Message):
    try:
        parts = message.text.split()
        num_mines = int(parts[1])
        bet = float(parts[2])
        if num_mines < 3 or num_mines > 24:
            await message.answer("❌ Мины от 3 до 24")
            return
        if bet < 10:
            await message.answer("❌ Ставка от 10₽")
            return
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Не хватает! Баланс: {balance:.2f}₽")
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
            f"💣 Мины | Ставка: {bet:.2f}₽ | Мин: {num_mines}\n"
            f"Множитель: x{game.get_multiplier(0):.2f} (матожидание 0.92)\n"
            f"Открывай клетки!",
            reply_markup=builder.as_markup()
        )
    except:
        await message.answer("❌ /mines [3-24] [ставка от 10]")

@dp.callback_query(lambda c: c.data.startswith('mine_'))
async def mines_callback(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.active:
        await callback.answer("Игра не активна")
        return
    action = callback.data.split('_')
    if action[1] == 'cancel':
        update_balance(callback.from_user.id, game.bet)
        del mines_games[callback.from_user.id]
        await callback.message.edit_text("❌ Ставка возвращена")
        await callback.answer()
        return
    row, col = int(action[1]), int(action[2])
    res = game.reveal(row, col)
    if res['status'] == 'lose':
        del mines_games[callback.from_user.id]
        await callback.message.edit_text(f"💥 Мина! Проигрыш {game.bet:.2f}₽")
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
        await callback.message.edit_text(f"🎉 ПОБЕДА! +{win:.2f}₽ (x{res['multiplier']:.2f})")
        del mines_games[callback.from_user.id]
    else:
        builder.row(
            InlineKeyboardButton(text="💰 Забрать", callback_data="mine_cashout"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="mine_cancel")
        )
        await callback.message.edit_text(
            f"✅ Открыто: {res['revealed']} | Множитель: x{res['multiplier']:.2f}\n"
            f"💰 Выигрыш: {game.bet * res['multiplier']:.2f}₽",
            reply_markup=builder.as_markup()
        )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "mine_cashout")
async def mines_cashout(callback: types.CallbackQuery):
    game = mines_games.get(callback.from_user.id)
    if not game or not game.active:
        await callback.answer("Нет активной игры")
        return
    win = game.cashout()
    await callback.message.edit_text(f"💰 Забрал {win:.2f}₽")
    del mines_games[callback.from_user.id]
    await callback.answer()

# ========== ИГРА ДЖОКЕР (бесконечные ряды) ==========
class JokerGame:
    def __init__(self, user_id, bet):
        self.user_id = user_id
        self.bet = bet
        self.rows = []  # каждый ряд: [('🃏' или '🎴', открыта ли)]
        self.add_row()
    def add_row(self):
        # новый ряд из 3 карт, шанс джокера 1/3 на каждой позиции
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
            # добавляем новый ряд снизу
            self.add_row()
            return {'status':'win', 'multiplier':1.0}
        else:
            return {'status':'lose'}
    def get_total_win(self):
        # считаем джокеров
        jokers = 0
        for row in self.rows:
            for card, rev in row:
                if rev and card == '🃏':
                    jokers += 1
        if jokers == 0:
            return 0
        total = 1.0
        for i in range(jokers):
            total += 0.3 + i*0.1
        return self.bet * total
    def cashout(self):
        win = self.get_total_win()
        if win > 0:
            update_balance(self.user_id, win - self.bet)
        else:
            return 0
        return win

joker_games = {}

@dp.message(Command("joker"))
async def cmd_joker(message: types.Message):
    try:
        bet = float(message.text.split()[1])
        if bet < 100:
            await message.answer("❌ Ставка от 100₽")
            return
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Не хватает! Баланс: {balance:.2f}₽")
            return
        update_balance(message.from_user.id, -bet)
        game = JokerGame(message.from_user.id, bet)
        joker_games[message.from_user.id] = game
        await show_joker_board(message, message.from_user.id, game, is_edit=False)
    except:
        await message.answer("❌ /joker [ставка от 100]")

async def show_joker_board(msg, user_id, game, is_edit=True, callback_query=None):
    builder = InlineKeyboardBuilder()
    for ridx, row in enumerate(game.rows):
        for cidx, (card, rev) in enumerate(row):
            text = card if rev else "❓"
            builder.button(text=text, callback_data=f"joker_{ridx}_{cidx}")
        builder.adjust(3)
    builder.row(InlineKeyboardButton(text="💰 Забрать", callback_data="joker_cashout"))
    text = f"🃏 ДЖОКЕР | Ставка: {game.bet:.2f}₽\n"
    jokers = 0
    for row in game.rows:
        for card, rev in row:
            if rev and card == '🃏':
                jokers += 1
    if jokers > 0:
        total_mult = 1.0
        for i in range(jokers):
            total_mult += 0.3 + i*0.1
        text += f"✅ Найдено джокеров: {jokers} | Множитель: x{total_mult:.2f}\n💰 Выигрыш: {game.bet*total_mult:.2f}₽"
    else:
        text += f"❓ Ищи джокеров! Каждый даёт +30%+10%*N"
    if is_edit and callback_query:
        await callback_query.message.edit_text(text, reply_markup=builder.as_markup())
    elif is_edit and not callback_query:
        await msg.edit_text(text, reply_markup=builder.as_markup())
    else:
        await msg.answer(text, reply_markup=builder.as_markup())

@dp.callback_query(lambda c: c.data.startswith('joker_'))
async def joker_callback(callback: types.CallbackQuery):
    game = joker_games.get(callback.from_user.id)
    if not game:
        await callback.answer("Игра не активна")
        return
    if callback.data == "joker_cashout":
        win = game.cashout()
        if win > 0:
            await callback.message.edit_text(f"💰 Забрал {win:.2f}₽!")
        else:
            await callback.message.edit_text("❌ Нет джокеров — проигрыш")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    parts = callback.data.split('_')
    ridx, cidx = int(parts[1]), int(parts[2])
    res = game.reveal(ridx, cidx)
    if res is None:
        await callback.answer("Уже открыто")
        return
    if res['status'] == 'lose':
        await callback.message.edit_text(f"😔 Обычная карта! Проигрыш {game.bet:.2f}₽")
        del joker_games[callback.from_user.id]
        await callback.answer()
        return
    else:
        await show_joker_board(callback.message, callback.from_user.id, game, is_edit=True, callback_query=callback)
        await callback.answer("🎉 ДЖОКЕР! +новый ряд")
        return

# ========== РУЛЕТКА С АНИМАЦИЕЙ ==========
async def roulette_animation(message, bet, selected):
    # selected может быть цветом или числом/диапазоном
    results = []
    for _ in range(20):
        results.append(roulette_spin())
    final = roulette_spin()
    # анимация
    msg = await message.answer("🎡 Крутим рулетку...\n==========|==========\n")
    for i in range(len(results)):
        line = "⬛🟥⬛🟥🟩⬛🟥⬛🟥"
        arrow = "==========|=========="
        display = f"{arrow}\n{line}\n{arrow}"
        await msg.edit_text(f"🎡 {display}\n{results[i]}")
        await asyncio.sleep(0.2 if i<10 else 0.1 if i<15 else 0.3)
    # финальный
    line = "⬛🟥⬛🟥🟩⬛🟥⬛🟥"
    arrow = "==========|=========="
    display = f"{arrow}\n{line}\n{arrow}"
    await msg.edit_text(f"🎡 {display}\n⚡ СТОП! {final}")

    # проверка выигрыша
    win = False
    win_amount = 0
    if isinstance(selected, str):  # цвет
        if final == selected:
            win = True
            win_amount = bet * 2
            if selected == 'green':
                win_amount = bet * 35
    else:  # число или диапазон
        # заглушка, для простоты сделаем только цвет, но можно добавить числа
        pass
    if win:
        update_balance(message.from_user.id, win_amount - bet)
        await message.answer(f"🎉 ВЫИГРЫШ! +{win_amount:.2f}₽")
    else:
        await message.answer(f"❌ ПРОИГРЫШ -{bet:.2f}₽")

@dp.message(Command("roulette"))
async def cmd_roulette(message: types.Message):
    try:
        parts = message.text.lower().split()
        if len(parts) < 3:
            await message.answer("❌ /roulette [black/red/green] [ставка от 500]")
            return
        bet = float(parts[-1])
        if bet < 500:
            await message.answer("❌ Ставка от 500₽")
            return
        balance = get_balance(message.from_user.id)
        if balance < bet:
            await message.answer(f"❌ Не хватает! Баланс: {balance:.2f}₽")
            return
        selected = parts[1]
        if selected not in ['black','red','green']:
            await message.answer("❌ Ставка на black/red/green")
            return
        update_balance(message.from_user.id, -bet)
        await roulette_animation(message, bet, selected)
    except:
        await message.answer("❌ /roulette [black/red/green] [ставка от 500]")

# ========== ЗАПУСК ==========
async def main():
    print("🎰 Казино бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
