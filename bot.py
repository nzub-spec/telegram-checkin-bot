import os
import json
import psycopg2
from psycopg2.extras import Json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters, ConversationHandler
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

ADDING_CHECKIN_MEDIA, ADDING_CHECKOUT_MEDIA, NAMING_CHECKIN_MEDIA, NAMING_CHECKOUT_MEDIA = range(4)

# Database connection
def get_db_connection():
    """Підключення до бази даних"""
    try:
        return psycopg2.connect(os.getenv('DATABASE_URL'))
    except Exception as e:
        print(f"❌ Помилка підключення до БД: {e}")
        return None

def init_db():
    """Ініціалізація таблиць бази даних"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        # Таблиця для СПІЛЬНОЇ бібліотеки медіа (для всіх користувачів)
        cur.execute('''
            CREATE TABLE IF NOT EXISTS shared_media (
                id SERIAL PRIMARY KEY,
                media_type TEXT NOT NULL,
                checkin_media JSONB DEFAULT '[]',
                checkout_media JSONB DEFAULT '[]'
            )
        ''')
        # Перевіряємо чи є запис, якщо ні - створюємо
        cur.execute('SELECT COUNT(*) FROM shared_media')
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO shared_media (media_type, checkin_media, checkout_media) VALUES ('shared', '[]', '[]')")
        
        # Таблиця для статусів користувачів
        cur.execute('''
            CREATE TABLE IF NOT EXISTS user_status (
                user_id BIGINT PRIMARY KEY,
                active BOOLEAN DEFAULT FALSE,
                username TEXT,
                workload TEXT
            )
        ''')
        conn.commit()
        cur.close()
        conn.close()
        print("✅ База даних ініціалізована")
    except Exception as e:
        print(f"❌ Помилка ініціалізації БД: {e}")
        if conn:
            conn.close()

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

# Функції для роботи з базою даних
def get_shared_media_from_db():
    """Отримати СПІЛЬНУ бібліотеку медіа з БД"""
    conn = get_db_connection()
    if not conn:
        return {'checkin': [], 'checkout': []}
    try:
        cur = conn.cursor()
        cur.execute('SELECT checkin_media, checkout_media FROM shared_media WHERE media_type = %s', ('shared',))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            return {'checkin': result[0] or [], 'checkout': result[1] or []}
        return {'checkin': [], 'checkout': []}
    except Exception as e:
        print(f"❌ Помилка читання медіа: {e}")
        if conn:
            conn.close()
        return {'checkin': [], 'checkout': []}

def save_shared_media_to_db(media):
    """Зберегти СПІЛЬНУ бібліотеку медіа в БД"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE shared_media 
            SET checkin_media = %s, checkout_media = %s
            WHERE media_type = %s
        ''', (Json(media['checkin']), Json(media['checkout']), 'shared'))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Помилка збереження медіа: {e}")
        if conn:
            conn.close()

def get_user_status_from_db(user_id):
    """Отримати статус користувача з БД"""
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute('SELECT active, username, workload FROM user_status WHERE user_id = %s', (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        if result:
            return {'active': result[0], 'username': result[1], 'workload': result[2]}
        return None
    except Exception as e:
        print(f"❌ Помилка читання статусу: {e}")
        if conn:
            conn.close()
        return None

def save_user_status_to_db(user_id, status):
    """Зберегти статус користувача в БД"""
    conn = get_db_connection()
    if not conn:
        return
    try:
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO user_status (user_id, active, username, workload)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (user_id) 
            DO UPDATE SET active = %s, username = %s, workload = %s
        ''', (user_id, status['active'], status['username'], status.get('workload'),
              status['active'], status['username'], status.get('workload')))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Помилка збереження статусу: {e}")
        if conn:
            conn.close()

def get_all_user_statuses():
    """Отримати всі статуси користувачів"""
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        cur = conn.cursor()
        cur.execute('SELECT user_id, active, username, workload FROM user_status')
        results = cur.fetchall()
        cur.close()
        conn.close()
        statuses = {}
        for row in results:
            statuses[row[0]] = {'active': row[1], 'username': row[2], 'workload': row[3]}
        return statuses
    except Exception as e:
        print(f"❌ Помилка читання всіх статусів: {e}")
        if conn:
            conn.close()
        return {}

