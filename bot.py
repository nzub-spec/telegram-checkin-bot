import logging
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from datetime import datetime
from threading import Thread
from typing import Dict
import random

# Flask для Render
try:
    from flask import Flask
    import requests
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False

# Налаштування
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Константи
CHOOSING_CHECKIN_MEDIA, CHOOSING_CHECKOUT_MEDIA = range(2)

# Рівні завантаження
WORKLOAD_LEVELS = {
    '🟢': 'Потрібні задачі',
    '🟡': 'Середня завантаженість',
    '🔴': 'Завантаженість до пенсії'
}

DEFAULT_CHECKIN = [
    {"type": "animation", "content": "https://media.giphy.com/media/BwzYkApdxCU/giphy.gif"},
    {"type": "text", "content": "Доброго ранку! ☀️"},
    {"type": "text", "content": "Готовий до роботи! 💪"},
]

DEFAULT_CHECKOUT = [
    {"type": "text", "content": "До завтра 👋"},
    {"type": "text", "content": "До понеділка 🎉"},
    {"type": "text", "content": "Гарного вечора! 🌙"},
]

# Глобальне сховище
user_status: Dict = {}
user_media: Dict = {}

# Flask setup
if FLASK_AVAILABLE:
    app = Flask(__name__)
    
    @app.route('/')
    def home(): return "🤖 Bot running!"
    
    @app.route('/health')
    def health(): return "OK", 200
    
    def run_flask():
        app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
    
    def keep_alive():
        """Пінг себе кожні 14 хвилин"""
        import time
        url = os.environ.get('RENDER_EXTERNAL_URL')
        if url:
            while True:
                time.sleep(840)
                try:
                    requests.get(f"{url}/health", timeout=5)
                    logger.info("🏓 Keep-alive ping")
                except Exception as e:
                    logger.error(f"Keep-alive error: {e}")
else:
    def run_flask(): pass
    def keep_alive(): pass

def get_media(user_id: int) -> Dict:
    """Отримати медіа користувача"""
    if user_id not in user_media:
        user_media[user_id] = {'checkin': DEFAULT_CHECKIN.copy(), 'checkout': DEFAULT_CHECKOUT.copy()}
    return user_media[user_id]

