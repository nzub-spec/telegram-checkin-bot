import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

# Стани для conversation handler
ADDING_CHECKIN_MEDIA, ADDING_CHECKOUT_MEDIA = range(2)

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

# Користувацькі медіа (бібліотека)
user_media = {}

def get_user_media(user_id):
    """Отримати медіа користувача"""
    if user_id not in user_media:
        user_media[user_id] = {
            'checkin': [],  # Список медіа [{'type': 'text/photo/video/animation', 'content': '...'}]
            'checkout': []
        }
    return user_media[user_id]

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
        [InlineKeyboardButton("👥 Команда", callback_data='team')],
        [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]
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

async def settings_menu(update: Update):
    """Меню налаштувань"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    keyboard = [
        [InlineKeyboardButton("➕ Додати Check-in медіа", callback_data='add_checkin')],
        [InlineKeyboardButton("➕ Додати Check-out медіа", callback_data='add_checkout')],
        [InlineKeyboardButton("📋 Переглянути бібліотеку", callback_data='view_library')],
        [InlineKeyboardButton("🗑 Очистити Check-in", callback_data='clear_checkin')],
        [InlineKeyboardButton("🗑 Очистити Check-out", callback_data='clear_checkout')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]
    ]
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass
        
        msg = (f'🎨 Бібліотека медіа:\n\n'
               f'📊 Check-in: {len(media["checkin"])} медіа\n'
               f'📊 Check-out: {len(media["checkout"])} медіа\n\n'
               f'При check-in/out бот випадково обере одне медіа з бібліотеки!')
        
        await update.callback_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))InlineKeyboardButton("➕ Налаштувати Check-out медіа", callback_data='set_checkout')],
        [InlineKeyboardButton("🗑 Видалити Check-in медіа", callback_data='del_checkin')],
        [InlineKeyboardButton("🗑 Видалити Check-out медіа", callback_data='del_checkout')],
        [InlineKeyboardButton("⬅️ Назад", callback_data='back_main')]
    ]
    
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await update.callback_query.message.reply_text(
            '🎨 Налаштування медіа:\n\n'
            'Ти можеш додати своє медіа для check-in/checkout:\n'
            '• 💬 Текст\n'
            '• 🖼 Фото\n'
            '• 🎬 Гіфку\n'
            '• 🎥 Відео',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def start_add_checkin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок додавання check-in медіа"""
    await update.callback_query.answer()
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    await update.callback_query.message.reply_text(
        '📸 Надішли медіа для Check-in:\n\n'
        '• 💬 Текст\n'
        '• 🖼 Фото\n'
        '• 🎬 Гіфку\n'
        '• 🎥 Відео\n\n'
        'Можеш надіслати кілька підряд!\n'
        '/done - завершити, /cancel - скасувати'
    )
    return ADDING_CHECKIN_MEDIA