user_status = {}
shared_media = {'checkin': [], 'checkout': []}  # Спільна бібліотека для всіх
WORKLOAD = {'🟢': 'Потрібні задачі', '🟡': 'Середня завантаженість', '🔴': 'Завантаженість до пенсії'}

def get_media(user_id=None):
    """Отримати СПІЛЬНУ бібліотеку медіа (user_id не використовується, але залишаємо для сумісності)"""
    global shared_media
    if not shared_media['checkin'] and not shared_media['checkout']:
        # Завантажуємо з БД, якщо ще не завантажено
        shared_media = get_shared_media_from_db()
    return shared_media

async def delete_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Автоматично видаляти всі команди бота"""
    try:
        await update.message.delete()
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("✅ Check-in", callback_data='checkin')], [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')], [InlineKeyboardButton("👥 Команда", callback_data='team')], [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]]
    await context.bot.send_message(chat_id=chat_id, text='👋 Бот для відмітки часу', reply_markup=InlineKeyboardMarkup(keyboard))

async def checkin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    media = get_media()  # Спільна бібліотека
    
    if not media['checkin']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека check-in порожня! Додай медіа через /start → 🎨 Налаштування')
        return
    keyboard = []
    for i, item in enumerate(media['checkin']):  # Показуємо ВСІ медіа
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'ci_{i}')])
        else:
            # Показуємо назву якщо є, інакше "Медіа #N"
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'ci_{i}')])
    await context.bot.send_message(chat_id=chat_id, text='📚 Обери Check-in:', reply_markup=InlineKeyboardMarkup(keyboard))

async def checkout_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    media = get_media()  # Спільна бібліотека
    
    if not media['checkout']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека check-out порожня! Додай медіа через /start → 🎨 Налаштування')
        return
    keyboard = []
    for i, item in enumerate(media['checkout']):  # Показуємо ВСІ медіа
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'co_{i}')])
        else:
            # Показуємо назву якщо є, інакше "Медіа #N"
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'co_{i}')])
    await context.bot.send_message(chat_id=chat_id, text='📚 Обери Check-out:', reply_markup=InlineKeyboardMarkup(keyboard))

async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    media = get_media()  # Спільна бібліотека
    keyboard = [
        [InlineKeyboardButton("➕ Додати Check-in", callback_data='add_checkin')], 
        [InlineKeyboardButton("➕ Додати Check-out", callback_data='add_checkout')], 
        [InlineKeyboardButton("📋 Бібліотека", callback_data='view_lib')], 
        [InlineKeyboardButton("✏️ Редагувати Check-in", callback_data='edit_checkin')], 
        [InlineKeyboardButton("✏️ Редагувати Check-out", callback_data='edit_checkout')], 
        [InlineKeyboardButton("⬅️ Назад", callback_data='back')]
    ]
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    msg = f'🎨 Спільна бібліотека:\n\n✅ Check-in: {len(media["checkin"])}\n🚪 Check-out: {len(media["checkout"])}'
    await context.bot.send_message(chat_id=chat_id, text=msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_checkin_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    media = get_media()  # Спільна бібліотека
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    if not media['checkin']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека порожня!')
        return
    keyboard = []
    for i, item in enumerate(media['checkin']):  # Показуємо ВСІ медіа
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'ci_{i}')])
        else:
            # Показуємо назву якщо є, інакше "Медіа #N"
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'ci_{i}')])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='checkin')])
    await context.bot.send_message(chat_id=chat_id, text='📚 Обери Check-in:', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_checkin_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати Check-in медіа для редагування/видалення"""
    chat_id = update.effective_chat.id
    media = get_media()
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    
    if not media['checkin']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека порожня!')
        return
    
    keyboard = []
    for i, item in enumerate(media['checkin']):
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'delci_{i}')])
        else:
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'delci_{i}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='settings')])
    await context.bot.send_message(chat_id=chat_id, text='🗑 Натисни на медіа щоб видалити:', reply_markup=InlineKeyboardMarkup(keyboard))

