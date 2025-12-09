import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime
from threading import Thread
from typing import Dict, List

# Flask для Render
try:
    from flask import Flask
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Налаштування
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Константи
CHOOSING_CHECKIN_MEDIA, CHOOSING_CHECKOUT_MEDIA = range(2)
DEFAULT_CHECKIN = [
    "https://media.giphy.com/media/3ornka9rAaKRA2Rkac/giphy.gif",
    "https://media.giphy.com/media/g9582DNuQppxC/giphy.gif",
    "https://media.giphy.com/media/l0MYt5jPR6QX5pnqM/giphy.gif",
    "https://media.giphy.com/media/xT0xeJpnrWC4XWblEk/giphy.gif",
]
DEFAULT_CHECKOUT = [
    "https://media.giphy.com/media/lD76yTC5zxZPG/giphy.gif",
    "https://media.giphy.com/media/3o6Zt6ML6BklcajjsA/giphy.gif",
    "https://media.giphy.com/media/KB8C86UMgLDThpt4WT/giphy.gif",
    "https://media.giphy.com/media/l3q2Z6S6n38zjPswo/giphy.gif",
]

# Глобальне сховище
user_status: Dict = {}
user_media: Dict = {}
user_selected_media: Dict = {}

# Flask setup
if FLASK_AVAILABLE:
    app = Flask(__name__)
    @app.route('/')
    def home(): return "🤖 Bot running!"
    @app.route('/health')
    def health(): return "OK", 200
    def run_flask():
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
else:
    def run_flask(): pass

def get_media(user_id: int) -> Dict[str, List[str]]:
    """Отримати медіа користувача"""
    if user_id not in user_media:
        user_media[user_id] = {'checkin': DEFAULT_CHECKIN.copy(), 'checkout': DEFAULT_CHECKOUT.copy()}
    return user_media[user_id]

def create_keyboard(buttons: List[List[tuple]]) -> InlineKeyboardMarkup:
    """Створити клавіатуру з кнопок"""
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data) for text, data in row] for row in buttons])