async def start_add_checkout_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Початок додавання check-out медіа"""
    await update.callback_query.answer()
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    await update.callback_query.message.reply_text(
        '📸 Надішли медіа для Check-out:\n\n'
        '• 💬 Текст\n'
        '• 🖼 Фото\n'
        '• 🎬 Гіфку\n'
        '• 🎥 Відео\n\n'
        'Можеш надіслати кілька підряд!\n'
        '/done - завершити, /cancel - скасувати'
    )
    return ADDING_CHECKOUT_MEDIA

async def receive_checkin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання check-in медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    if update.message.text:
        media['checkin'].append({'type': 'text', 'content': update.message.text})
        await update.message.reply_text(f'✅ Текст додано! Всього в бібліотеці: {len(media["checkin"])}\n\nНадішли ще або /done')
    elif update.message.photo:
        media['checkin'].append({'type': 'photo', 'content': update.message.photo[-1].file_id})
        await update.message.reply_text(f'✅ Фото додано! Всього: {len(media["checkin"])}\n\nНадішли ще або /done')
    elif update.message.animation:
        media['checkin'].append({'type': 'animation', 'content': update.message.animation.file_id})
        await update.message.reply_text(f'✅ Гіфка додана! Всього: {len(media["checkin"])}\n\nНадішли ще або /done')
    elif update.message.video:
        media['checkin'].append({'type': 'video', 'content': update.message.video.file_id})
        await update.message.reply_text(f'✅ Відео додано! Всього: {len(media["checkin"])}\n\nНадішли ще або /done')
    else:
        await update.message.reply_text('❌ Надішли текст, фото, гіфку або відео')
        return ADDING_CHECKIN_MEDIA
    
    return ADDING_CHECKIN_MEDIA  # Продовжуємо додавати

async def receive_checkout_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отримання check-out медіа"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    if update.message.text:
        media['checkout'].append({'type': 'text', 'content': update.message.text})
        await update.message.reply_text(f'✅ Текст додано! Всього в бібліотеці: {len(media["checkout"])}\n\nНадішли ще або /done')
    elif update.message.photo:
        media['checkout'].append({'type': 'photo', 'content': update.message.photo[-1].file_id})
        await update.message.reply_text(f'✅ Фото додано! Всього: {len(media["checkout"])}\n\nНадішли ще або /done')
    elif update.message.animation:
        media['checkout'].append({'type': 'animation', 'content': update.message.animation.file_id})
        await update.message.reply_text(f'✅ Гіфка додана! Всього: {len(media["checkout"])}\n\nНадішли ще або /done')
    elif update.message.video:
        media['checkout'].append({'type': 'video', 'content': update.message.video.file_id})
        await update.message.reply_text(f'✅ Відео додано! Всього: {len(media["checkout"])}\n\nНадішли ще або /done')
    else:
        await update.message.reply_text('❌ Надішли текст, фото, гіфку або відео')
        return ADDING_CHECKOUT_MEDIA
    
    return ADDING_CHECKOUT_MEDIA  # Продовжуємо додавати

async def done_adding_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершити додавання"""
    await update.message.reply_text('✅ Збережено! Медіа додано в бібліотеку.')
    return ConversationHandler.END

