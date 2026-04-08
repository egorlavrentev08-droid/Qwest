import logging
from typing import Dict, List
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ===== КОНФИГУРАЦИЯ =====
TOKEN = "8796145107:AAGMIvKd-Ohcxl4pd4GzkvgsLshZn2kREEc"  # Замени на новый токен после отзыва!

# Соответствие кода -> информация о команде
CODES = {
    "8372914650182749": {"name": "Команда 1", "number": "Первая"},
    "4718263095147203": {"name": "Команда 2", "number": "Вторая"},
    "6293850174263918": {"name": "Команда 3", "number": "Третья"},
    "5049273618294756": {"name": "Команда 4", "number": "Четвертая"},
}

# Хранилище победителей: {chat_id: [список команд-победителей]}
winners: Dict[int, List[str]] = {}

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== ФУНКЦИИ БОТА =====

async def send_to_all_groups(app: Application, message: str):
    """
    Отправляет сообщение во все группы, где есть бот
    """
    sent_count = 0
    try:
        # Получаем обновления, чтобы найти все чаты
        async for update in app.bot.get_updates():
            if update.effective_chat and update.effective_chat.type in ["group", "supergroup"]:
                try:
                    await app.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=message
                    )
                    sent_count += 1
                    logger.info(f"Уведомление отправлено в чат {update.effective_chat.id}")
                except Exception as e:
                    logger.error(f"Не удалось отправить в чат {update.effective_chat.id}: {e}")
        
        # Альтернативный способ: проходим по всем известным чатам из winners
        for chat_id in winners.keys():
            if chat_id not in [update.effective_chat.id for update in await app.bot.get_updates()]:
                try:
                    await app.bot.send_message(chat_id=chat_id, text=message)
                    sent_count += 1
                    logger.info(f"Уведомление отправлено в чат {chat_id} (из winners)")
                except Exception as e:
                    logger.error(f"Не удалось отправить в чат {chat_id}: {e}")
        
        logger.info(f"Всего отправлено уведомлений: {sent_count}")
    except Exception as e:
        logger.error(f"Ошибка при рассылке уведомлений: {e}")

async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /code
    """
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_input = context.args
    
    # Проверяем, что код введен
    if not user_input:
        await update.message.reply_text(
            "❌ Использование: /code [код]\n"
            "Пример: /code 8372914650182749"
        )
        return
    
    code = user_input[0].strip()
    
    # Проверяем, существует ли такой код
    if code not in CODES:
        await update.message.reply_text(
            "❌ Неверный код. Попробуйте снова.\n"
            "Доступные коды вы получили от организаторов."
        )
        return
    
    team_info = CODES[code]
    team_name = team_info["name"]
    team_number = team_info["number"]
    
    # Инициализируем список победителей для этого чата
    if chat_id not in winners:
        winners[chat_id] = []
    
    # Проверяем, не побеждала ли уже эта команда в этой группе
    if team_name in winners[chat_id]:
        await update.message.reply_text(
            f"⚠️ Команда {team_number} уже проходила в этой группе.\n"
            f"Бот не реагирует на повторные попытки."
        )
        logger.info(f"Повторная попытка: {team_name} в чате {chat_id} от пользователя {user.id}")
        return
    
    # Проверяем, не прошли ли уже две команды в этой группе
    if len(winners[chat_id]) >= 2:
        await update.message.reply_text(
            "🏁 Игра в этой группе завершена!\n"
            "Две команды уже успешно прошли задание.\n"
            "Бот больше не реагирует на коды."
        )
        logger.info(f"Попытка ввести код после завершения игры в чате {chat_id}")
        return
    
    # Фиксируем победу команды
    winners[chat_id].append(team_name)
    
    # Личное поздравление
    await update.message.reply_text(
        f"🎉 Поздравляю! Вы угадали код!\n"
        f"🏆 {team_name} успешно прошла задание!"
    )
    
    # Сообщение в текущую группу о прохождении
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ {team_name} прошла!"
    )
    
    # Рассылаем уведомление во ВСЕ группы
    notification = f"📢 {team_number} команда успешно справилась с заданием!"
    await send_to_all_groups(context.application, notification)
    
    # Логируем событие
    logger.info(f"ПОБЕДА: {team_name} в чате {chat_id} от пользователя {user.id}")
    logger.info(f"Текущие победители в чате {chat_id}: {winners[chat_id]}")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /stats - показывает статистику в текущей группе
    """
    chat_id = update.effective_chat.id
    
    if chat_id not in winners or len(winners[chat_id]) == 0:
        await update.message.reply_text(
            "📊 В этой группе пока никто не прошел задание.\n"
            "Используйте /code [код] для проверки."
        )
        return
    
    teams_passed = winners[chat_id]
    passed_list = "\n".join([f"• {team}" for team in teams_passed])
    
    await update.message.reply_text(
        f"📊 Статистика по этой группе:\n\n"
        f"✅ Прошло команд: {len(teams_passed)}/2\n"
        f"{passed_list}\n\n"
        f"{'🏁 Игра завершена!' if len(teams_passed) >= 2 else '🎯 Остались свободные места!'}"
    )

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /reset - сбрасывает победителей в текущей группе (только для админов)
    """
    chat_id = update.effective_chat.id
    
    # Проверяем, является ли пользователь админом
    chat_member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
    
    if not chat_member.status in ["administrator", "creator"]:
        await update.message.reply_text("❌ Только администраторы группы могут сбрасывать прогресс!")
        return
    
    if chat_id in winners:
        old_winners = winners[chat_id].copy()
        winners[chat_id] = []
        await update.message.reply_text(
            f"🔄 Прогресс в этой группе сброшен!\n"
            f"Были удалены победители: {', '.join(old_winners)}"
        )
        logger.info(f"Сброс прогресса в чате {chat_id} админом {update.effective_user.id}")
    else:
        await update.message.reply_text("📭 В этой группе нет сохраненного прогресса для сброса.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /start - приветствие
    """
    await update.message.reply_text(
        "🤖 Привет! Я бот для проверки кодов.\n\n"
        "📝 Как использовать:\n"
        "• /code [код] - проверить код и пройти задание\n"
        "• /stats - посмотреть статистику в этой группе\n"
        "• /help - показать эту справку\n\n"
        "⚠️ В каждой группе могут пройти только 2 команды!\n"
        "При повторном вводе кода бот не реагирует."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /help - справка
    """
    await update.message.reply_text(
        "📚 Справка по командам:\n\n"
        "/code [код] - проверить код.\n"
        "  Пример: /code 8372914650182749\n\n"
        "/stats - показать, какие команды уже прошли в этой группе\n\n"
        "/reset - сбросить прогресс в группе (только для админов)\n\n"
        "/start - приветствие\n"
        "/help - эта справка\n\n"
        "🎮 Правила:\n"
        "• В каждой группе могут пройти ТОЛЬКО 2 команды\n"
        "• После этого бот перестает реагировать на коды\n"
        "• При успешном прохождении уведомление летит во все группы"
    )

async def post_init(app: Application):
    """
    Выполняется после запуска бота
    """
    logger.info("🤖 Бот успешно запущен и готов к работе!")
    logger.info("Бот будет отслеживать команды /code во всех группах")

# ===== ЗАПУСК БОТА =====

def main():
    """
    Главная функция запуска бота
    """
    # Создаем приложение
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reset", reset_command))
    
    # Запускаем бота
    logger.info("Запуск бота...")
    app.run_polling()

if __name__ == "__main__":
    main()