async def send_or_edit(update: Update, text: str, keyboard: InlineKeyboardMarkup = None):
    """Відправити або редагувати повідомлення"""
    if update.callback_query:
        await update.callback_query.answer()
        if keyboard:
            await update.callback_query.message.edit_text(text, reply_markup=keyboard)
        else:
            await update.callback_query.message.reply_text(text)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Головне меню"""
    keyboard = create_keyboard([
        [("✅ Check-in", 'choose_checkin'), ("🚪 Check-out", 'choose_checkout')],
        [("📊 Мій статус", 'status')],
        [("🎨 Налаштувати медіа", 'settings')]
    ])
    await update.message.reply_text(
        '👋 Привіт! Бот для відмітки робочого часу.\n\n'
        '📝 Команди:\n/checkin /checkout /status /team\n'
        '/settings /add_checkin_media /add_checkout_media /reset_media',
        reply_markup=keyboard
    )

async def show_media_selection(update: Update, user_id: int, media_type: str):
    """Показати вибір медіа"""
    media = get_media(user_id)[media_type]
    buttons = [[(f"🎬 Гіфка #{i+1}", f'{media_type}_media_{i}')] for i in range(min(10, len(media)))]
    buttons.append([("⬅️ Назад", 'back_to_main')])
    
    await send_or_edit(
        update,
        f"🎬 Обери гіфку для {media_type}:\n\nВсього: {len(media)} гіфок",
        create_keyboard(buttons)
    )

async def preview_media(update: Update, user_id: int, media_type: str, index: int):
    """Показати превʼю та підтвердження"""
    query = update.callback_query
    username = update.effective_user.first_name
    
    # Перевірки
    if media_type == 'checkin' and user_id in user_status and user_status[user_id].get('checked_in'):
        await query.answer()
        await query.message.reply_text(f"❗ {username}, ти вже зачекінився!")
        return
    elif media_type == 'checkout' and (user_id not in user_status or not user_status[user_id].get('checked_in')):
        await query.answer()
        await query.message.reply_text(f"❗ {username}, спочатку зробіть check-in!")
        return
    
    media = get_media(user_id)[media_type][index]
    user_selected_media[user_id] = {media_type: media}
    
    keyboard = create_keyboard([
        [(f"✅ Підтвердити", f'confirm_{media_type}')],
        [("🔄 Обрати іншу", f'choose_{media_type}')],
        [("❌ Скасувати", 'back_to_main')]
    ])
    
    await query.answer()
    try:
        await query.message.reply_animation(
            animation=media,
            caption=f"🎬 Превʼю для {media_type}\n\nПідтверджуєш?",
            reply_markup=keyboard
        )
    except:
        await query.message.reply_text(f"🎬 Гіфка вибрана!\n\nПідтверджуєш?", reply_markup=keyboard)

async def confirm_action(update: Update, user_id: int, action: str):
    """Підтвердити check-in/out"""
    query = update.callback_query
    username = update.effective_user.first_name
    now = datetime.now().strftime("%H:%M:%S")
    
    if action == 'checkin':
        if user_id in user_status and user_status[user_id].get('checked_in'):
            await query.answer("Вже зачекінений!")
            return
        
        user_status[user_id] = {'checked_in': True, 'checkin_time': now, 'username': username}
        msg = f"✅ {username} почав роботу!\n⏰ {now}\n\n💪 Продуктивної роботи!"
    
    else:  # checkout
        if user_id not in user_status or not user_status[user_id].get('checked_in'):
            await query.answer("Спочатку check-in!")
            return
        
        checkin = datetime.strptime(user_status[user_id]['checkin_time'], "%H:%M:%S")
        checkout = datetime.strptime(now, "%H:%M:%S")
        duration = checkout - checkin
        h, rem = divmod(duration.seconds, 3600)
        m, _ = divmod(rem, 60)
        
        user_status[user_id]['checked_in'] = False
        msg = f"🚪 {username} закінчив роботу!\n⏰ {now}\n⏱ Відпрацьовано: {h}г {m}хв\n\n👏 Чудова робота!"
    
    media = user_selected_media.get(user_id, {}).get(action)
    await query.answer(f"✅ {action.capitalize()} підтверджено!")
    
    try:
        if media:
            await query.message.reply_animation(animation=media, caption=msg)
        else:
            await query.message.reply_text(msg)
    except:
        await query.message.reply_text(msg)

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню налаштувань"""
    user_id = update.effective_user.id
    media = get_media(user_id)
    
    keyboard = create_keyboard([
        [("➕ Додати check-in", 'add_checkin')],
        [("➕ Додати check-out", 'add_checkout')],
        [("📋 Переглянути медіа", 'view_media')],
        [("🔄 Скинути", 'reset_media')],
        [("⬅️ Назад", 'back_to_main')]
    ])
    
    await send_or_edit(
        update,
        f"🎨 Налаштування медіа\n\n"
        f"✅ Check-in: {len(media['checkin'])} файлів\n"
        f"🚪 Check-out: {len(media['checkout'])} файлів",
        keyboard
    )