def create_keyboard(buttons) -> InlineKeyboardMarkup:
    """Створити клавіатуру"""
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data) for text, data in row] for row in buttons])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Головне меню"""
    keyboard = create_keyboard([
        [("✅ Check-in", 'checkin'), ("🚪 Check-out", 'checkout')],
        [("📊 Мій статус", 'status'), ("👥 Команда", 'team')],
        [("🎨 Налаштувати медіа", 'settings')]
    ])
    await update.message.reply_text(
        '👋 Привіт! Бот для відмітки робочого часу.\n\n'
        '📝 Команди:\n'
        '/checkin - почати день\n'
        '/checkout - закінчити день\n'
        '/status - мій статус\n'
        '/team - статус команди\n'
        '/settings - налаштування',
        reply_markup=keyboard
    )

async def show_workload_selection(update: Update, action: str):
    """Показати вибір рівня завантаження"""
    keyboard = create_keyboard([
        [("🟢 Потрібні задачі", f'{action}_workload_🟢')],
        [("🟡 Середня завантаженість", f'{action}_workload_🟡')],
        [("🔴 Завантаженість до пенсії", f'{action}_workload_🔴')],
        [("⬅️ Назад", 'back_to_main')]
    ])
    
    msg = f"📊 Обери рівень завантаження для {action}:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(msg, reply_markup=keyboard)
    else:
        await update.message.reply_text(msg, reply_markup=keyboard)

async def send_media(query, media_item: dict, caption: str):
    """Відправити медіа будь-якого типу"""
    try:
        media_type = media_item.get("type", "text")
        content = media_item.get("content", "")
        
        if media_type == "text":
            # Якщо це текст - додаємо до caption
            full_message = f"{caption}\n\n💬 {content}"
            await query.message.reply_text(full_message)
        elif media_type == "animation":
            # Гіфка
            await query.message.reply_animation(animation=content, caption=caption)
        elif media_type == "photo":
            # Фото
            await query.message.reply_photo(photo=content, caption=caption)
        elif media_type == "video":
            # Відео
            await query.message.reply_video(video=content, caption=caption)
        else:
            # Якщо невідомий тип - просто текст
            await query.message.reply_text(caption)
    except Exception as e:
        logger.error(f"Помилка відправки медіа: {e}")
        # Якщо не вдалося відправити медіа - відправляємо текст
        await query.message.reply_text(caption)
    """Check-in з рівнем завантаження"""
    query = update.callback_query
    
    if user_id in user_status and user_status[user_id].get('checked_in'):
        await query.answer("Вже зачекінений!")
        await query.message.reply_text(f"❗ {username}, ти вже на роботі!")
        return
    
    user_status[user_id] = {
        'checked_in': True,
        'username': username,
        'workload': workload,
        'workload_text': WORKLOAD_LEVELS[workload]
    }
    
    media = get_media(user_id)['checkin']
    selected = random.choice(media)
    
    msg = (f"✅ {username} почав робочий день!\n"
           f"{workload} Рівень: {WORKLOAD_LEVELS[workload]}\n\n"
           f"💪 Продуктивної роботи!")
    
    await query.answer(f"✅ Check-in: {WORKLOAD_LEVELS[workload]}")
    
    try:
        await query.message.reply_animation(animation=selected, caption=msg)
    except:
        await query.message.reply_text(msg)

async def checkout(update: Update, user_id: int, username: str, workload: str):
    """Check-out з рівнем завантаження"""
    query = update.callback_query
    
    if user_id not in user_status or not user_status[user_id].get('checked_in'):
        await query.answer("Спочатку check-in!")
        await query.message.reply_text(f"❗ {username}, спочатку зробіть check-in!")
        return
    
    checkin_workload = user_status[user_id].get('workload', '🟡')
    user_status[user_id]['checked_in'] = False
    user_status[user_id]['checkout_workload'] = workload
    user_status[user_id]['checkout_workload_text'] = WORKLOAD_LEVELS[workload]
    
    media = get_media(user_id)['checkout']
    selected = random.choice(media)
    
    msg = (f"🚪 {username} закінчив робочий день!\n\n"
           f"📊 Завантаженість:\n"
           f"  Початок дня: {checkin_workload} {WORKLOAD_LEVELS[checkin_workload]}\n"
           f"  Кінець дня: {workload} {WORKLOAD_LEVELS[workload]}\n\n"
           f"👏 Чудова робота!")
    
    await query.answer(f"✅ Check-out: {WORKLOAD_LEVELS[workload]}")
    await send_media(query, selected, msg)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус користувача"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id].get('checked_in'):
        msg = f"📊 {username}, ти не на роботі\n\nВикористай /checkin"
    else:
        workload = user_status[user_id].get('workload', '🟡')
        workload_text = user_status[user_id].get('workload_text', 'Середня')
        msg = (f"📊 Статус: {username}\n\n"
               f"✅ На роботі\n"
               f"{workload} Завантаженість: {workload_text}")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)

async def team_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Статус команди"""
    if not user_status:
        msg = "📊 Немає даних про команду"
    else:
        online = []
        offline = []
        
        for uid, data in user_status.items():
            name = data.get('username', 'User')
            if data.get('checked_in'):
                workload = data.get('workload', '🟡')
                workload_text = data.get('workload_text', 'Середня')
                online.append(f"{workload} {name} - {workload_text}")
            else:
                offline.append(f"⭕ {name}")
        
        msg = "👥 Статус команди:\n\n"
        if online:
            msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
        if offline:
            msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)

async def settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню налаштувань"""
    user_id = update.effective_user.id
    media = get_media(user_id)
    
    keyboard = create_keyboard([
        [("➕ Додати check-in медіа", 'add_checkin')],
        [("➕ Додати check-out медіа", 'add_checkout')],
        [("📋 Переглянути медіа", 'view_media')],
        [("🔄 Скинути до стандартних", 'reset_media')],
        [("⬅️ Назад", 'back_to_main')]
    ])
    
    msg = (f"🎨 Налаштування медіа\n\n"
           f"✅ Check-in: {len(media['checkin'])} файлів\n"
           f"🚪 Check-out: {len(media['checkout'])} файлів")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.edit_text(msg, reply_markup=keyboard)
    else:
        await update.message.reply_text(msg, reply_markup=keyboard)

async def view_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Переглянути медіа"""
    media = get_media(update.effective_user.id)
    
    type_emoji = {
        "text": "💬",
        "photo": "🖼",
        "animation": "🎬",
        "video": "🎥"
    }
    
    msg = "📋 Твої медіа:\n\n✅ Check-in:\n"
    for i, item in enumerate(media['checkin'], 1):
        emoji = type_emoji.get(item.get("type", "text"), "📎")
        content = item.get("content", "")
        preview = content[:40] + "..." if len(content) > 40 else content
        msg += f"{i}. {emoji} {preview}\n"
    
    msg += "\n🚪 Check-out:\n"
    for i, item in enumerate(media['checkout'], 1):
        emoji = type_emoji.get(item.get("type", "text"), "📎")
        content = item.get("content", "")
        preview = content[:40] + "..." if len(content) > 40 else content
        msg += f"{i}. {emoji} {preview}\n"
    
    await update.callback_query.answer()
    await update.callback_query.message.reply_text(msg)

