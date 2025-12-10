import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

ADDING_CHECKIN_MEDIA, ADDING_CHECKOUT_MEDIA = range(2)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'Bot running!')
    def log_message(self, format, *args):
        pass

def run_http():
    HTTPServer(('0.0.0.0', int(os.getenv('PORT', 10000))), SimpleHandler).serve_forever()

user_status = {}
user_media = {}
WORKLOAD = {'🟢': 'Потрібні задачі', '🟡': 'Середня завантаженість', '🔴': 'Завантаженість до пенсії'}

def get_media(user_id):
    if user_id not in user_media:
        user_media[user_id] = {'checkin': [], 'checkout': []}
    return user_media[user_id]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try: 
        await update.message.delete()
    except: 
        pass
    keyboard = [[InlineKeyboardButton("✅ Check-in", callback_data='checkin')], [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')], [InlineKeyboardButton("👥 Команда", callback_data='team')], [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]]
    await context.bot.send_message(chat_id=chat_id, text='👋 Бот для відмітки часу', reply_markup=InlineKeyboardMarkup(keyboard))

async def settings(update: Update):
    user_id = update.effective_user.id
    media = get_media(user_id)
    keyboard = [[InlineKeyboardButton("➕ Додати Check-in", callback_data='add_checkin')], [InlineKeyboardButton("➕ Додати Check-out", callback_data='add_checkout')], [InlineKeyboardButton("📋 Бібліотека", callback_data='view_lib')], [InlineKeyboardButton("🗑 Очистити Check-in", callback_data='clear_checkin')], [InlineKeyboardButton("🗑 Очистити Check-out", callback_data='clear_checkout')], [InlineKeyboardButton("⬅️ Назад", callback_data='back')]]
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    msg = f'🎨 Бібліотека:\n\n✅ Check-in: {len(media["checkin"])}\n🚪 Check-out: {len(media["checkout"])}'
    await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_checkin_library(update: Update):
    user_id = update.effective_user.id
    media = get_media(user_id)
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    if not media['checkin']:
        await update.callback_query.message.reply_text('📚 Бібліотека порожня!')
        return
    keyboard = []
    for i, item in enumerate(media['checkin'][:10]):
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'ci_{i}')])
        else:
            keyboard.append([InlineKeyboardButton(f"{emoji} Медіа #{i+1}", callback_data=f'ci_{i}')])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='checkin')])
    await update.callback_query.message.reply_text('📚 Обери Check-in:', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_checkout_library(update: Update):
    user_id = update.effective_user.id
    media = get_media(user_id)
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    if not media['checkout']:
        await update.callback_query.message.reply_text('📚 Бібліотека порожня!')
        return
    keyboard = []
    for i, item in enumerate(media['checkout'][:10]):
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'co_{i}')])
        else:
            keyboard.append([InlineKeyboardButton(f"{emoji} Медіа #{i+1}", callback_data=f'co_{i}')])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back')])
    await update.callback_query.message.reply_text('📚 Обери Check-out:', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_workload(update: Update):
    keyboard = [[InlineKeyboardButton("🟢 Потрібні задачі", callback_data='w_🟢')], [InlineKeyboardButton("🟡 Середня завантаженість", callback_data='w_🟡')], [InlineKeyboardButton("🔴 Завантаженість до пенсії", callback_data='w_🔴')], [InlineKeyboardButton("➡️ Пропустити", callback_data='w_skip')]]
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    await update.callback_query.message.reply_text('📊 Завантаженість:', reply_markup=InlineKeyboardMarkup(keyboard))

async def do_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE, media_idx: int, workload: str = None):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    if user_id in user_status and user_status[user_id]['active']:
        await update.callback_query.answer("Вже на роботі!")
        return
    user_status[user_id] = {'active': True, 'username': username, 'workload': workload}
    await update.callback_query.answer("✅ Check-in!")
    try: await update.callback_query.message.delete()
    except: pass
    msg = f"✅ {username} почав день!\n"
    if workload:
        msg += f"{workload} {WORKLOAD[workload]}\n"
    msg += "\n💪 Продуктивної роботи!"
    media = get_media(user_id)
    if media['checkin']:
        await send_media(update.callback_query.message, media['checkin'][media_idx], msg)
    else:
        await update.callback_query.message.reply_text(msg)

async def do_checkout(update: Update, media_idx: int):
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    if user_id not in user_status or not user_status[user_id]['active']:
        await update.callback_query.answer("Спочатку check-in!")
        return
    user_status[user_id]['active'] = False
    await update.callback_query.answer("✅ Check-out!")
    try: await update.callback_query.message.delete()
    except: pass
    msg = f"🚪 {username} закінчив день!\n\n👏 Чудова робота!"
    media = get_media(user_id)
    if media['checkout']:
        await send_media(update.callback_query.message, media['checkout'][media_idx], msg)
    else:
        await update.callback_query.message.reply_text(msg)