async def view_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переглянути медіа"""
    media = get_media(update.effective_user.id)
    msg = "📋 Твої медіа:\n\n✅ Check-in:\n"
    msg += "\n".join(f"{i+1}. {url[:50]}..." for i, url in enumerate(media['checkin']))
    msg += "\n\n🚪 Check-out:\n"
    msg += "\n".join(f"{i+1}. {url[:50]}..." for i, url in enumerate(media['checkout']))
    
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(msg)

async def add_media_start(update: Update, media_type: str):
    """Початок додавання медіа"""
    msg = (f"📸 Додавання {media_type} медіа\n\n"
           "Надішли URL, фото або гіфку\n"
           "/done - завершити, /cancel - скасувати")
    await send_or_edit(update, msg)
    return CHOOSING_CHECKIN_MEDIA if media_type == 'checkin' else CHOOSING_CHECKOUT_MEDIA

async def receive_media(update: Update, media_type: str):
    """Отримати медіа від користувача"""
    user_id = update.effective_user.id
    media = get_media(user_id)[media_type]
    
    if update.message.text and update.message.text.startswith('http'):
        media.append(update.message.text.strip())
        await update.message.reply_text(f"✅ Додано! Всього: {len(media)}\nНадішли ще або /done")
    elif update.message.photo:
        media.append(update.message.photo[-1].file_id)
        await update.message.reply_text(f"✅ Фото додано! Всього: {len(media)}\nНадішли ще або /done")
    elif update.message.animation:
        media.append(update.message.animation.file_id)
        await update.message.reply_text(f"✅ Гіфка додана! Всього: {len(media)}\nНадішли ще або /done")
    else:
        await update.message.reply_text("❌ Надішли URL, фото або гіфку")
    
    return CHOOSING_CHECKIN_MEDIA if media_type == 'checkin' else CHOOSING_CHECKOUT_MEDIA

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус користувача"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id].get('checked_in'):
        msg = f"📊 {username}, ти не на роботі\n\nВикористай /checkin"
    else:
        checkin = datetime.strptime(user_status[user_id]['checkin_time'], "%H:%M:%S")
        now = datetime.now()
        checkin = checkin.replace(year=now.year, month=now.month, day=now.day)
        duration = now - checkin
        h, rem = divmod(duration.seconds, 3600)
        m, _ = divmod(rem, 60)
        msg = f"📊 {username}\n\n✅ На роботі\n⏰ З {user_status[user_id]['checkin_time']}\n⏱ Працюєш: {h}г {m}хв"
    
    await send_or_edit(update, msg)

async def team_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус команди"""
    if not user_status:
        await update.message.reply_text("📊 Немає даних")
        return
    
    online = [f"✅ {d['username']} (з {d['checkin_time']})" for d in user_status.values() if d.get('checked_in')]
    offline = [f"⭕ {d['username']}" for d in user_status.values() if not d.get('checked_in')]
    
    msg = "👥 Статус команди:\n\n"
    if online: msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
    if offline: msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    await update.message.reply_text(msg)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка всіх кнопок"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    
    if data == 'choose_checkin':
        await show_media_selection(update, user_id, 'checkin')
    elif data == 'choose_checkout':
        await show_media_selection(update, user_id, 'checkout')
    elif data.startswith('checkin_media_'):
        await preview_media(update, user_id, 'checkin', int(data.split('_')[-1]))
    elif data.startswith('checkout_media_'):
        await preview_media(update, user_id, 'checkout', int(data.split('_')[-1]))
    elif data == 'confirm_checkin':
        await confirm_action(update, user_id, 'checkin')
    elif data == 'confirm_checkout':
        await confirm_action(update, user_id, 'checkout')
    elif data == 'status':
        await status(update, context)
    elif data == 'settings':
        await settings_menu(update, context)
    elif data == 'add_checkin':
        await add_media_start(update, 'checkin')
    elif data == 'add_checkout':
        await add_media_start(update, 'checkout')
    elif data == 'view_media':
        await view_media(update, context)
    elif data == 'reset_media':
        user_media[user_id] = {'checkin': DEFAULT_CHECKIN.copy(), 'checkout': DEFAULT_CHECKOUT.copy()}
        await query.answer("🔄 Скинуто!")
        await query.message.reply_text("✅ Медіа скинуто до стандартних")
    elif data == 'back_to_main':
        keyboard = create_keyboard([
            [("✅ Check-in", 'choose_checkin'), ("🚪 Check-out", 'choose_checkout')],
            [("📊 Мій статус", 'status')],
            [("🎨 Налаштувати медіа", 'settings')]
        ])
        await query.answer()
        await query.message.edit_text("👋 Головне меню:", reply_markup=keyboard)

def main():
    """Запуск"""
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        logger.error("BOT_TOKEN не знайдено!")
        return
    
    if FLASK_AVAILABLE:
        Thread(target=run_flask, daemon=True).start()
        logger.info("Flask запущено!")
    
    app = Application.builder().token(TOKEN).build()
    
    # Conversation handler
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("add_checkin_media", lambda u, c: add_media_start(u, 'checkin')),
            CommandHandler("add_checkout_media", lambda u, c: add_media_start(u, 'checkout')),
        ],
        states={
            CHOOSING_CHECKIN_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: receive_media(u, 'checkin')),
                MessageHandler(filters.PHOTO | filters.ANIMATION, lambda u, c: receive_media(u, 'checkin')),
                CommandHandler("done", lambda u, c: (u.message.reply_text("✅ Збережено!"), ConversationHandler.END)[1]),
            ],
            CHOOSING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: receive_media(u, 'checkout')),
                MessageHandler(filters.PHOTO | filters.ANIMATION, lambda u, c: receive_media(u, 'checkout')),
                CommandHandler("done", lambda u, c: (u.message.reply_text("✅ Збережено!"), ConversationHandler.END)[1]),
            ],
        },
        fallbacks=[CommandHandler("cancel", lambda u, c: (u.message.reply_text("❌ Скасовано"), ConversationHandler.END)[1])],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("team", team_status))
    app.add_handler(CommandHandler("settings", settings_menu))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(button_callback))
    
    logger.info("🤖 Бот запущено!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