async def cancel_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Скасування додавання медіа"""
    await update.message.reply_text('❌ Скасовано')
    return ConversationHandler.END

async def checkin_with_selected_media(update: Update, media_index: int, workload: str = None):
    """Check-in з обраним медіа"""
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
    
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    # Формуємо повідомлення
    if workload:
        msg = (f"✅ {username} почав робочий день!\n"
               f"{workload} {WORKLOAD[workload]}\n\n"
               f"💪 Продуктивної роботи!")
    else:
        msg = (f"✅ {username} почав робочий день!\n\n"
               f"💪 Продуктивної роботи!")
    
    # Отримуємо обране медіа
    media = get_user_media(user_id)
    selected_media = media['checkin'][media_index]
    
    await send_with_media_direct(update.callback_query.message, selected_media, msg)

async def checkout_with_selected_media(update: Update, media_index: int):
    """Check-out з обраним медіа"""
    user_id = update.effective_user.id
    username = update.effective_user.first_name
    
    if user_id not in user_status or not user_status[user_id]['active']:
        await update.callback_query.answer("Спочатку check-in!")
        return
    
    user_status[user_id]['active'] = False
    
    await update.callback_query.answer("✅ Check-out!")
    
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    msg = f"🚪 {username} закінчив робочий день!\n\n👏 Чудова робота!"
    
    # Отримуємо обране медіа
    media = get_user_media(user_id)
    selected_media = media['checkout'][media_index]
    
    await send_with_media_direct(update.callback_query.message, selected_media, msg)

async def send_with_media_direct(message, media_item, text):
    """Відправити медіа напряму"""
    try:
        media_type = media_item['type']
        content = media_item['content']
        
        if media_type == 'text':
            await message.reply_text(f"{text}\n\n💬 {content}")
        elif media_type == 'photo':
            await message.reply_photo(photo=content, caption=text)
        elif media_type == 'animation':
            await message.reply_animation(animation=content, caption=text)
        elif media_type == 'video':
            await message.reply_video(video=content, caption=text)
    except:
        await message.reply_text(text)

async def send_with_media(query, media_item, message):
    """Відправити повідомлення з медіа"""
    try:
        if not media_item:
            await query.message.reply_text(message)
            return
        
        media_type = media_item['type']
        content = media_item['content']
        
        if media_type == 'text':
            await query.message.reply_text(f"{message}\n\n💬 {content}")
        elif media_type == 'photo':
            await query.message.reply_photo(photo=content, caption=message)
        elif media_type == 'animation':
            await query.message.reply_animation(animation=content, caption=message)
        elif media_type == 'video':
            await query.message.reply_video(video=content, caption=message)
        else:
            await query.message.reply_text(message)
    except:
        await query.message.reply_text(message)

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
    
    msg = f"✅ {username} почав робочий день!\n\n💪 Продуктивної роботи!"
    
    # Отримуємо медіа користувача
    media = get_user_media(user_id)
    checkin_media = media.get('checkin')
    
    try:
        if checkin_media:
            media_type = checkin_media['type']
            content = checkin_media['content']
            
            if media_type == 'text':
                await update.message.reply_text(f"{msg}\n\n💬 {content}")
            elif media_type == 'photo':
                await update.message.reply_photo(photo=content, caption=msg)
            elif media_type == 'animation':
                await update.message.reply_animation(animation=content, caption=msg)
            elif media_type == 'video':
                await update.message.reply_video(video=content, caption=msg)
        else:
            await update.message.reply_text(msg)
    except:
        await update.message.reply_text(msg)

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
    
    msg = f"🚪 {username} закінчив робочий день!\n\n👏 Чудова робота!"
    
    # Отримуємо медіа користувача
    media = get_user_media(user_id)
    checkout_media = media.get('checkout')
    
    try:
        if checkout_media:
            media_type = checkout_media['type']
            content = checkout_media['content']
            
            if media_type == 'text':
                await update.message.reply_text(f"{msg}\n\n💬 {content}")
            elif media_type == 'photo':
                await update.message.reply_photo(photo=content, caption=msg)
            elif media_type == 'animation':
                await update.message.reply_animation(animation=content, caption=msg)
            elif media_type == 'video':
                await update.message.reply_video(video=content, caption=msg)
        else:
            await update.message.reply_text(msg)
    except:
        await update.message.reply_text(msg)

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

async def show_checkin_media_selection(update: Update):
    """Показати бібліотеку check-in медіа для вибору"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    await update.callback_query.answer()
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    if not media['checkin']:
        await update.callback_query.message.reply_text(
            '📚 Бібліотека check-in порожня!\n\n'
            'Додай медіа через /start → 🎨 Налаштування → ➕ Додати Check-in медіа'
        )
        return
    
    # Створюємо кнопки для кожного медіа
    keyboard = []
    for i, item in enumerate(media['checkin'][:10]):  # Максимум 10
        media_type = item['type']
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(media_type, '📄')
        
        if media_type == 'text':
            preview = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {preview}", callback_data=f'checkin_select_{i}')])
        else:
            keyboard.append([InlineKeyboardButton(f"{emoji} Медіа #{i+1}", callback_data=f'checkin_select_{i}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='checkin')])
    
    await update.callback_query.message.reply_text(
        '📚 Обери медіа для Check-in:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_checkout_media_selection(update: Update):
    """Показати бібліотеку check-out медіа для вибору"""
    user_id = update.effective_user.id
    media = get_user_media(user_id)
    
    await update.callback_query.answer()
    try:
        await update.callback_query.message.delete()
    except:
        pass
    
    if not media['checkout']:
        await update.callback_query.message.reply_text(
            '📚 Бібліотека check-out порожня!\n\n'
            'Додай медіа через /start → 🎨 Налаштування → ➕ Додати Check-out медіа'
        )
        return
    
    # Створюємо кнопки
    keyboard = []
    for i, item in enumerate(media['checkout'][:10]):
        media_type = item['type']
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(media_type, '📄')
        
        if media_type == 'text':
            preview = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {preview}", callback_data=f'checkout_select_{i}')])
        else:
            keyboard.append([InlineKeyboardButton(f"{emoji} Медіа #{i+1}", callback_data=f'checkout_select_{i}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back_main')])
    
    await update.callback_query.message.reply_text(
        '📚 Обери медіа для Check-out:',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_workload(update: Update):
    """Показати вибір завантаження"""
    keyboard = [
        [InlineKeyboardButton("🟢 Потрібні задачі", callback_data='work_🟢')],
        [InlineKeyboardButton("🟡 Середня завантаженість", callback_data='work_🟡')],
        [InlineKeyboardButton("🔴 Завантаженість до пенсії", callback_data='work_🔴')],
        [InlineKeyboardButton("➡️ Пропустити", callback_data='work_skip')]
    ]
    await update.callback_query.answer()
    # Видаляємо меню
    try:
        await update.callback_query.message.delete()
    except:
        pass
    # Відправляємо нове
    await update.callback_query.message.reply_text(
        '📊 Обери рівень завантаження або пропусти:',
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
    
    # Формуємо повідомлення
    if workload:
        msg = (f"✅ {username} почав робочий день!\n"
               f"{workload} {WORKLOAD[workload]}\n\n"
               f"💪 Продуктивної роботи!")
    else:
        msg = (f"✅ {username} почав робочий день!\n\n"
               f"💪 Продуктивної роботи!")
    
    # Отримуємо медіа
    media = get_user_media(user_id)
    await send_with_media(update.callback_query, media.get('checkin'), msg)

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
    
    msg = f"🚪 {username} закінчив робочий день!\n\n👏 Чудова робота!"
    
    # Отримуємо медіа
    media = get_user_media(user_id)
    await send_with_media(update.callback_query, media.get('checkout'), msg)

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
        # Показуємо бібліотеку медіа для вибору
        await show_checkin_media_selection(update)
    elif data.startswith('checkin_select_'):
        # Обрано медіа для checkin - показуємо вибір завантаження
        media_index = int(data.split('_')[-1])
        context.user_data['selected_checkin_media'] = media_index
        await show_workload(update)
    elif data.startswith('work_'):
        # Обрано завантаження - робимо checkin з обраним медіа
        media_index = context.user_data.get('selected_checkin_media', 0)
        if data == 'work_skip':
            await checkin_with_selected_media(update, media_index, None)
        else:
            workload = data.split('_')[1]
            await checkin_with_selected_media(update, media_index, workload)
    elif data == 'checkout':
        # Показуємо бібліотеку медіа для checkout
        await show_checkout_media_selection(update)
    elif data.startswith('checkout_select_'):
        # Обрано медіа для checkout - робимо checkout
        media_index = int(data.split('_')[-1])
        await checkout_with_selected_media(update, media_index)
    elif data == 'team':
        await team(update)
    elif data == 'settings':
        await settings_menu(update)
    elif data == 'add_checkin':
        await start_add_checkin_media(update, context)
    elif data == 'add_checkout':
        await start_add_checkout_media(update, context)
    elif data == 'clear_checkin':
        user_id = update.effective_user.id
        get_user_media(user_id)['checkin'] = []
        await update.callback_query.answer("🗑 Check-in бібліотека очищена!")
    elif data == 'clear_checkout':
        user_id = update.effective_user.id
        get_user_media(user_id)['checkout'] = []
        await update.callback_query.answer("🗑 Check-out бібліотека очищена!")
    elif data == 'view_library':
        user_id = update.effective_user.id
        media = get_user_media(user_id)
        msg = f'📚 Твоя бібліотека:\n\n'
        msg += f'✅ Check-in: {len(media["checkin"])} медіа\n'
        msg += f'🚪 Check-out: {len(media["checkout"])} медіа'
        await update.callback_query.answer()
        await update.callback_query.message.reply_text(msg)
    elif data == 'back_main':
        keyboard = [
            [InlineKeyboardButton("✅ Check-in", callback_data='checkin')],
            [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')],
            [InlineKeyboardButton("👥 Команда", callback_data='team')],
            [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]
        ]
        await update.callback_query.answer()
        try:
            await update.callback_query.message.delete()
        except:
            pass
        await update.callback_query.message.reply_text(
            '👋 Головне меню:',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

def main():
    """Запуск бота"""
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ Додай BOT_TOKEN!")
        return
    
    # Запускаємо HTTP сервер в окремому потоці
    Thread(target=run_http_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    
    # Conversation handler для медіа
    conv_handler = ConversationHandler(
        entry_points=[],
        states={
            ADDING_CHECKIN_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkin_media),
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkin_media),
                CommandHandler("done", done_adding_media),
            ],
            ADDING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkout_media),
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkout_media),
                CommandHandler("done", done_adding_media),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_media)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(CommandHandler("team", team_command))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
