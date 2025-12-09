import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import random

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Зберігання даних користувачів
user_status = {}
checkin_history = []
user_preferences = {}

# Категорії GIF для чекіну
CHECKIN_CATEGORIES = {
    '💪 Мотивація': [
        "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif",
        "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
        "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    ],
    '☕ Ранок': [
        "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
        "https://media.giphy.com/media/3o7qDQ4kcSD1PLM3BK/giphy.gif",
        "https://media.giphy.com/media/KztT2c4u8mYYUiMKdJ/giphy.gif",
    ],
    '🚀 Продуктивність': [
        "https://media.giphy.com/media/l4FGGafcOHmrlQxG0/giphy.gif",
        "https://media.giphy.com/media/26ufdipQqU2lhNA4g/giphy.gif",
        "https://media.giphy.com/media/3oKIPnAiaMCws8nOsE/giphy.gif",
    ],
    '😎 Круто': [
        "https://media.giphy.com/media/d3mlE7uhX8KFgEmY/giphy.gif",
        "https://media.giphy.com/media/11sBLVxNs7v6WA/giphy.gif",
        "https://media.giphy.com/media/3o7TKF1fSIs1R19B8k/giphy.gif",
    ]
}

# Категорії GIF для вичекіну
CHECKOUT_CATEGORIES = {
    '👋 До побачення': [
        "https://media.giphy.com/media/lD76yTC5zxZPG/giphy.gif",
        "https://media.giphy.com/media/3oEjHWXddcCOGZNmFO/giphy.gif",
        "https://media.giphy.com/media/26gsjCZpPolPr3sBy/giphy.gif",
    ],
    '🎉 Відпочинок': [
        "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
        "https://media.giphy.com/media/KB8C86UMgLDThpt4WT/giphy.gif",
        "https://media.giphy.com/media/l3q2Z6S6n38zjPswo/giphy.gif",
    ],
    '😴 Втома': [
        "https://media.giphy.com/media/TGcD6N5dryYNi/giphy.gif",
        "https://media.giphy.com/media/12l9Bh8T1fuGI/giphy.gif",
        "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif",
    ],
    '✨ Виконано': [
        "https://media.giphy.com/media/XreQmk7ETCak0/giphy.gif",
        "https://media.giphy.com/media/111ebonMs90YLu/giphy.gif",
        "https://media.giphy.com/media/26u4cqiYI30juCOGY/giphy.gif",
    ]
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Check-in", callback_data='checkin'),
            InlineKeyboardButton("🚪 Check-out", callback_data='checkout')
        ],
        [
            InlineKeyboardButton("📊 Мій статус", callback_data='status'),
            InlineKeyboardButton("⚙️ Налаштування", callback_data='settings')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '👋 Привіт! Я бот для відмітки робочого часу.\n\n'
        '📌 Команди:\n'
        '/checkin - почати робочий день\n'
        '/checkout - закінчити робочий день\n'
        '/status - переглянути свій статус\n'
        '/team - статус всієї команди\n'
        '/settings - вибрати стиль GIF',
        reply_markup=reply_markup
    )

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Налаштування стилю GIF"""
    keyboard = [
        [InlineKeyboardButton("🎨 Змінити GIF для Check-in", callback_data='choose_checkin')],
        [InlineKeyboardButton("🎨 Змінити GIF для Check-out", callback_data='choose_checkout')],
        [InlineKeyboardButton("🔙 Назад", callback_data='back_to_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = '⚙️ Налаштування\n\nОбери що хочеш змінити:'
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

async def choose_checkin_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір категорії для check-in"""
    keyboard = []
    for category in CHECKIN_CATEGORIES.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f'set_checkin_{category}')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='settings')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        '🎨 Обери стиль GIF для Check-in:',
        reply_markup=reply_markup
    )

async def choose_checkout_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Вибір категорії для check-out"""
    keyboard = []
    for category in CHECKOUT_CATEGORIES.keys():
        keyboard.append([InlineKeyboardButton(category, callback_data=f'set_checkout_{category}')])
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data='settings')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        '🎨 Обери стиль GIF для Check-out:',
        reply_markup=reply_markup
    )

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
    
    # Вибір GIF відповідно до налаштувань користувача
    if user_id in user_preferences and 'checkin_category' in user_preferences[user_id]:
        category = user_preferences[user_id]['checkin_category']
        gif_list = CHECKIN_CATEGORIES[category]
    else:
        # Випадкова категорія якщо не встановлено
        all_gifs = [gif for gifs in CHECKIN_CATEGORIES.values() for gif in gifs]
        gif_list = all_gifs
    
    gif_url = random.choice(gif_list)
    message = f"✅ {username} почав робочий день!\n⏰ Час: {current_time}\n\n💪 Продуктивної роботи!"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_animation(animation=gif_url, caption=message)
    else:
        await update.message.reply_animation(animation=gif_url, caption=message)

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
    
    # Розрахунок робочого часу
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
    
    # Вибір GIF відповідно до налаштувань користувача
    if user_id in user_preferences and 'checkout_category' in user_preferences[user_id]:
        category = user_preferences[user_id]['checkout_category']
        gif_list = CHECKOUT_CATEGORIES[category]
    else:
        # Випадкова категорія якщо не встановлено
        all_gifs = [gif for gifs in CHECKOUT_CATEGORIES.values() for gif in gifs]
        gif_list = all_gifs
    
    gif_url = random.choice(gif_list)
    message = (f"🚪 {username} закінчив робочий день!\n"
               f"⏰ Час виходу: {current_time}\n"
               f"⏱ Відпрацьовано: {hours}г {minutes}хв\n\n"
               f"👏 Чудова робота!")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_animation(animation=gif_url, caption=message)
    else:
        await update.message.reply_animation(animation=gif_url, caption=message)

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
    
    for user_id, data in user_status.items():
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
    user_id = update.effective_user.id
    
    if query.data == 'checkin':
        await checkin(update, context)
    elif query.data == 'checkout':
        await checkout(update, context)
    elif query.data == 'status':
        await status(update, context)
    elif query.data == 'settings':
        await settings(update, context)
    elif query.data == 'choose_checkin':
        await choose_checkin_category(update, context)
    elif query.data == 'choose_checkout':
        await choose_checkout_category(update, context)
    elif query.data.startswith('set_checkin_'):
        category = query.data.replace('set_checkin_', '')
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        user_preferences[user_id]['checkin_category'] = category
        await query.answer(f"✅ Встановлено: {category}")
        await settings(update, context)
    elif query.data.startswith('set_checkout_'):
        category = query.data.replace('set_checkout_', '')
        if user_id not in user_preferences:
            user_preferences[user_id] = {}
        user_preferences[user_id]['checkout_category'] = category
        await query.answer(f"✅ Встановлено: {category}")
        await settings(update, context)
    elif query.data == 'back_to_menu':
        keyboard = [
            [
                InlineKeyboardButton("✅ Check-in", callback_data='checkin'),
                InlineKeyboardButton("🚪 Check-out", callback_data='checkout')
            ],
            [
                InlineKeyboardButton("📊 Мій статус", callback_data='status'),
                InlineKeyboardButton("⚙️ Налаштування", callback_data='settings')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.answer()
        await query.edit_message_text('👋 Головне меню:', reply_markup=reply_markup)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник помилок"""
    logger.error(f"Update {update} caused error {context.error}")

def main():
    """Запуск бота"""
    # Отримуємо токен з змінної середовища
    TOKEN = os.getenv('BOT_TOKEN')
    
    if not TOKEN:
        logger.error("BOT_TOKEN не знайдено! Додай змінну середовища BOT_TOKEN")
        return
    
    # Створюємо додаток
    application = Application.builder().token(TOKEN).build()
    
    # Додавання обробників команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("checkout", checkout))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("team", team_status))
    application.add_handler(CommandHandler("settings", settings))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Додаємо обробник помилок
    application.add_error_handler(error_handler)
    
    logger.info("🤖 Бот запущено!")
    print
