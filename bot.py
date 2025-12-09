import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime
import random
from threading import Thread
from flask import Flask

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask додаток для Render (щоб не засинав)
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Telegram Bot is running!"

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    """Запустити Flask в окремому потоці"""
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)

# Стани для conversation handler
CHOOSING_CHECKIN_MEDIA, CHOOSING_CHECKOUT_MEDIA = range(2)

# Зберігання даних користувачів
user_status = {}
checkin_history = []

# URL картинок та гіфок за замовчуванням
DEFAULT_CHECKIN_IMAGES = [
    "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif",
    "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
]

DEFAULT_CHECKOUT_IMAGES = [
    "https://media.giphy.com/media/lD76yTC5zxZPG/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/KB8C86UMgLDThpt4WT/giphy.gif",
    "https://media.giphy.com/media/l3q2Z6S6n38zjPswo/giphy.gif",
]

# Користувацькі медіа
user_media = {}

def get_user_media(user_id):
    """Отримати медіа користувача або дефолтні"""
    if user_id not in user_media:
        user_media[user_id] = {
            'checkin': DEFAULT_CHECKIN_IMAGES.copy(),
            'checkout': DEFAULT_CHECKOUT_IMAGES.copy()
        }
    return user_media[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Check-in", callback_data='checkin'),
            InlineKeyboardButton("🚪 Check-out", callback_data='checkout')
        ],
        [InlineKeyboardButton("📊 Мій статус", callback_data='status')],
        [InlineKeyboardButton("🎨 Налаштувати медіа", callback_data='settings')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '👋 Привіт! Я бот для відмітки робочого часу.\n\n'
        '📝 Команди:\n'
        '/checkin - почати робочий день\n'
        '/checkout - закінчити робочий день\n'
        '/status - переглянути свій статус\n'
        '/team - статус всієї команди\n'
        '/settings - налаштувати свої картинки\n'
        '/add_checkin_media - додати медіа для check-in\n'
        '/add_checkout_media - додати медіа для check-out\n'
        '/reset_media - скинути до стандартних',
        reply_markup=reply_markup
    )

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню налаштувань медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Додати check-in медіа", callback_data='add_checkin')],
        [InlineKeyboardButton("➕ Додати check-out медіа", callback_data='add_checkout')],
        [InlineKeyboardButton("📋 Переглянути мої медіа", callback_data='view_media')],
        [InlineKeyboardButton("🔄 Скинути до стандартних", callback_data='reset_media')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = (f"🎨 Налаштування медіа\n\n"
               f"📊 Твої медіа:\n"
               f"✅ Check-in: {len(media['checkin'])} файлів\n"
               f"🚪 Check-out: {len(media['checkout'])} файлів\n\n"
               f"Обери дію:")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)

async def view_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переглянути всі збережені медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    message = "📋 Твої медіа:\n\n"
    
    message += "✅ Check-in медіа:\n"
    for i, url in enumerate(media['checkin'], 1):
        short_url = url[:50] + "..." if len(url) > 50 else url
        message += f"{i}. {short_url}\n"
    
    message += "\n🚪 Check-out медіа:\n"
    for i, url in enumerate(media['checkout'], 1):
        short_url = url[:50] + "..." if len(url) > 50 else url
        message += f"{i}. {short_url}\n"
    
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(message)

async def add_checkin_media_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок додавання check-in медіа"""
    message = (
        "📸 Додавання check-in медіа\n\n"
        "Надішли мені:\n"
        "• URL картинки/гіфки (наприклад: https://media.giphy.com/...)\n"
        "• Або просто надішли фото/гіфку\n\n"
        "Відправ /cancel щоб скасувати"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message)
    else:
        await update.message.reply_text(message)
    
    return CHOOSING_CHECKIN_MEDIA

async def add_checkout_media_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок додавання check-out медіа"""
    message = (
        "📸 Додавання check-out медіа\n\n"
        "Надішли мені:\n"
        "• URL картинки/гіфки (наприклад: https://media.giphy.com/...)\n"
        "• Або просто надішли фото/гіфку\n\n"
        "Відправ /cancel щоб скасувати"
    )
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message)
    else:
        await update.message.reply_text(message)
    
    return CHOOSING_CHECKOUT_MEDIA