async def edit_checkout_library(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показати Check-out медіа для редагування/видалення"""
    chat_id = update.effective_chat.id
    media = get_media()
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    
    if not media['checkout']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека порожня!')
        return
    
    keyboard = []
    for i, item in enumerate(media['checkout']):
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'delco_{i}')])
        else:
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'delco_{i}')])
    
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='settings')])
    await context.bot.send_message(chat_id=chat_id, text='🗑 Натисни на медіа щоб видалити:', reply_markup=InlineKeyboardMarkup(keyboard))

async def delete_checkin_item(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    """Видалити конкретний check-in елемент"""
    media = get_media()
    
    if 0 <= idx < len(media['checkin']):
        deleted_item = media['checkin'].pop(idx)
        save_shared_media_to_db(media)
        
        # Показуємо що видалили
        if deleted_item['type'] == 'text':
            name = deleted_item['content'][:30]
        else:
            name = deleted_item.get('name', f"Медіа #{idx+1}")
        
        await update.callback_query.answer(f"🗑 Видалено: {name}")
        
        # Оновлюємо список
        await edit_checkin_library(update, context)
    else:
        await update.callback_query.answer("❌ Помилка: елемент не знайдено")

async def delete_checkout_item(update: Update, context: ContextTypes.DEFAULT_TYPE, idx: int):
    """Видалити конкретний check-out елемент"""
    media = get_media()
    
    if 0 <= idx < len(media['checkout']):
        deleted_item = media['checkout'].pop(idx)
        save_shared_media_to_db(media)
        
        # Показуємо що видалили
        if deleted_item['type'] == 'text':
            name = deleted_item['content'][:30]
        else:
            name = deleted_item.get('name', f"Медіа #{idx+1}")
        
        await update.callback_query.answer(f"🗑 Видалено: {name}")
        
        # Оновлюємо список
        await edit_checkout_library(update, context)
    else:
        await update.callback_query.answer("❌ Помилка: елемент не знайдено")
    chat_id = update.effective_chat.id
    media = get_media()  # Спільна бібліотека
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    if not media['checkout']:
        await context.bot.send_message(chat_id=chat_id, text='📚 Бібліотека порожня!')
        return
    keyboard = []
    for i, item in enumerate(media['checkout'][:10]):
        emoji = {'text': '💬', 'photo': '🖼', 'animation': '🎬', 'video': '🎥'}.get(item['type'], '📄')
        if item['type'] == 'text':
            text = item['content'][:30] + '...' if len(item['content']) > 30 else item['content']
            keyboard.append([InlineKeyboardButton(f"{emoji} {text}", callback_data=f'co_{i}')])
        else:
            # Показуємо назву якщо є, інакше "Медіа #N"
            name = item.get('name', '') or f"Медіа #{i+1}"
            display_name = name[:30] + '...' if len(name) > 30 else name
            keyboard.append([InlineKeyboardButton(f"{emoji} {display_name}", callback_data=f'co_{i}')])
    keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data='back')])
    await context.bot.send_message(chat_id=chat_id, text='📚 Обери Check-out:', reply_markup=InlineKeyboardMarkup(keyboard))

async def show_workload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    keyboard = [[InlineKeyboardButton("🟢 Потрібні задачі", callback_data='w_🟢')], [InlineKeyboardButton("🟡 Середня завантаженість", callback_data='w_🟡')], [InlineKeyboardButton("🔴 Завантаженість до пенсії", callback_data='w_🔴')], [InlineKeyboardButton("➡️ Пропустити", callback_data='w_skip')]]
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    await context.bot.send_message(chat_id=chat_id, text='📊 Завантаженість:', reply_markup=InlineKeyboardMarkup(keyboard))

async def do_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE, media_idx: int, workload: str = None):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    username = update.effective_user.first_name
    if user_id in user_status and user_status[user_id]['active']:
        await update.callback_query.answer("Вже на роботі!")
        return
    user_status[user_id] = {'active': True, 'username': username, 'workload': workload}
    save_user_status_to_db(user_id, user_status[user_id])  # Зберігаємо в БД
    await update.callback_query.answer("✅ Check-in!")
    # ВИДАЛЯЄМО ПОВІДОМЛЕННЯ З ВИБОРОМ ЗАВАНТАЖЕНОСТІ
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    msg = f"✅ {username} розпочинає день!\n"
    if workload:
        msg += f"{workload} {WORKLOAD[workload]}\n"
    msg += "\n💪 Продуктивної роботи!"
    media = get_media()  # Спільна бібліотека
    if media['checkin']:
        await send_media(context.bot, chat_id, media['checkin'][media_idx], msg)
    else:
        await context.bot.send_message(chat_id=chat_id, text=msg)

async def do_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE, media_idx: int):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    username = update.effective_user.first_name
    if user_id not in user_status or not user_status[user_id]['active']:
        await update.callback_query.answer("Спочатку check-in!")
        return
    user_status[user_id]['active'] = False
    save_user_status_to_db(user_id, user_status[user_id])  # Зберігаємо в БД
    await update.callback_query.answer("✅ Check-out!")
    # ВИДАЛЯЄМО ПОВІДОМЛЕННЯ З ВИБОРОМ МЕДІА
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    msg = f"🚪 {username} завершує робочий день!\n\n👏 Good job!"
    media = get_media()  # Спільна бібліотека
    if media['checkout']:
        await send_media(context.bot, chat_id, media['checkout'][media_idx], msg)
    else:
        await context.bot.send_message(chat_id=chat_id, text=msg)

async def send_media(bot, chat_id, item, text):
    try:
        t = item['type']
        c = item['content']
        if t == 'text':
            await bot.send_message(chat_id=chat_id, text=f"{text}\n\n💬 {c}")
        elif t == 'photo':
            await bot.send_photo(chat_id=chat_id, photo=c, caption=text)
        elif t == 'animation':
            await bot.send_animation(chat_id=chat_id, animation=c, caption=text)
        elif t == 'video':
            await bot.send_video(chat_id=chat_id, video=c, caption=text)
    except:
        await bot.send_message(chat_id=chat_id, text=text)

async def team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    # Завантажуємо актуальні статуси з БД
    all_statuses = get_all_user_statuses()
    if not all_statuses:
        msg = "📊 Немає даних"
    else:
        online = []
        for d in all_statuses.values():
            if d['active']:
                if d.get('workload'):
                    online.append(f"{d['workload']} {d['username']} - {WORKLOAD[d['workload']]}")
                else:
                    online.append(f"✅ {d['username']}")
        offline = [f"⭕ {d['username']}" for d in all_statuses.values() if not d['active']]
        msg = "👥 Команда:\n\n"
        if online: msg += "🟢 На роботі:\n" + "\n".join(online) + "\n\n"
        if offline: msg += "🔴 Не на роботі:\n" + "\n".join(offline)
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    await context.bot.send_message(chat_id=chat_id, text=msg)

async def start_add_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    await context.bot.send_message(chat_id=chat_id, text='📸 Надішли медіа:\n• 💬 Текст\n• 🖼 Фото\n• 🎬 Гіфку\n• 🎥 Відео\n\nПісля медіа система попросить назву.\n\n/done - готово, /cancel - скасувати')
    return ADDING_CHECKIN_MEDIA

async def start_add_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.callback_query.answer()
    try: 
        await update.callback_query.message.delete()
    except: 
        pass
    await context.bot.send_message(chat_id=chat_id, text='📸 Надішли медіа:\n• 💬 Текст\n• 🖼 Фото\n• 🎬 Гіфку\n• 🎥 Відео\n\nПісля медіа система попросить назву.\n\n/done - готово, /cancel - скасувати')
    return ADDING_CHECKOUT_MEDIA

async def receive_checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        # Текст додаємо відразу
        media = get_media()
        media['checkin'].append({'type': 'text', 'content': update.message.text, 'name': ''})
        save_shared_media_to_db(media)
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
        return ADDING_CHECKIN_MEDIA
    elif update.message.photo:
        # Зберігаємо фото тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'photo', 'content': update.message.photo[-1].file_id}
        await update.message.reply_text('📝 Надішли назву для цього фото (або /skip щоб пропустити):')
        return NAMING_CHECKIN_MEDIA
    elif update.message.animation:
        # Зберігаємо гіфку тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'animation', 'content': update.message.animation.file_id}
        await update.message.reply_text('📝 Надішли назву для цієї гіфки (або /skip щоб пропустити):')
        return NAMING_CHECKIN_MEDIA
    elif update.message.video:
        # Зберігаємо відео тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'video', 'content': update.message.video.file_id}
        await update.message.reply_text('📝 Надішли назву для цього відео (або /skip щоб пропустити):')
        return NAMING_CHECKIN_MEDIA
    return ADDING_CHECKIN_MEDIA

async def name_checkin_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Зберегти назву для check-in медіа"""
    media = get_media()
    temp_media = context.user_data.get('temp_media')
    
    if not temp_media:
        await update.message.reply_text('❌ Помилка: медіа не знайдено')
        return ADDING_CHECKIN_MEDIA
    
    # Отримуємо назву або залишаємо порожньою
    name = update.message.text if update.message.text and update.message.text != '/skip' else ''
    
    # Додаємо медіа з назвою
    temp_media['name'] = name
    media['checkin'].append(temp_media)
    save_shared_media_to_db(media)
    
    # Очищаємо тимчасові дані
    context.user_data.pop('temp_media', None)
    
    if name:
        await update.message.reply_text(f'✅ Додано "{name}"! Всього: {len(media["checkin"])}')
    else:
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkin"])}')
    
    return ADDING_CHECKIN_MEDIA

async def receive_checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text:
        # Текст додаємо відразу
        media = get_media()
        media['checkout'].append({'type': 'text', 'content': update.message.text, 'name': ''})
        save_shared_media_to_db(media)
        await update.message.reply_text(f'✅ Додано! Всього: {len(media["checkout"])}')
        return ADDING_CHECKOUT_MEDIA
    elif update.message.photo:
        # Зберігаємо фото тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'photo', 'content': update.message.photo[-1].file_id}
        await update.message.reply_text('📝 Надішли назву для цього фото (або /skip щоб пропустити):')
        return NAMING_CHECKOUT_MEDIA
    elif update.message.animation:
        # Зберігаємо гіфку тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'animation', 'content': update.message.animation.file_id}
        await update.message.reply_text('📝 Надішли назву для цієї гіфки (або /skip щоб пропустити):')
        return NAMING_CHECKOUT_MEDIA
    elif update.message.video:
        # Зберігаємо відео тимчасово і просимо назву
        context.user_data['temp_media'] = {'type': 'video', 'content': update.message.video.file_id}
        await update.message.reply_text('📝 Надішли назву для цього відео (або /skip щоб пропустити):')
        return NAMING_CHECKOUT_MEDIA
    return ADDING_CHECKOUT_MEDIA

async def name_checkout_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Зберегти назву для check-out медіа"""
    media = get_media()
    temp_media = context.user_data.get('temp_media')
    
    if not temp_media:
        await update.message.reply_text('❌ Помилка: медіа не знайдено')
        return ADDING_CHECKOUT_MEDIA
    
    # Отримуємо назву або залишаємо порожньою
    name = update.message.text if update.message.text and update.message.text != '/skip' else ''
    
    # Додаємо медіа з назвою
    temp_media['name'] = name
    media['checkout'].append(temp_media)
    save_shared_media_to_db(media)
    
    # Очищаємо тимчасові дані
    context.user_data.pop('temp_media', None)
    
    if name:
        await update.message.reply_text(f'✅ Додано "{name}"! Всього: {len(media["checkout"])}')
    else:
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
        await show_checkin_library(update, context)
    elif data.startswith('ci_'):
        idx = int(data[3:])
        context.user_data['ci_idx'] = idx
        await show_workload(update, context)
    elif data.startswith('w_'):
        idx = context.user_data.get('ci_idx', 0)
        workload = None if data == 'w_skip' else data[2:]
        await do_checkin(update, context, idx, workload)
    elif data == 'checkout':
        await show_checkout_library(update, context)
    elif data.startswith('co_'):
        idx = int(data[3:])
        await do_checkout(update, context, idx)
    elif data == 'team':
        await team(update, context)
    elif data == 'settings':
        await settings(update, context)
    elif data == 'edit_checkin':
        await edit_checkin_library(update, context)
    elif data == 'edit_checkout':
        await edit_checkout_library(update, context)
    elif data.startswith('delci_'):
        idx = int(data[6:])
        await delete_checkin_item(update, context, idx)
    elif data.startswith('delco_'):
        idx = int(data[6:])
        await delete_checkout_item(update, context, idx)
    elif data == 'view_lib':
        media = get_media()
        msg = f'📚 Спільна бібліотека:\n\n✅ Check-in: {len(media["checkin"])}\n🚪 Check-out: {len(media["checkout"])}'
        await update.callback_query.answer()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    elif data == 'back':
        chat_id = update.effective_chat.id
        keyboard = [[InlineKeyboardButton("✅ Check-in", callback_data='checkin')], [InlineKeyboardButton("🚪 Check-out", callback_data='checkout')], [InlineKeyboardButton("👥 Команда", callback_data='team')], [InlineKeyboardButton("🎨 Налаштування", callback_data='settings')]]
        await update.callback_query.answer()
        try: 
            await update.callback_query.message.delete()
        except: 
            pass
        await context.bot.send_message(chat_id=chat_id, text='👋 Меню:', reply_markup=InlineKeyboardMarkup(keyboard))

def main():
    TOKEN = os.getenv('BOT_TOKEN')
    if not TOKEN:
        print("❌ BOT_TOKEN не знайдено!")
        return
    
    # Ініціалізуємо базу даних
    init_db()
    
    # Завантажуємо спільну бібліотеку медіа
    global shared_media
    shared_media = get_shared_media_from_db()
    print(f"📚 Завантажено медіа: Check-in={len(shared_media['checkin'])}, Check-out={len(shared_media['checkout'])}")
    
    # Завантажуємо статуси в пам'ять для швидкого доступу
    global user_status
    user_status = get_all_user_statuses()
    print(f"📊 Завантажено статусів: {len(user_status)}")
    
    Thread(target=run_http, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    
    # Налаштовуємо команди для меню
    async def post_init(application: Application):
        from telegram import BotCommand
        await application.bot.set_my_commands([
            BotCommand("start", "🏠 Головне меню"),
            BotCommand("checkin", "✅ Check-in"),
            BotCommand("checkout", "🚪 Check-out"),
        ])
    
    app.post_init = post_init
    
    # ВАЖЛИВО: Додаємо обробник видалення команд ПЕРШИМ (найвищий пріоритет)
    app.add_handler(MessageHandler(filters.COMMAND, delete_commands), group=-1)
    
    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_add_checkin, pattern='^add_checkin$'), 
            CallbackQueryHandler(start_add_checkout, pattern='^add_checkout$')
        ], 
        states={
            ADDING_CHECKIN_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkin), 
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkin), 
                CommandHandler("done", done)
            ],
            NAMING_CHECKIN_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_checkin_media),
                CommandHandler("skip", name_checkin_media)
            ],
            ADDING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_checkout), 
                MessageHandler(filters.PHOTO | filters.ANIMATION | filters.VIDEO, receive_checkout), 
                CommandHandler("done", done)
            ],
            NAMING_CHECKOUT_MEDIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, name_checkout_media),
                CommandHandler("skip", name_checkout_media)
            ]
        }, 
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("checkin", checkin_command))
    app.add_handler(CommandHandler("checkout", checkout_command))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(buttons))
    print("🤖 Бот запущено!")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