async def send_media(message, item, text):
    try:
        t = item['type']
        c = item['content']
        if t == 'text':
            await message.reply_text(f"{text}\n\n💬 {c}")
        elif t == 'photo':
            await message.reply_photo(photo=c, caption=text)
        elif t == 'animation':
            await message.reply_animation(animation=c, caption=text)
        elif t == 'video':
            await message.reply_video(video=c, caption=text)
    except:
        await message.reply_text(text)

async def team(update: Update):
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
        offline = [f"⭕ {d['username']}" for d in user_status.values() if not d['active']]
        msg = "👥 Команда:\n\n"
        if online: msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
        if offline: msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    await update.callback_query.message.reply_text(msg)

async def start_add_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    await update.callback_query.message.reply_text('📸 Надішли медіа:\n• 💬 Текст\n• 🖼 Фото\n• 🎬 Гіфку\n• 🎥 Відео\n\n/done - готово, /cancel - скасувати')
    return ADDING_CHECKIN_MEDIA

async def start_add_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    try: await update.callback_query.message.delete()
    except: pass
    await update.callback_query.message.reply_text('📸 Надішли медіа:\n• 💬 Текст\n• 🖼 Фото\n• 🎬 Гіфку\n• 🎥 Відео\n\n/done - готово, /cancel - скасувати')
    return ADDING_CHECKOUT_MEDIA

async def receive_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    media = get_media(user_id)
    if update.message.text:
        media['checkin'].append({'type': 'text', 'content': update.message.text})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
    elif update.message.photo:
        media['checkin'].append({'type': 'photo', 'content': update.message.photo[-1].file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
    elif update.message.animation:
        media['checkin'].append({'type': 'animation', 'content': update.message.animation.file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
    elif update.message.video:
        media['checkin'].append({'type': 'video', 'content': update.message.video.file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
    return ADDING_CHECKIN_MEDIA

async def receive_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    media = get_media(user_id)
    if update.message.text:
        media['checkout'].append({'type': 'text', 'content': update.message.text})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkout"])}')
    elif update.message.photo:
        media['checkout'].append({'type': 'photo', 'content': update.message.photo[-1].file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkout"])}')
    elif update.message.animation:
        media['checkout'].append({'type': 'animation', 'content': update.message.animation.file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkout"])}')
    elif update.message.video:
        media['checkout'].append({'type': 'video', 'content': update.message.video.file_id})
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkout"])}')
    return ADDING_CHECKOUT_MEDIA

async def done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('✅ Збережено!')
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('❌ Скасовано')
    return ConversationHandler.END

async def buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = update.callback_query.data
    if data in ['add_checkin', 'add_checkout']:
        return
    if data == 'checkin':
        await show_checkin_library(update)
    elif data.startswith('ci_'):
        idx = int(data[3:])
        context.user_data['ci_idx'] = idx
        await show_workload(update)
    elif data.startswith('w_'):
        idx = context.user_data.get('ci_idx', 0)
        workload = None if data == 'w_skip' else data[2:]
        await do_checkin(update, context, idx, workload)
    elif data == 'checkout':
        await show_checkout_library(update)
    elif data.startswith('co_'):
        idx = int(data[3:])
        await do_checkout(update, idx)
    elif data == 'team':
        await team(update)
    elif data == 'settings':
        await settings(update)
    elif data == 'clear_checkin':
        get_media(update.effective_user.id)['checkin'] = []
        await update.callback_query.answer("🗑 Очищено!")
    elif data == 'clear_checkout':
        get_media(update.effective_user.id)['checkout'] = []
        await update.callback_query.answer("🗑 Очищено!")
    elif data == 'view_lib':
        media = get_media(update.effective_user.id)
        msg = f'📚 Бібліотека:\n\n✅ Check-in: {len(media["checkin"])}\n🚪 Check-out: {len(media["checkout"])}'
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    elif data == 'back':
        keyboard = [[InlineKeyboardButton("✅ Check-in", callback_data='checkin')], [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')], [InlineKeyboardButton("👥 Команда", callback_data='team')], [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]]
        await update.callback_query.answer()
        try: await update.callback_query.message.delete()
        except: pass
        await update.callback_query.message.reply_text('👋 Меню:', reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ BOT_TOKEN не знайдено!")
        return
    Thread(target=run_http, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(entry_points=[CallbackQueryHandler(start_add_checkin, pattern='^add_checkin$'), CallbackQueryHandler(start_add_checkout, pattern='^add_checkout$')], states={ADDING_CHECKIN_MEDIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkin), MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkin), CommandHandler("done", done)], ADDING_CHECKOUT_MEDIA: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkout), MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkout), CommandHandler("done", done)]}, fallbacks=[CommandHandler("cancel", cancel)])
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQuer
