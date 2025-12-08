import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime
import random
import os

# Налаштування логування
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Зберігання даних користувачів (у продакшені використовуй БД)
user_status = {}
checkin_history = []

# URL картинок та гіфок для чекіну
CHECKIN_IMAGES = [
    "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif",
    "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
]

# URL картинок та гіфок для вичекіну
CHECKOUT_IMAGES = [
    "https://media.giphy.com/media/lD76yTC5zxZPG/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/KB8C86UMgLDThpt4WT/giphy.gif",
    "https://media.giphy.com/media/l3q2Z6S6n38zjPswo/giphy.gif",
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Check-in", callback_data='checkin'),
            InlineKeyboardButton("🚪 Check-out", callback_data='checkout')
        ],
        [InlineKeyboardButton("📊 Мій статус", callback_data='status')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        '👋 Привіт! Я бот для відмітки робочого часу.\n\n'
        'Використовуй кнопки нижче або команди:\n'
        '/checkin - почати робочий день\n'
        '/checkout - закінчити робочий день\n'
        '/status - переглянути свій статус',
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
    
    gif_url = random.choice(CHECKIN_IMAGES)
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
    
    gif_url = random.choice(CHECKOUT_IMAGES)
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
    
    if query.data == 'checkin':
        await checkin(update, context)
    elif query.data == 'checkout':
        await checkout(update, context)
    elif query.data == 'status':
        await status(update, context)

def main():
    """Запуск бота"""
    # Вставте свій токен від @BotFather
    import os
    TOKEN = os.getenv('BOT_TOKEN')
    
    application = Application.builder().token(TOKEN).build()
    
    # Додавання обробників команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("checkin", checkin))
    application.add_handler(CommandHandler("checkout", checkout))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("team", team_status))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 Бот запущено!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
