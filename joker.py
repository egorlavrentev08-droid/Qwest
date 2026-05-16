# joker.py
import asyncio
import random
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_balance, update_balance
from config import MIN_BET

class JokerGame:
    def __init__(self, uid, bet):
        self.uid = uid
        self.bet = bet
        self.rows = []
        self.joker_positions = []
        self.found_jokers = 0
        self.active = True
        self.last_update = 0
        self.add_first_row()
    
    def add_first_row(self):
        cards = ['🎴', '🎴', '🎴']
        joker_pos = random.randint(0, 2)
        cards[joker_pos] = '🃏'
        self.rows = [cards]
        self.joker_positions = [[False, False, False]]
        self.joker_positions[0][joker_pos] = True
    
    def add_row(self):
        cards = ['🎴', '🎴', '🎴']
        joker_pos = random.randint(0, 2)
        cards[joker_pos] = '🃏'
        self.rows.append(cards)
        joker_row = [False, False, False]
        joker_row[joker_pos] = True
        self.joker_positions.append(joker_row)
    
    def reveal(self, r, c):
        if not self.active or r >= len(self.rows):
            return None
        card = self.rows[r][c]
        if card == '💎' or card == '❌':
            return None
        if card == '🃏':
            self.rows[r][c] = '💎'
            self.found_jokers += 1
            self.add_row()
            return 'win'
        else:
            self.rows[r][c] = '❌'
            self.active = False
            return 'lose'
    
    def get_total_win(self):
        if self.found_jokers == 0:
            return 0
        total = 1.0
        for i in range(self.found_jokers):
            total += 0.3 + i * 0.1
        return self.bet * total
    
    def cashout(self):
        win = self.get_total_win()
        if win > 0:
            update_balance(self.uid, win - self.bet)
        self.active = False
        return win
    
    def get_final_board(self):
        kb = InlineKeyboardBuilder()
        for r, row in enumerate(self.rows):
            for c, card in enumerate(row):
                text = "💎" if card == '🃏' else "❌" if card == '🎴' else card
                kb.button(text=text, callback_data="noop")
            kb.adjust(3)
        return kb.as_markup()
    
    def get_current_board(self):
        kb = InlineKeyboardBuilder()
        for r, row in enumerate(self.rows):
            for c, card in enumerate(row):
                text = card if card in ['💎', '❌'] else "❓"
                kb.button(text=text, callback_data=f"joker_{r}_{c}")
            kb.adjust(3)
        kb.row(InlineKeyboardButton(text="💰 ЗАБРАТЬ", callback_data="joker_cashout"))
        return kb.as_markup()

joker_games = {}

def register_joker(dp):
    @dp.message(Command("joker"))
    async def cmd_joker(message: types.Message):
        try:
            bet = float(message.text.split()[1])
            if bet < MIN_BET:
                await message.answer(f"❌ Минимальная ставка {MIN_BET}₽")
                return
            
            balance = get_balance(message.from_user.id)
            if balance < bet:
                await message.answer(f"❌ Недостаточно средств! Баланс: {balance:.2f}₽")
                return
            
            update_balance(message.from_user.id, -bet)
            game = JokerGame(message.from_user.id, bet)
            joker_games[message.from_user.id] = game
            
            text = f"🃏 ДЖОКЕР | Ставка: {bet:.2f}₽\n\n❓ Ищи джокера! В каждом ряду 1 джокер.\nКаждый найденный джокер даёт +30% + 10% за каждого предыдущего"
            await message.answer(text, reply_markup=game.get_current_board())
        except:
            await message.answer("❌ Использование: /joker [ставка]")
    
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
        
        now = asyncio.get_event_loop().time()
        if now - game.last_update < 0.5:
            await callback.answer("⏳ Не так быстро!", show_alert=False)
            return
        game.last_update = now
        
        if callback.data == "joker_cashout":
            win = game.cashout()
            if win > 0:
                await callback.message.edit_text(f"💰 Ты забрал {win:.2f}₽!")
            else:
                final_board = game.get_final_board()
                await callback.message.edit_text(f"❌ Ты не нашёл ни одного джокера! Проигрыш {game.bet:.2f}₽\n\n**Вот где были карты:**", reply_markup=final_board)
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
            await callback.message.edit_text(f"😔 Обычная карта! Проигрыш {game.bet:.2f}₽\n\n**Вот где были карты:**", reply_markup=final_board)
            del joker_games[user_id]
        else:
            mult = 1.0
            for i in range(game.found_jokers):
                mult += 0.3 + i * 0.1
            text = f"🃏 ДЖОКЕР | Ставка: {game.bet:.2f}₽\n\n✅ Найдено джокеров: {game.found_jokers}\n📈 Множитель: x{mult:.2f}\n💰 Выигрыш: {game.bet * mult:.2f}₽\n\n🎉 Ты нашёл джокера! Добавлен новый ряд!"
            await callback.message.edit_text(text, reply_markup=game.get_current_board())
            await callback.answer("🎉 ДЖОКЕР!")
        await callback.answer()
