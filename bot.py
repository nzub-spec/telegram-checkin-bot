import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Простий HTTP сервер для Render
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Вимикаємо логи HTTP

def run_http_server():
    port = int(os.getenv('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    print(f"HTTP server on port {port}")
    server.serve_forever()

# Зберігання статусу користувачів
user_status = {}

# Рівні завантаження
WORKLOAD = {
    '🟢': 'Потрібні задачі',
    '🟡': 'Середня завантаженість', 
    '🔴': 'Завантаженість до пенсії'
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Головне меню"""
    keyboard = [
        [InlineKeyboardButton("✅ Check-in", callback_data='checkin')],
        [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')],
        [InlineKeyboardButton("👥 Команда", callback_data='team')]
    ]
    # Видаляємо попереднє меню якщо є
    try:
        await update.message.delete()
    except:
        pass
    
    await update.message.reply_text(
        '👋 Привіт! Бот для відмітки робочого часу.',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkin - одразу чекін без вибору"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    # Видаляємо команду
    try:
        await update.message.delete()
    except:
        pass
    
    if user_id in user_status and user_status[user_id]['active']:
        await update.message.reply_text("❗ Ти вже на роботі!")
        return
    
    # Чекін без завантаження
    user_status[user_id] = {
        'active': True,
        'username': username,
        'workload': None
    }
    
    await update.message.reply_text(
        f"✅ {username} почав робочий день!\n\n"
        f"💪 Продуктивної роботи!"
    )

async def checkout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /checkout"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    # Видаляємо команду
    try:
        await update.message.delete()
    except:
        pass
    
    if user_id not in user_status or not user_status[user_id]['active']:
        await update.message.reply_text("❗ Спочатку зроби check-in!")
        return
    
    user_status[user_id]['active'] = False
    
    await update.message.reply_text(
        f"🚪 {username} закінчив робочий день!\n\n"
        f"👏 Чудова робота!"
    )

async def team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /team"""
    # Видаляємо команду
    try:
        await update.message.delete()
    except:
        pass
    
    if not user_status:
        msg = "📊 Немає даних"
    else:
        online = []
        for d in user_status.values():
            if d['active']:
                if d.get('workload'):
                    online.append(f"{d['workload']} {d['username']} - {WORKLOAD[d['workload']]}")
                else:
                    online.append(f"✅ {d['username']}")
        
        offline = [f"⭕ {d['username']}" 
                   for d in user_status.values() if not d['active']]
        
        msg = "👥 Статус команди:\n\n"
        if online:
            msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
        if offline:
            msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    await update.message.reply_text(msg)

async def show_workload(update: Update):
    """Показати вибір завантаження"""
    keyboard = [
        [InlineKeyboardButton("🟢 Потрібні задачі", callback_data='work_🟢')],
        [InlineKeyboardButton("🟡 Середня завантаженість", callback_data='work_🟡')],
        [InlineKeyboardButton("🔴 Завантаженість до пенсії", callback_data='work_🔴')]
    ]
    await update.callback_query.answer()
    # Видаляємо меню
    try:
        await update.callback_query.message.delete()
    except:
        pass
    # Відправляємо нове
    await update.callback_query.message.reply_text(
        '📊 Обери рівень завантаження:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def checkin(update: Update, workload: str):
    """Check-in з рівнем завантаження (через кнопку)"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id in user_status and user_status[user_id]['active']:
        await update.callback_query.answer("Вже на роботі!")
        return
    
    user_status[user_id] = {
        'active': True,
        'username': username,
        'workload': workload
    }
    
    await update.callback_query.answer("✅ Check-in!")
    
    # Видаляємо меню вибору
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    # Відправляємо підтвердження з завантаженістю
    await update.callback_query.message.reply_text(
        f"✅ {username} почав робочий день!\n"
        f"{workload} {WORKLOAD[workload]}\n\n"
        f"💪 Продуктивної роботи!"
    )

async def checkout(update: Update):
    """Check-out (через кнопку)"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id]['active']:
        await update.callback_query.answer("Спочатку check-in!")
        return
    
    user_status[user_id]['active'] = False
    
    await update.callback_query.answer("✅ Check-out!")
    
    # Видаляємо меню
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    await update.callback_query.message.reply_text(
        f"🚪 {username} закінчив робочий день!\n\n"
        f"👏 Чудова робота!"
    )

async def team(update: Update):
    """Статус команди (через кнопку)"""
    if not user_status:
        msg = "📊 Немає даних"
    else:
        online = []
        for d in user_status.values():
            if d['active']:
                if d.get('workload'):
                    online.append(f"{d['workload']} {d['username']} - {WORKLOAD[d['workload']]}")
                else:
                    online.append(f"✅ {d['username']}")
        
        offline = [f"⭕ {d['username']}" 
                   for d in user_status.values() if not d['active']]
        
        msg = "👥 Статус команди:\n\n"
        if online:
            msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
        if offline:
            msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    await update.callback_query.answer()
    
    # Видаляємо меню
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    await update.callback_query.message.reply_text(msg)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок"""
    data = update.callback_query.data
    
    if data == 'checkin':
        await show_workload(update)
    elif data.startswith('work_'):
        workload = data.split('_')[1]
        await checkin(update, workload)
    elif data == 'checkout':
        await checkout(update)
    elif data == 'team':
        await team(update)

def main():
    """Запуск бота"""
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ Додай BOT_TOKEN!")
        return
    
    # Запускаємо HTTP сервер в окремому потоці
    Thread(target=run_http_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(CommandHandler("team", team_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
