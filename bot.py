import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from datetime import datetime, timedelta # Імпортуємо timedelta
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

# --- ОНОВЛЕНІ КОНСТАНТИ ---
# Використовуємо словники для зручності вибору
CHECKIN_GIFS = {
    'gif_ci_1': "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif", # Продуктивний старт
    'gif_ci_2': "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif", # Готовність
    'gif_ci_3': "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif", # Кава-пауза
    'gif_ci_4': "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif", # Робочий стіл
}

CHECKOUT_GIFS = {
    'gif_co_1': "https://media.giphy.com/media/lD76yTC5zxZPG/giphy.gif",
    'gif_co_2': "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    'gif_co_3': "https://media.giphy.com/media/KB8C86UMgLDThpt4WT/giphy.gif",
    'gif_co_4': "https://media.giphy.com/media/l3q2Z6S6n38zjPswo/giphy.gif",
}
# -------------------------

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
        '/status - переглянути свій статус\n'
        '/team - статус команди',
        reply_markup=reply_markup
    )

# --- НОВА ДОПОМІЖНА ФУНКЦІЯ: Запит вибору GIF ---
async def _request_gif_choice(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Створює клавіатуру для вибору GIF-файлу."""
    
    gifs = CHECKIN_GIFS if action == 'checkin' else CHECKOUT_GIFS
    
    keyboard = []
    
    for i, (key, url) in enumerate(gifs.items()):
        # Формат callback_data: 'checkin_gif_gif_ci_1'
        callback_data = f'{action}_gif_{key}' 
        # Додаємо кнопку, де можна побачити номер GIF
        keyboard.append([InlineKeyboardButton(f"🖼️ GIF {i+1}", callback_data=callback_data)])
        
    reply_markup = InlineKeyboardMarkup(keyboard)

    message_text = "👆 Оберіть GIF-файл для вашої відмітки:"
    
    # Визначаємо, як відповісти: через команду чи через кнопку
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)

# --- НОВА ДОПОМІЖНА ФУНКЦІЯ: Виконання Check-in/Check-out ---
async def _execute_check(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str, gif_key: str):
    """Виконує фактичний check-in або check-out з обраним GIF."""
    
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    username = query.from_user.first_name
    
    current_time = datetime.now()
    time_str = current_time.strftime("%H:%M:%S")

    # Редагуємо повідомлення про вибір GIF, щоб показати прогрес
    await query.edit_message_text(f"⏳ Обробка вашої відмітки...")
    
    if action == 'checkin':
        # Логіка Check-in
        user_status[user_id] = {
            'checked_in': True,
            'checkin_time': time_str,
            'checkin_dt': current_time, # Зберігаємо повний datetime для точного розрахунку
            'username': username
        }
        
        checkin_history.append({
            'user': username, 'action': 'check-in', 'time': time_str, 'date': current_time.strftime("%d.%m.%Y")
        })
        
        gif_url = CHECKIN_GIFS.get(gif_key)
        message = f"✅ {username} почав робочий день!\n⏰ Час: {time_str}\n\n💪 Продуктивної роботи!"
        
    elif action == 'checkout':
        # Логіка Check-out
        if user_id not in user_status or not user_status[user_id].get('checked_in'):
            # Запобіжник на випадок, якщо статус змінився до натискання кнопки
            await query.edit_message_text(f"❗ {username}, ти вже вийшов або не зачекінився!")
            return
            
        checkin_dt = user_status[user_id]['checkin_dt']
        
        # Розрахунок робочого часу (використовуємо повні datetime об'єкти)
        work_duration = current_time - checkin_dt
        
        hours, remainder = divmod(work_duration.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        user_status[user_id]['checked_in'] = False
        
        checkin_history.append({
            'user': username, 'action': 'check-out', 'time': time_str, 'date': current_time.strftime("%d.%m.%Y")
        })
        
        gif_url = CHECKOUT_GIFS.get(gif_key)
        message = (f"🚪 {username} закінчив робочий день!\n"
                   f"⏰ Час виходу: {time_str}\n"
                   f"⏱ Відпрацьовано: {int(hours)}г {int(minutes)}хв\n\n"
                   f"👏 Чудова робота!")

    # Відправляємо GIF та повідомлення
    await query.message.reply_animation(animation=gif_url, caption=message)

# --- ОНОВЛЕНІ ФУНКЦІЇ: Ініціюють вибір GIF ---
async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkin або кнопка check-in - ініціює вибір GIF."""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id in user_status and user_status[user_id].get('checked_in'):
        message = f"❗ {username}, ти вже зачекінився о {user_status[user_id]['checkin_time']}"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return
        
    # Якщо ще не зачекінився, просимо обрати GIF
    await _request_gif_choice(update, context, 'checkin')

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkout або кнопка check-out - ініціює вибір GIF."""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id].get('checked_in'):
        message = f"❗ {username}, ти ще не зачекінився!"
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.message.reply_text(message)
        else:
            await update.message.reply_text(message)
        return
        
    # Якщо зачекінився, просимо обрати GIF
    await _request_gif_choice(update, context, 'checkout')
# ----------------------------------------------


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /status або кнопка статусу"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    # Змінено перевірку на використання .get() для безпеки
    if user_id not in user_status or not user_status[user_id].get('checked_in'):
        message = f"📊 {username}, ти зараз не на роботі.\n\nВикористай /checkin щоб почати робочий день!"
    else:
        # Використовуємо збережений повний datetime об'єкт для точного розрахунку
        checkin_time_str = user_status[user_id]['checkin_time']
        checkin_dt = user_status[user_id]['checkin_dt']
        current_time = datetime.now()
        
        work_duration = current_time - checkin_dt
        
        # Використовуємо .total_seconds() для коректного розрахунку різниці datetime
        hours, remainder = divmod(work_duration.total_seconds(), 3600)
        minutes, _ = divmod(remainder, 60)
        
        message = (f"📊 Статус: {username}\n\n"
                   f"✅ Ти на роботі\n"
                   f"⏰ Check-in: {checkin_time_str}\n"
                   f"⏱ Працюєш вже: {int(hours)}г {int(minutes)}хв")
    
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
        if data.get('checked_in'):
            # Розрахунок поточної тривалості для онлайну
            checkin_dt = data.get('checkin_dt', datetime.now())
            work_duration = datetime.now() - checkin_dt
            hours, remainder = divmod(work_duration.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)

            online.append(f"✅ {data['username']} (з {data['checkin_time']} | {int(hours)}г {int(minutes)}хв)")
        else:
            offline.append(f"⭕ {data['username']}")
    
    message = "👥 Статус команди:\n\n"
    
    if online:
        message += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
    
    if offline:
        message += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    await update.message.reply_text(message)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробник натискань на кнопки, включаючи вибір GIF"""
    query = update.callback_query
    data = query.data
    
    if data == 'checkin':
        # Ініціює вибір GIF для Check-in (викликає _request_gif_choice)
        await checkin(update, context)
    elif data == 'checkout':
        # Ініціює вибір GIF для Check-out (викликає _request_gif_choice)
        await checkout(update, context)
    elif data == 'status':
        await status(update, context)
    
    # --- ЛОГІКА ОБРОБКИ ВИБОРУ GIF ---
    # Формат даних: 'checkin_gif_gif_ci_1' або 'checkout_gif_gif_co_2'
    elif data.startswith('checkin_gif_') or data.startswith('checkout_gif_'):
        parts = data.split('_') 
        action = parts[0]       # 'checkin' або 'checkout'
        gif_key = parts[2]      # 'gif_ci_1' або 'gif_co_2'

        await _execute_check(update, context, action, gif_key)

def main():
    """Запуск бота"""
    # Вставте свій токен від @BotFather
    TOKEN = os.getenv('BOT_TOKEN')

    if not TOKEN:
        raise ValueError("BOT_TOKEN не знайдено. Переконайтеся, що ви встановили змінну середовища BOT_TOKEN.")

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