async def receive_checkin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання check-in медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    if update.message.text:
        url = update.message.text.strip()
        if url.startswith('http'):
            media['checkin'].append(url)
            await update.message.reply_text(
                f"✅ Додано!\n\n"
                f"У тебе тепер {len(media['checkin'])} check-in медіа.\n"
                f"Надішли ще або /done щоб завершити."
            )
            return CHOOSING_CHECKIN_MEDIA
        else:
            await update.message.reply_text("❌ Це не схоже на URL. Спробуй ще раз або /cancel")
            return CHOOSING_CHECKIN_MEDIA
    
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        media['checkin'].append(file.file_id)
        await update.message.reply_text(
            f"✅ Фото додано!\n\n"
            f"У тебе тепер {len(media['checkin'])} check-in медіа.\n"
            f"Надішли ще або /done щоб завершити."
        )
        return CHOOSING_CHECKIN_MEDIA
    
    if update.message.animation:
        file = await update.message.animation.get_file()
        media['checkin'].append(file.file_id)
        await update.message.reply_text(
            f"✅ Гіфка додана!\n\n"
            f"У тебе тепер {len(media['checkin'])} check-in медіа.\n"
            f"Надішли ще або /done щоб завершити."
        )
        return CHOOSING_CHECKIN_MEDIA
    
    await update.message.reply_text("❌ Надішли URL, фото або гіфку. Або /cancel щоб скасувати.")
    return CHOOSING_CHECKIN_MEDIA

async def receive_checkout_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання check-out медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    if update.message.text:
        url = update.message.text.strip()
        if url.startswith('http'):
            media['checkout'].append(url)
            await update.message.reply_text(
                f"✅ Додано!\n\n"
                f"У тебе тепер {len(media['checkout'])} check-out медіа.\n"
                f"Надішли ще або /done щоб завершити."
            )
            return CHOOSING_CHECKOUT_MEDIA
        else:
            await update.message.reply_text("❌ Це не схоже на URL. Спробуй ще раз або /cancel")
            return CHOOSING_CHECKOUT_MEDIA
    
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        media['checkout'].append(file.file_id)
        await update.message.reply_text(
            f"✅ Фото додано!\n\n"
            f"У тебе тепер {len(media['checkout'])} check-out медіа.\n"
            f"Надішли ще або /done щоб завершити."
        )
        return CHOOSING_CHECKOUT_MEDIA
    
    if update.message.animation:
        file = await update.message.animation.get_file()
        media['checkout'].append(file.file_id)
        await update.message.reply_text(
            f"✅ Гіфка додана!\n\n"
            f"У тебе тепер {len(media['checkout'])} check-out медіа.\n"
            f"Надішли ще або /done щоб завершити."
        )
        return CHOOSING_CHECKOUT_MEDIA
    
    await update.message.reply_text("❌ Надішли URL, фото або гіфку. Або /cancel щоб скасувати.")
    return CHOOSING_CHECKOUT_MEDIA

async def done_adding_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершити додавання медіа"""
    await update.message.reply_text(
        "✅ Збережено! Тепер твої медіа будуть використовуватися при check-in/check-out.\n\n"
        "Використай /start щоб повернутися до головного меню."
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасувати додавання"""
    await update.message.reply_text("❌ Скасовано. Використай /start щоб повернутися.")
    return ConversationHandler.END

