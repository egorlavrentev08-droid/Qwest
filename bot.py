import logging
from typing import Dict, List, Set
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatType

# ===== КОНФИГУРАЦИЯ =====
TOKEN = "8796145107:AAGMIvKd-Ohcxl4pd4GzkvgsLshZn2kREEc"  # ЗАМЕНИ НА НОВЫЙ ТОКЕН!

# Соответствие кода -> информация о команде
CODES = {
    "8372914650182749": {"name": "Команда 1", "number": "Первая"},
    "4718263095147203": {"name": "Команда 2", "number": "Вторая"},
    "6293850174263918": {"name": "Команда 3", "number": "Третья"},
    "5049273618294756": {"name": "Команда 4", "number": "Четвертая"},
}

# Хранилище победителей: {chat_id: [список команд-победителей]}
winners: Dict[int, List[str]] = {}

# Хранилище всех групп, где есть бот
all_groups: Set[int] = set()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Добавляет группу в список всех групп (если это группа)"""
    chat = update.effective_chat
    if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        all_groups.add(chat.id)
        logger.info(f"Группа {chat.id} ({chat.title}) добавлена в список рассылки")


async def send_to_all_groups(app: Application, message: str):
    """Отправляет сообщение во все группы, где есть бот"""
    sent_count = 0
    failed_count = 0
    
    for chat_id in all_groups.copy():
        try:
            await app.bot.send_message(chat_id=chat_id, text=message)
            sent_count += 1
            logger.info(f"✅ Уведомление отправлено в чат {chat_id}")
        except Exception as e:
            failed_count += 1
            logger.error(f"❌ Не удалось отправить в чат {chat_id}: {e}")
            if "chat not found" in str(e).lower() or "bot is not a member" in str(e).lower():
                all_groups.discard(chat_id)
                logger.info(f"Чат {chat_id} удален из списка (бот не участник)")
    
    logger.info(f"📊 Рассылка завершена: отправлено {sent_count}, ошибок {failed_count}")


async def code_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /code"""
    chat_id = update.effective_chat.id
    user = update.effective_user
    user_input = context.args
    
    # Добавляем группу в список для рассылки
    await add_group(update, context)
    
    # Проверяем, что код введен
    if not user_input:
        await update.message.reply_text("Шифр решён неверно")
        return
    
    code = user_input[0].strip()
    
    # Проверяем, существует ли такой код
    if code not in CODES:
        await update.message.reply_text("Шифр решён неверно")
        return
    
    team_info = CODES[code]
    team_name = team_info["name"]
    team_number = team_info["number"]
    
    # Инициализируем список победителей для этого чата
    if chat_id not in winners:
        winners[chat_id] = []
    
    # Проверяем, не побеждала ли уже эта команда в этой группе
    if team_name in winners[chat_id]:
        await update.message.reply_text("Шифр решён неверно")
        return
    
    # Проверяем, не прошли ли уже две команды в этой группе
    if len(winners[chat_id]) >= 2:
        await update.message.reply_text("Шифр решён неверно")
        return
    
    # Фиксируем победу команды
    winners[chat_id].append(team_name)
    
    # Сообщение в текущую группу о прохождении
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ {team_name} прошла!"
    )
    
    # ===== РАССЫЛКА ВО ВСЕ ГРУППЫ =====
    notification = f"📢 {team_number} команда успешно справилась с заданием!"
    await send_to_all_groups(context.application, notification)
    
    # Логируем событие
    logger.info(f"🏆 ПОБЕДА: {team_name} в чате {chat_id} от {user.id}")
    logger.info(f"📋 Текущие победители в чате {chat_id}: {winners[chat_id]}")
    logger.info(f"📡 Всего групп в рассылке: {len(all_groups)}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats - показывает статистику в текущей группе"""
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
    """Команда /reset - сбрасывает победителей в текущей группе (только для админов)"""
    chat_id = update.effective_chat.id
    
    # Проверяем, является ли пользователь админом
    try:
        chat_member = await context.bot.get_chat_member(chat_id, update.effective_user.id)
        if not chat_member.status in ["administrator", "creator"]:
            await update.message.reply_text("❌ Только администраторы группы могут сбрасывать прогресс!")
            return
    except Exception as e:
        await update.message.reply_text("❌ Не удалось проверить права администратора!")
        return
    
    if chat_id in winners:
        old_winners = winners[chat_id].copy()
        winners[chat_id] = []
        await update.message.reply_text(
            f"🔄 Прогресс в этой группе сброшен!\n"
            f"Были удалены победители: {', '.join(old_winners)}"
        )
        logger.info(f"🔄 Сброс прогресса в чате {chat_id} админом {update.effective_user.id}")
    else:
        await update.message.reply_text("📭 В этой группе нет сохраненного прогресса для сброса.")


async def groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /groups - показывает список всех групп (только для админа бота)"""
    # Проверяем, что команду ввел владелец бота (укажи свой ID)
    AUTHORIZED_USER_ID = 123456789  # ЗАМЕНИ НА СВОЙ TELEGRAM ID
    
    if update.effective_user.id != AUTHORIZED_USER_ID:
        await update.message.reply_text("❌ Эта команда только для владельца бота.")
        return
    
    if not all_groups:
        await update.message.reply_text("📭 Бот пока не добавлен ни в одну группу.")
        return
    
    groups_list = []
    for chat_id in all_groups:
        try:
            chat = await context.bot.get_chat(chat_id)
            groups_list.append(f"• {chat.title} (ID: {chat_id})")
        except:
            groups_list.append(f"• Группа {chat_id} (недоступна)")
    
    await update.message.reply_text(
        f"📡 Бот добавлен в {len(all_groups)} групп(ы):\n\n" + "\n".join(groups_list)
    )


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start - минимальное приветствие"""
    await add_group(update, context)
    # Ничего не отправляем


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help - справка"""
    await update.message.reply_text(
        "📚 Команды:\n\n"
        "/code [код] - проверить код\n"
        "/stats - статистика в группе\n"
        "/reset - сброс прогресса (админ)\n"
        "/start - ничего\n"
        "/help - справка"
    )


async def post_init(app: Application):
    """Выполняется после запуска бота"""
    logger.info("🤖 Бот успешно запущен и готов к работе!")


def main():
    """Главная функция запуска бота"""
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    # Добавляем обработчики команд
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("code", code_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("groups", groups_command))
    
    # Запускаем бота
    app.run_polling()


if __name__ == "__main__":
    main()
