# mines.py
import asyncio
import random
from aiogram import types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database import get_balance, update_balance
from config import MIN_BET

class MinesGame:
    def __init__(self, uid, bet, mines):
        self.uid = uid
        self.bet = bet
        self.mines = mines
        self.field = [[0]*5 for _ in range(5)]
        self.revealed = [[False]*5 for _ in range(5)]
        self.active = True
        self.last_update = 0
        
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

def register_mines(dp):
    @dp.message(Command("mines"))
    async def cmd_mines(message: types.Message):
        try:
            parts = message.text.split()
            mines = int(parts[1])
            bet = float(parts[2])
            
            if mines < 3 or mines > 24:
                await message.answer("❌ Количество мин от 3 до 24")
                return
            if bet < MIN_BET:
                await message.answer(f"❌ Минимальная ставка {MIN_BET}₽")
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
                f"💣 МИНЫ | Ставка: {bet:.2f}₽ | Мин: {mines}\nМножитель: x{game.get_multiplier(0):.2f}\n\nОткрывай клетки!",
                reply_markup=kb.as_markup()
            )
        except:
            await message.answer("❌ Использование: /mines [3-24] [ставка]")
    
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
        
        now = asyncio.get_event_loop().time()
        if now - game.last_update < 0.5:
            await callback.answer("⏳ Не так быстро!", show_alert=False)
            return
        game.last_update = now
        
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
                f"✅ Открыто клеток: {opened}\n📈 Множитель: x{mult:.2f}\n💰 Возможный выигрыш: {game.bet * mult:.2f}₽",
                reply_markup=kb.as_markup()
            )
        await callback.answer()