async def reset_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скинути медіа до стандартних"""
    user_id = update.effective_user.id
    user_media[user_id] = {
        'checkin': DEFAULT_CHECKIN_IMAGES.copy(),
        'checkout': DEFAULT_CHECKOUT_IMAGES.copy()
    }
    
    message = "🔄 Медіа скинуто до стандартних!"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message)
    else:
        await update.message.reply_text(message)

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkin або кнопка check-in"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id in user_status and user_status[user_id]['checked_in']:
        message = f"❗ {username}, ти вже зачекінився о {user_status[user_id]['checkin_time']}"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    current_time = datetime.now().strftime("%H:%M:%S")
    user_status[user_id] = {
        'checked_in': True,
        'checkin_time': current_time,
        'username': username
    }
    
    checkin_history.append({
        'user': username,
        'action': 'check-in',
        'time': current_time,
        'date': datetime.now().strftime("%d.%m.%Y")
    })
    
    media = get_user_media(user_id)
    media_item = random.choice(media['checkin'])
    
    message = f"✅ {username} почав робочий день!\n⏰ Час: {current_time}\n\n💪 Продуктивної роботи!"
    
    try:
        if update.callback_query:
            await update.callback_query.answer()
            if isinstance(media_item, str) and media_item.startswith('http'):
                await update.callback_query.message.reply_animation(animation=media_item, caption=message)
            else:
                await update.callback_query.message.reply_animation(animation=media_item, caption=message)
        else:
            if isinstance(media_item, str) and media_item.startswith('http'):
                await update.message.reply_animation(animation=media_item, caption=message)
            else:
                await update.message.reply_animation(animation=media_item, caption=message)
    except Exception as e:
        logger.error(f"Помилка відправки медіа: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkout або кнопка check-out"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id]['checked_in']:
        message = f"❗ {username}, ти ще не зачекінився!"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return
    
    checkin_time = user_status[user_id]['checkin_time']
    current_time = datetime.now().strftime("%H:%M:%S")
    
    checkin_dt = datetime.strptime(checkin_time, "%H:%M:%S")
    checkout_dt = datetime.strptime(current_time, "%H:%M:%S")
    work_duration = checkout_dt - checkin_dt
    hours, remainder = divmod(work_duration.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    user_status[user_id]['checked_in'] = False
    
    checkin_history.append({
        'user': username,
        'action': 'check-out',
        'time': current_time,
        'date': datetime.now().strftime("%d.%m.%Y")
    })
    
    media = get_user_media(user_id)
    media_item = random.choice(media['checkout'])
    
    message = (f"🚪 {username} закінчив робочий день!\n"
               f"⏰ Час виходу: {current_time}\n"
               f"⏱ Відпрацьовано: {hours}г {minutes}хв\n\n"
               f"👏 Чудова робота!")
    
    try:
        if update.callback_query:
            await update.callback_query.answer()
            if isinstance(media_item, str) and media_item.startswith('http'):
                await update.callback_query.message.reply_animation(animation=media_item, caption=message)
            else:
                await update.callback_query.message.reply_animation(animation=media_item, caption=message)
        else:
            if isinstance(media_item, str) and media_item.startswith('http'):
                await update.message.reply_animation(animation=media_item, caption=message)
            else:
                await update.message.reply_animation(animation=media_item, caption=message)
    except Exception as e:
        logger.error(f"Помилка відправки медіа: {e}")
        if update.callback_query:
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status або кнопка статусу"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id]['checked_in']:
        message = f"📊 {username}, ти зараз не на роботі.\n\nВикористай /checkin щоб почати робочий день!"
    else:
        checkin_time = user_status[user_id]['checkin_time']
        current_time = datetime.now()
        checkin_dt = datetime.strptime(checkin_time, "%H:%M:%S")
        checkin_dt = checkin_dt.replace(year=current_time.year, month=current_time.month, day=current_time.day)
        work_duration = current_time - checkin_dt
        hours, remainder = divmod(work_duration.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        message = (f"📊 Статус: {username}\n\n"
                   f"✅ Ти на роботі\n"
                   f"⏰ Check-in: {checkin_time}\n"
                   f"⏱ Працюєш вже: {hours}г {minutes}хв")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message)
    else:
        await update.message.reply_text(message)

async def team_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /team - показує статус всієї команди"""
    if not user_status:
        await update.message.reply_text("📊 Поки що немає даних про команду.")
        return
    
    online = []
    offline = []
    
    for uid, data in user_status.items():
        if data['checked_in']:
            online.append(f"✅ {data['username']} (з {data['checkin_time']})")
        else:
            offline.append(f"⭕ {data['username']}")
    
    message = "👥 Статус команди:\n\n"
    
    if online:
        message += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
    
    if offline:
        message += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    await update.message.reply_text(message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник натискань на кнопки"""
    query = update.callback_query
    
    if query.data == 'checkin':
        await checkin(update, context)
    elif query.data == 'checkout':
        await checkout(update, context)
    elif query.data == 'status':
        await status(update, context)
    elif query.data == 'settings':
        await settings_menu(update, context)
    elif query.data == 'add_checkin':
        await add_checkin_media_start(update, context)
    elif query.data == 'add_checkout':
        await add_checkout_media_start(update, context)
    elif query.data == 'view_media':
        await view_media(update, context)
    elif query.data == 'reset_media':
        await reset_media(update, context)
    elif query.data == 'back_to_main':
        await query.answer()
        keyboard = [
            [
                InlineKeyboardButton("✅ Check-in", callback_data='checkin'),
                InlineKeyboardButton("🚪 Check-out", callback_data='checkout')
            ],
            [InlineKeyboardButton("📊 Мій статус", callback_data='status')],
            [InlineKeyboardButton("🎨 Налаштувати медіа", callback_data='settings')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("👋 Головне меню:", reply_markup=reply_markup)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник помилок"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Запуск бота"""
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logger.error("BOT_TOKEN не знайдено! Додай змінну середовища BOT_TOKEN")
        return
    
    # Запускаємо Flask в окремому потоці
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask сервер запущено!")
    
    application = Application.builder().token(TOKEN).build()
    
    # Conversation handler для додавання медіа
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add_checkin_media", add_checkin_media_start),
            CommandHandler("add_checkout_media", add_checkout_media_start),
        ],
        states={
            CHOOSING_CHECKIN_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkin_media),
                MessageHandler(filters.PHOTO, receive_checkin_media),
                MessageHandler(filters.ANIMATION, receive_checkin_media),
                CommandHandler("done", done_adding_media),
            ],
            CHOOSING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkout_media),
                MessageHandler(filters.PHOTO, receive_checkout_media),
                MessageHandler(filters.ANIMATION, receive_checkout_media),
                CommandHandler("done", done_adding_media),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    # Додавання обробників
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("checkout", checkout))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("team", team_status))
    application.add_handler(CommandHandler("settings", settings_menu))
    application.add_handler(CommandHandler("reset_media", reset_media))
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Telegram бот запущено!")
    print("🤖 Telegram бот запущено!")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