async def add_media_start(update: Update, media_type: str):
    """Початок додавання медіа"""
    msg = (f"📸 Додавання {media_type} медіа\n\n"
           "Надішли:\n"
           "💬 Текст (буде показано як повідомлення)\n"
           "🖼 Фото\n"
           "🎬 Гіфку\n"
           "🎥 Відео\n"
           "🔗 URL на медіа\n\n"
           "/done - завершити\n"
           "/cancel - скасувати")
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    else:
        await update.message.reply_text(msg)
    
    return CHOOSING_CHECKIN_MEDIA if media_type == 'checkin' else CHOOSING_CHECKOUT_MEDIA

async def receive_media(update: Update, media_type: str):
    """Отримати медіа будь-якого типу"""
    user_id = update.effective_user.id
    media_list = get_media(user_id)[media_type]
    
    media_item = None
    
    # Якщо це текст
    if update.message.text:
        text = update.message.text.strip()
        if text.startswith('http'):
            # URL - визначаємо тип
            if any(ext in text.lower() for ext in ['.gif', 'giphy.com', 'tenor.com']):
                media_item = {"type": "animation", "content": text}
            elif any(ext in text.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                media_item = {"type": "photo", "content": text}
            elif any(ext in text.lower() for ext in ['.mp4', '.mov', 'youtube.com', 'youtu.be']):
                media_item = {"type": "video", "content": text}
            else:
                media_item = {"type": "animation", "content": text}  # За замовчуванням гіфка
        else:
            # Звичайний текст
            media_item = {"type": "text", "content": text}
    
    # Якщо це фото
    elif update.message.photo:
        media_item = {"type": "photo", "content": update.message.photo[-1].file_id}
    
    # Якщо це гіфка/анімація
    elif update.message.animation:
        media_item = {"type": "animation", "content": update.message.animation.file_id}
    
    # Якщо це відео
    elif update.message.video:
        media_item = {"type": "video", "content": update.message.video.file_id}
    
    if media_item:
        media_list.append(media_item)
        type_emoji = {
            "text": "💬",
            "photo": "🖼",
            "animation": "🎬",
            "video": "🎥"
        }
        emoji = type_emoji.get(media_item["type"], "📎")
        await update.message.reply_text(
            f"✅ {emoji} Додано!\n"
            f"Всього: {len(media_list)} медіа\n"
            f"/done щоб завершити"
        )
    else:
        await update.message.reply_text(
            "❌ Надішли:\n"
            "• 💬 Текст\n"
            "• 🖼 Фото\n"
            "• 🎬 Гіфку\n"
            "• 🎥 Відео\n"
            "• 🔗 URL на медіа"
        )
    
    return CHOOSING_CHECKIN_MEDIA if media_type == 'checkin' else CHOOSING_CHECKOUT_MEDIA

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка кнопок"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if data == 'checkin':
        await show_workload_selection(update, 'checkin')
    elif data == 'checkout':
        await show_workload_selection(update, 'checkout')
    elif data.startswith('checkin_workload_'):
        workload = data.split('_')[-1]
        await checkin(update, user_id, username, workload)
    elif data.startswith('checkout_workload_'):
        workload = data.split('_')[-1]
        await checkout(update, user_id, username, workload)
    elif data == 'status':
        await status(update, context)
    elif data == 'team':
        await team_status(update, context)
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
        await query.message.reply_text("✅ Медіа скинуто")
    elif data == 'back_to_main':
        keyboard = create_keyboard([
            [("✅ Check-in", 'checkin'), ("🚪 Check-out", 'checkout')],
            [("📊 Мій статус", 'status'), ("👥 Команда", 'team')],
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
        Thread(target=keep_alive, daemon=True).start()
        logger.info("Flask + Keep-alive запущено!")
    
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
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, lambda u, c: receive_media(u, 'checkin')),
                CommandHandler("done", lambda u, c: (u.message.reply_text("✅ Збережено!"), ConversationHandler.END)[1]),
            ],
            CHOOSING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: receive_media(u, 'checkout')),
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, lambda u, c: receive_media(u, 'checkout')),
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
