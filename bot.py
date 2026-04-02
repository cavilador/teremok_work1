# coding: utf-8

import logging
import re
import sqlite3
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    ContextTypes, 
    CallbackQueryHandler,
)
from config import Config
from trello_manager import TrelloManager

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('shifts.db', check_same_thread=False)
        self.create_tables()
    
    def create_tables(self):
        """Создание таблиц базы данных"""
        cursor = self.conn.cursor()
        
        # Таблица ожидающих заявок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pending_requests (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                host TEXT NOT NULL,
                cohost TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                full_time TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица одобренных смен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS approved_shifts (
                card_id TEXT PRIMARY KEY,
                card_url TEXT NOT NULL,
                host TEXT NOT NULL,
                cohost TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                approved_by TEXT NOT NULL,
                approved_by_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                approved_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица выполненных действий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sent_actions (
                card_id TEXT PRIMARY KEY,
                poll_sent BOOLEAN DEFAULT 0,
                poll_message_id INTEGER,
                channel_start_sent BOOLEAN DEFAULT 0,
                channel_scheduled_sent BOOLEAN DEFAULT 0,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Таблица сообщений пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_messages (
                user_id INTEGER,
                card_id TEXT,
                message_id INTEGER,
                PRIMARY KEY (user_id, card_id)
            )
        ''')
        
        # Таблица отмененных смен
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cancelled_shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                card_id TEXT NOT NULL,
                host TEXT NOT NULL,
                cohost TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL,
                cancelled_by TEXT NOT NULL,
                cancelled_by_id INTEGER NOT NULL,
                cancelled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                reason TEXT DEFAULT 'По техническим причинам'
            )
        ''')
        
        self.conn.commit()
    
    def add_pending_request(self, request_id, user_id, username, host, cohost, date, time, full_time):
        """Добавление заявки на ожидание"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO pending_requests 
            (id, user_id, username, host, cohost, date, time, full_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (request_id, user_id, username, host, cohost, date, time, full_time))
        self.conn.commit()
    
    def get_pending_request(self, request_id):
        """Получение заявки по ID"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM pending_requests WHERE id = ?', (request_id,))
        row = cursor.fetchone()
        if row:
            return {
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'host': row[3],
                'cohost': row[4],
                'date': row[5],
                'time': row[6],
                'full_time': row[7],
                'status': row[8],
                'timestamp': row[9]
            }
        return None
    
    def get_all_pending_requests(self):
        """Получение всех ожидающих заявок"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM pending_requests ORDER BY timestamp DESC')
        return [
            {
                'id': row[0],
                'user_id': row[1],
                'username': row[2],
                'host': row[3],
                'cohost': row[4],
                'date': row[5],
                'time': row[6],
                'full_time': row[7],
                'status': row[8],
                'timestamp': row[9]
            } for row in cursor.fetchall()
        ]
    
    def delete_pending_request(self, request_id):
        """Удаление заявки"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM pending_requests WHERE id = ?', (request_id,))
        self.conn.commit()
    
    def add_approved_shift(self, card_id, card_url, host, cohost, date, time, approved_by, approved_by_id, user_id):
        """Добавление одобренной смены"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO approved_shifts 
            (card_id, card_url, host, cohost, date, time, approved_by, approved_by_id, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (card_id, card_url, host, cohost, date, time, approved_by, approved_by_id, user_id))
        self.conn.commit()
    
    def get_approved_shift(self, card_id):
        """Получение смены по card_id"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM approved_shifts WHERE card_id = ?', (card_id,))
        row = cursor.fetchone()
        if row:
            return {
                'card_id': row[0],
                'card_url': row[1],
                'host': row[2],
                'cohost': row[3],
                'date': row[4],
                'time': row[5],
                'approved_by': row[6],
                'approved_by_id': row[7],
                'user_id': row[8],
                'approved_at': row[9]
            }
        return None
    
    def get_user_shifts(self, user_id):
        """Получение смен пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM approved_shifts WHERE user_id = ? ORDER BY approved_at DESC', (user_id,))
        return [
            {
                'card_id': row[0],
                'card_url': row[1],
                'host': row[2],
                'cohost': row[3],
                'date': row[4],
                'time': row[5],
                'approved_by': row[6],
                'approved_by_id': row[7],
                'user_id': row[8],
                'approved_at': row[9]
            } for row in cursor.fetchall()
        ]
    
    def get_all_approved_shifts(self):
        """Получение всех одобренных смен"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM approved_shifts ORDER BY approved_at DESC')
        return [
            {
                'card_id': row[0],
                'card_url': row[1],
                'host': row[2],
                'cohost': row[3],
                'date': row[4],
                'time': row[5],
                'approved_by': row[6],
                'approved_by_id': row[7],
                'user_id': row[8],
                'approved_at': row[9]
            } for row in cursor.fetchall()
        ]
    
    def add_cancelled_shift(self, card_id, host, cohost, date, time, cancelled_by, cancelled_by_id, reason="По техническим причинам"):
        """Добавление информации об отмененной смене"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO cancelled_shifts 
            (card_id, host, cohost, date, time, cancelled_by, cancelled_by_id, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (card_id, host, cohost, date, time, cancelled_by, cancelled_by_id, reason))
        self.conn.commit()
    
    def delete_approved_shift(self, card_id):
        """Удаление одобренной смены из базы данных"""
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM approved_shifts WHERE card_id = ?', (card_id,))
        cursor.execute('DELETE FROM sent_actions WHERE card_id = ?', (card_id,))
        cursor.execute('DELETE FROM user_messages WHERE card_id = ?', (card_id,))
        self.conn.commit()
    
    def add_sent_action(self, card_id, action_type, value=None):
        """Добавление информации о выполненном действии"""
        cursor = self.conn.cursor()
        
        cursor.execute('SELECT * FROM sent_actions WHERE card_id = ?', (card_id,))
        existing = cursor.fetchone()
        
        if existing:
            if action_type == 'poll_sent':
                cursor.execute('''
                    UPDATE sent_actions 
                    SET poll_sent = ?, poll_message_id = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE card_id = ?
                ''', (1, value, card_id))
            elif action_type == 'channel_start_sent':
                cursor.execute('''
                    UPDATE sent_actions 
                    SET channel_start_sent = 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE card_id = ?
                ''', (card_id,))
            elif action_type == 'channel_scheduled_sent':
                cursor.execute('''
                    UPDATE sent_actions 
                    SET channel_scheduled_sent = 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE card_id = ?
                ''', (card_id,))
        else:
            if action_type == 'poll_sent':
                cursor.execute('''
                    INSERT INTO sent_actions (card_id, poll_sent, poll_message_id)
                    VALUES (?, ?, ?)
                ''', (card_id, 1, value))
            elif action_type == 'channel_start_sent':
                cursor.execute('''
                    INSERT INTO sent_actions (card_id, channel_start_sent)
                    VALUES (?, ?)
                ''', (card_id, 1))
            elif action_type == 'channel_scheduled_sent':
                cursor.execute('''
                    INSERT INTO sent_actions (card_id, channel_scheduled_sent)
                    VALUES (?, ?)
                ''', (card_id, 1))
        
        self.conn.commit()
    
    def get_sent_actions(self, card_id):
        """Получение информации о выполненных действиях"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sent_actions WHERE card_id = ?', (card_id,))
        row = cursor.fetchone()
        if row:
            return {
                'card_id': row[0],
                'poll_sent': bool(row[1]),
                'poll_message_id': row[2],
                'channel_start_sent': bool(row[3]),
                'channel_scheduled_sent': bool(row[4]),
                'updated_at': row[5]
            }
        return None
    
    def add_user_message(self, user_id, card_id, message_id):
        """Добавление информации о сообщении пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO user_messages (user_id, card_id, message_id)
            VALUES (?, ?, ?)
        ''', (user_id, card_id, message_id))
        self.conn.commit()
    
    def get_user_message(self, user_id, card_id):
        """Получение ID сообщения пользователя"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT message_id FROM user_messages WHERE user_id = ? AND card_id = ?', (user_id, card_id))
        row = cursor.fetchone()
        return row[0] if row else None
    
    def get_all_user_messages_for_card(self, card_id):
        """Получение всех сообщений для конкретной карточки"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT user_id, message_id FROM user_messages WHERE card_id = ?', (card_id,))
        return {row[0]: row[1] for row in cursor.fetchall()}
    
    def close(self):
        """Закрытие соединения с базой данных"""
        self.conn.close()


class ShiftBot:
    def __init__(self):
        self.trello_manager = TrelloManager()
        self.db = Database()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = """
        👋 Здравствуйте!

        Добро пожаловать в портал персонала Теремок Roblox. Этот бот предназначен только для сотрудников компании.

        Если у вас есть вопрос или вам нужна помощь обратитесь в @teremokrobloxsupport_bot.
        """
        await update.message.reply_text(welcome_text)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = """
        📋 Доступные команды:
        
        /shift <Хост> <Со-Хост> <Дата> <Время> - Запросить новую смену
        /shifts - Показать все запланированные смены
        /myshifts - Показать мои одобренные смены с кнопками управления
        
        📅 Форматы даты:
        • сегодня / сегодняшний
        • завтра / завтрашний
        • послезавтра
        • 15.01 (день.месяц)
        
        ⏰ Форматы времени:
        • 20:00-22:00
        • 20:00 - 22:00
        
        ⚠️ Заявки проверяются администратором!
        """
        await update.message.reply_text(help_text)
    
    def parse_date(self, date_str):
        """Парсинг строки с датой"""
        today = datetime.now()
        date_str = date_str.lower().strip()
        
        if date_str in ['сегодня', 'сегодняшний']:
            return today
        elif date_str in ['завтра', 'завтрашний']:
            return today + timedelta(days=1)
        elif date_str == 'послезавтра':
            return today + timedelta(days=2)
        
        try:
            if '.' in date_str:
                parts = date_str.split('.')
                if len(parts) == 2:  # 15.01
                    day, month = int(parts[0]), int(parts[1])
                    year = today.year
                    if month < today.month or (month == today.month and day < today.day):
                        year += 1
                    return datetime(year, month, day)
                elif len(parts) == 3:  # 15.01.2024
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                    return datetime(year, month, day)
            
            month_dict = {
                'января': 1, 'янв': 1,
                'февраля': 2, 'фев': 2,
                'марта': 3, 'мар': 3,
                'апреля': 4, 'апр': 4,
                'мая': 5, 'май': 5,
                'июня': 6, 'июн': 6,
                'июля': 7, 'июл': 7,
                'августа': 8, 'авг': 8,
                'сентября': 9, 'сен': 9,
                'октября': 10, 'окт': 10,
                'ноября': 11, 'ноя': 11,
                'декабря': 12, 'дек': 12
            }
            
            for month_name, month_num in month_dict.items():
                if month_name in date_str:
                    day = int(re.search(r'\d+', date_str).group())
                    year = today.year
                    if month_num < today.month or (month_num == today.month and day < today.day):
                        year += 1
                    return datetime(year, month_num, day)
        
        except Exception as e:
            logger.error(f"Error parsing date: {date_str}, error: {e}")
        
        raise ValueError(f"Не удалось распознать дату: {date_str}")
    
    def parse_time(self, time_str):
        """Парсинг строки со временем"""
        time_str = time_str.lower().strip()
        
        time_str = time_str.replace('с ', '').replace('до ', '').replace('-', ' ').replace('по', ' ')
        
        time_pattern = r'(\d{1,2}):(\d{2})'
        times = re.findall(time_pattern, time_str)
        
        if len(times) >= 2:
            start_hour, start_minute = int(times[0][0]), int(times[0][1])
            end_hour, end_minute = int(times[1][0]), int(times[1][1])
            return f"{start_hour:02d}:{start_minute:02d}-{end_hour:02d}:{end_minute:02d}"
        
        hour_pattern = r'(\d{1,2})\s*(утра|дня|вечера|ночи|ночью)?'
        matches = re.findall(hour_pattern, time_str)
        
        if len(matches) >= 2:
            start_hour = int(matches[0][0])
            end_hour = int(matches[1][0])
            
            if 'вечера' in time_str or 'дня' in time_str:
                if start_hour < 12:
                    start_hour += 12
                if end_hour < 12:
                    end_hour += 12
            
            return f"{start_hour:02d}:00-{end_hour:02d}:00"
        
        return time_str
    
    async def shift_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /shift"""
        try:
            if not context.args or len(context.args) < 4:
                await update.message.reply_text(
                    "❌ Недостаточно аргументов.\n"
                    "Используйте: /shift <Хост> <Со-Хост> <Дата> <Время>\n"
                    "Пример: /shift 1x1x1x1_officalacc DDEEII00 завтра 20:00-22:00"
                )
                return
            
            host = context.args[0]
            cohost = context.args[1]
            date_str = context.args[2]
            time_str = ' '.join(context.args[3:])
            user_id = update.effective_user.id
            username = update.effective_user.username or update.effective_user.full_name
            
            try:
                date_obj = self.parse_date(date_str)
                formatted_date = date_obj.strftime('%d.%m.%Y')
            except ValueError as e:
                await update.message.reply_text(f"❌ {str(e)}")
                return
            
            try:
                formatted_time = self.parse_time(time_str)
            except Exception as e:
                await update.message.reply_text(f"❌ Не удалось распознать время: {time_str}")
                return
            
            request_id = f"{user_id}_{int(datetime.now().timestamp())}"
            
            # Сохраняем в базу данных
            self.db.add_pending_request(
                request_id, user_id, username, host, cohost, 
                formatted_date, formatted_time, f"{formatted_date} {formatted_time}"
            )
            
            await update.message.reply_text(
                "🔄 Заявка отправлена на одобрение администратору!\n"
                "Ожидайте подтверждения."
            )
            
            await self.send_approval_request(context, request_id)
            
        except Exception as e:
            logger.error(f"Error in shift_command: {e}")
            await update.message.reply_text(
                f"❌ Произошла ошибка: {str(e)}\n"
                "Попробуйте еще раз."
            )
    
    async def send_approval_request(self, context: ContextTypes.DEFAULT_TYPE, request_id: str):
        """Отправка заявки на одобрение в группу администраторов"""
        try:
            if not Config.ADMIN_CHAT_ID:
                logger.error("ADMIN_CHAT_ID не настроен в конфигурации")
                return
            
            request = self.db.get_pending_request(request_id)
            if not request:
                logger.error(f"Заявка {request_id} не найдена в базе данных")
                return
            
            message_text = (
                f"📋 НОВАЯ ЗАЯВКА НА СМЕНУ\n\n"
                f"👤 От: @{request['username']} (ID: {request['user_id']})\n"
                f"👤 Хост: {request['host']}\n"
                f"👥 Со-Хост: {request['cohost']}\n"
                f"📅 Дата: {request['date']}\n"
                f"⏰ Время: {request['time']}\n\n"
                f"🆔 ID заявки: {request_id}"
            )
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Одобрить", callback_data=f"a_{request_id}"),
                    InlineKeyboardButton("❌ Отказать", callback_data=f"r_{request_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=Config.ADMIN_CHAT_ID,
                text=message_text,
                reply_markup=reply_markup
            )
            
            logger.info(f"Заявка {request_id} отправлена на одобрение")
            
        except Exception as e:
            logger.error(f"Error sending approval request: {e}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка всех callback-ов"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        user_name = query.from_user.username or query.from_user.full_name
        user_id = query.from_user.id
        
        # Проверяем, откуда пришел callback (ЛС или группа админов)
        chat_type = query.message.chat.type
        
        # Обработка одобрения/отказа (только из группы админов)
        if callback_data.startswith('a_'):
            if chat_type != 'group' and chat_type != 'supergroup':
                await query.answer("❌ Эта команда только для администраторов")
                return
            request_id = callback_data.replace('a_', '')
            await self.approve_request(query, context, request_id, user_name, user_id)
        
        elif callback_data.startswith('r_'):
            if chat_type != 'group' and chat_type != 'supergroup':
                await query.answer("❌ Эта команда только для администраторов")
                return
            request_id = callback_data.replace('r_', '')
            await self.reject_request(query, context, request_id, user_name, user_id)
        
        # Обработка подтверждения отмены
        elif callback_data.startswith('confirm_cancel_'):
            card_id = callback_data.replace('confirm_cancel_', '')
            await self.handle_confirmed_cancel(query, context, card_id, user_name, user_id)
        
        # Обработка остальных действий в ЛС пользователя
        elif callback_data.startswith(('p_', 'c1_', 'c2_', 's_', 'h_', 'd_', 'b_', 'cancel_')):
            await self.handle_action_callback(query, context, callback_data, user_name, user_id)
    
    async def approve_request(self, query, context: ContextTypes.DEFAULT_TYPE, request_id: str, admin_name: str, admin_id: int):
        """Одобрение заявки"""
        try:
            request = self.db.get_pending_request(request_id)
            if not request:
                await query.edit_message_text("❌ Заявка не найдена или уже обработана")
                return
            
            result = self.trello_manager.create_card(
                request['host'], 
                request['cohost'], 
                request['full_time']
            )
            
            if result['success']:
                card_id = result.get('card_id')
                if not card_id:
                    await query.edit_message_text("❌ Не удалось получить ID карточки")
                    return
                
                # Сохраняем информацию об одобренной смене в базу данных
                self.db.add_approved_shift(
                    card_id, result['card_url'], request['host'], request['cohost'],
                    request['date'], request['time'], admin_name, admin_id, request['user_id']
                )
                
                # Отправляем сообщение с кнопками в ЛС пользователю
                await self.send_user_shift_controls(context, card_id, request['user_id'])
                
                # Обновляем сообщение в группе админов
                new_text = (
                    f"✅ ЗАЯВКА ОДОБРЕНА\n\n"
                    f"👤 Одобрил: @{admin_name}\n"
                    f"👤 Хост: {request['host']}\n"
                    f"👥 Со-Хост: {request['cohost']}\n"
                    f"📅 Дата: {request['date']}\n"
                    f"⏰ Время: {request['time']}\n\n"
                    f"📋 Карточка в Trello: {result['card_url']}\n\n"
                    f"✅ Кнопки управления отправлены в ЛС пользователю"
                )
                
                await query.edit_message_text(new_text)
                
                # Отправляем уведомление пользователю
                success_text = (
                    f"✅ Ваша заявка на смену одобрена!\n\n"
                    f"👤 Хост: {request['host']}\n"
                    f"👥 Со-Хост: {request['cohost']}\n"
                    f"📅 Дата: {request['date']}\n"
                    f"⏰ Время: {request['time']}\n\n"
                    f"🔗 Ссылка на карточку в Trello: {result['card_url']}\n\n"
                    f"📋 Используйте кнопки управления ниже для дальнейших действий."
                )
                await context.bot.send_message(
                    chat_id=request['user_id'],
                    text=success_text
                )
                
                # Удаляем заявку из ожидания
                self.db.delete_pending_request(request_id)
                logger.info(f"Заявка {request_id} одобрена администратором @{admin_name}")
                
            else:
                await query.edit_message_text(f"❌ Ошибка при создании карточки: {result['error']}")
                
        except Exception as e:
            logger.error(f"Error approving request: {e}")
            await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def send_user_shift_controls(self, context: ContextTypes.DEFAULT_TYPE, card_id: str, user_id: int):
        """Отправка кнопок управления сменой в ЛС пользователя"""
        try:
            shift_info = self.db.get_approved_shift(card_id)
            if not shift_info:
                logger.error(f"Смена с card_id {card_id} не найдена в базе")
                return
            
            sent_actions = self.db.get_sent_actions(card_id)
            
            # Создаем сообщение с кнопками
            message_text = (
                f"🔄 УПРАВЛЕНИЕ СМЕНОЙ\n\n"
                f"👤 Хост: {shift_info['host']}\n"
                f"👥 Со-Хост: {shift_info['cohost']}\n"
                f"📅 Дата: {shift_info['date']}\n"
                f"⏰ Время: {shift_info['time']}\n\n"
                f"🔗 {shift_info['card_url']}"
            )
            
            # Определяем текст кнопок
            poll_text = "📊 Опрос в стафф группу"
            channel_start_text = "📢 В канал (начало)"
            channel_scheduled_text = "📅 В канал (запланирована)"
            
            if sent_actions:
                if sent_actions['poll_sent']:
                    poll_text = "✅ Опрос отправлен"
                if sent_actions['channel_start_sent']:
                    channel_start_text = "✅ Начало отправлено"
                if sent_actions['channel_scheduled_sent']:
                    channel_scheduled_text = "✅ Запланирована отправлена"
            
            # Создаем кнопки
            keyboard = [
                [
                    InlineKeyboardButton(poll_text, callback_data=f"p_{card_id}"),
                    InlineKeyboardButton(channel_start_text, callback_data=f"c1_{card_id}"),
                    InlineKeyboardButton(channel_scheduled_text, callback_data=f"c2_{card_id}")
                ],
                [
                    InlineKeyboardButton("🔄 Изменить статус", callback_data=f"s_{card_id}")
                ],
                [
                    InlineKeyboardButton("❌ Отмена смены", callback_data=f"cancel_{card_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Отправляем сообщение с кнопками
            message = await context.bot.send_message(
                chat_id=user_id,
                text=message_text,
                reply_markup=reply_markup
            )
            
            # Сохраняем ID сообщения в базу данных
            self.db.add_user_message(user_id, card_id, message.message_id)
            
            logger.info(f"Кнопки управления отправлены пользователю {user_id} для карточки {card_id}")
            
        except Exception as e:
            logger.error(f"Error sending user controls: {e}")
    
    async def handle_action_callback(self, query, context: ContextTypes.DEFAULT_TYPE, callback_data: str, user_name: str, user_id: int):
        """Обработка действий (опрос, сообщение, статус, отмена) в ЛС"""
        try:
            # Разбираем callback_data
            parts = callback_data.split('_')
            if len(parts) < 2:
                await query.answer("❌ Неверный формат callback")
                return
            
            action_type = parts[0]
            card_id = '_'.join(parts[1:])  # На случай, если в card_id есть подчеркивания
            
            shift_info = self.db.get_approved_shift(card_id)
            if not shift_info:
                await query.answer("❌ Информация о смене не найдена")
                return
            
            # Проверяем права пользователя
            if user_id != shift_info['user_id'] and user_id != shift_info.get('approved_by_id'):
                await query.answer("❌ У вас нет прав для управления этой сменой")
                return
            
            if action_type == 'p':  # poll
                await self.handle_poll_action(query, context, card_id, shift_info)
            
            elif action_type == 'c1':  # channel start
                await self.handle_channel_start_action(query, context, card_id, shift_info)
            
            elif action_type == 'c2':  # channel scheduled
                await self.handle_channel_scheduled_action(query, context, card_id, shift_info)
            
            elif action_type == 's':  # status menu
                await self.show_status_menu(query, card_id)
            
            elif action_type in ['h', 'd', 'b']:  # status actions
                await self.handle_status_action(query, context, action_type, card_id, shift_info, user_name)
            
            elif action_type == 'cancel':  # cancel shift
                await self.cancel_shift_action(query, context, card_id, shift_info, user_name, user_id)
            
        except Exception as e:
            logger.error(f"Error handling action callback: {e}")
            await query.answer(f"❌ Ошибка: {str(e)[:100]}")
    
    async def cancel_shift_action(self, query, context, card_id, shift_info, user_name, user_id):
        """Обработка отмены смены - показ подтверждения"""
        try:
            # Подтверждение отмены
            confirm_keyboard = [
                [
                    InlineKeyboardButton("✅ Да, отменить", callback_data=f"confirm_cancel_{card_id}"),
                    InlineKeyboardButton("❌ Нет, вернуться", callback_data=f"b_{card_id}")
                ]
            ]
            confirm_markup = InlineKeyboardMarkup(confirm_keyboard)
            
            await query.edit_message_text(
                text=f"⚠️ ВЫ УВЕРЕНЫ, ЧТО ХОТИТЕ ОТМЕНИТЬ СМЕНУ?\n\n"
                     f"📅 Дата: {shift_info['date']}\n"
                     f"⏰ Время: {shift_info['time']}\n"
                     f"👤 Хост: {shift_info['host']}\n"
                     f"👥 Со-Хост: {shift_info['cohost']}\n\n"
                     f"✅ При отмене:\n"
                     f"• В стафф группу отправится уведомление\n"
                     f"• В канал отправится сообщение об отмене\n"
                     f"• Карточка Trello будет удалена\n\n"
                     f"❌ Это действие нельзя отменить!",
                reply_markup=confirm_markup
            )
            
        except Exception as e:
            logger.error(f"Error in cancel confirmation: {e}")
            await query.answer(f"❌ Ошибка: {str(e)[:100]}")
    
    async def handle_confirmed_cancel(self, query, context, card_id, user_name, user_id):
        """Обработка подтвержденной отмены смены"""
        try:
            shift_info = self.db.get_approved_shift(card_id)
            if not shift_info:
                await query.answer("❌ Смена не найдена в базе данных")
                return
            
            # Уведомляем о начале процесса
            await query.answer("⏳ Отменяем смену...")
            
            # Отправляем сообщение в стафф группу
            if Config.STAFF_CHAT_ID:
                staff_message = (

                    f"Дата и время: {shift_info['date']} {shift_info['time']}\n"
                    f"Хост: {shift_info['host']}\n"
                    f"Со-Хост: {shift_info['cohost']}\n\n"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=Config.STAFF_CHAT_ID,
                        text=staff_message
                    )
                    logger.info(f"Уведомление об отмене отправлено в стафф группу")
                except Exception as e:
                    logger.error(f"Ошибка отправки в стафф группу: {e}")
            
            # Отправляем сообщение в канал
            if Config.CHANNEL_CHAT_ID:
                channel_message = (
                    f"ВНИМАНИЕ: ОТМЕНА СМЕНЫ\n\n"
                    f"Смена, запланированная на {shift_info['date']} {shift_info['time']} отменена. "
                    f"Приносим извинения за неудобства.\n"
                    f"Следите за анонсами новых смен!"
                )
                
                try:
                    await context.bot.send_message(
                        chat_id=Config.CHANNEL_CHAT_ID,
                        text=channel_message
                    )
                    logger.info(f"Уведомление об отмене отправлено в канал")
                except Exception as e:
                    logger.error(f"Ошибка отправки в канал: {e}")
            
            # Удаляем карточку в Trello
            delete_result = self.trello_manager.delete_card(card_id)
            if not delete_result.get('success'):
                logger.error(f"Ошибка при удалении карточки в Trello: {delete_result.get('error')}")
                # Продолжаем выполнение даже если ошибка Trello
            
            # Сохраняем информацию об отмене в базу данных
            self.db.add_cancelled_shift(
                card_id, shift_info['host'], shift_info['cohost'],
                shift_info['date'], shift_info['time'], user_name, user_id,
                "Отменено пользователем через бота"
            )
            
            # Удаляем смену из базы данных
            self.db.delete_approved_shift(card_id)
            
            # Уведомляем пользователя об успешной отмене
            success_message = (
                f"✅ СМЕНА УСПЕШНО ОТМЕНЕНА!\n\n"
                f"📅 Дата: {shift_info['date']}\n"
                f"⏰ Время: {shift_info['time']}\n"
                f"👤 Хост: {shift_info['host']}\n"
                f"👥 Со-Хост: {shift_info['cohost']}\n\n"
            )
            
            if delete_result.get('success'):
                success_message += "✅ Карточка Trello удалена\n"
            else:
                success_message += f"⚠️ Карточка Trello не удалена: {delete_result.get('error', 'неизвестная ошибка')}\n"
            
            if Config.STAFF_CHAT_ID:
                success_message += "✅ Уведомление отправлено в стафф группу\n"
            
            if Config.CHANNEL_CHAT_ID:
                success_message += "✅ Анонс об отмене отправлен в канал\n"
            
            await query.edit_message_text(
                text=success_message,
                reply_markup=None
            )
            
            logger.info(f"Смена {card_id} отменена пользователем @{user_name}")
            
        except Exception as e:
            logger.error(f"Error in confirmed cancel: {e}")
            await query.edit_message_text(
                text=f"❌ Произошла ошибка при отмене смены:\n\n{str(e)[:200]}"
            )
    
    async def handle_poll_action(self, query, context, card_id, shift_info):
        """Обработка отправки опроса"""
        sent_actions = self.db.get_sent_actions(card_id)
        if sent_actions and sent_actions.get('poll_sent'):
            await query.answer("❌ Опрос уже был отправлен ранее")
            return
        
        if not Config.STAFF_CHAT_ID:
            await query.answer("❌ STAFF_CHAT_ID не настроен")
            return
        
        # Создаем опрос
        poll_question = f"Придете ли вы на смену {shift_info['date']} в {shift_info['time']}?"
        poll_options = ["✅ Да", "❌ Нет"]
        
        try:
            poll_message = await context.bot.send_poll(
                chat_id=Config.STAFF_CHAT_ID,
                question=poll_question,
                options=poll_options,
                is_anonymous=False,
                allows_multiple_answers=False
            )
            
            # Сохраняем информацию об отправленном опросе
            self.db.add_sent_action(card_id, 'poll_sent', poll_message.message_id)
            await query.answer("✅ Опрос отправлен в стафф группу")
            
            # Обновляем кнопки во всех сообщениях пользователей
            await self.update_all_action_buttons(card_id, context)
        
        except Exception as e:
            logger.error(f"Error sending poll: {e}")
            await query.answer(f"❌ Ошибка отправки опроса: {str(e)[:100]}")
    
    async def handle_channel_start_action(self, query, context, card_id, shift_info):
        """Обработка отправки сообщения о начале смены"""
        sent_actions = self.db.get_sent_actions(card_id)
        if sent_actions and sent_actions.get('channel_start_sent'):
            await query.answer("❌ Сообщение о начале уже было отправлено в канал ранее")
            return
        
        if not Config.CHANNEL_CHAT_ID:
            await query.answer("❌ CHANNEL_CHAT_ID не настроен")
            return
        
        from telegram.constants import ParseMode
        
        # Сообщение о начале смены
        channel_message_start = (
            "<b>Смена в Теремке началась!</b>\n"
            "\n"
            "https://www.roblox.com/games/82007520505614/Teremok-Saint-Petersburg-Bolshaya-Morskaya-11\n"
            "\n"
            "<b>Для улучшения вашего посещения советуем играть с компьютера или ноутбука а также зайти в нашу <a href=\"https://www.roblox.com/groups/33873170/PBO-rblx#!/about\">Roblox группу</a></b>\n"
            "\n"
            "<i>Партнеры, будем рады вашему пиару.</i>"
        )
        
        try:
            if hasattr(Config, 'IMAGE_URL_START') and Config.IMAGE_URL_START:
                await context.bot.send_photo(
                    chat_id=Config.CHANNEL_CHAT_ID,
                    photo=Config.IMAGE_URL_START,
                    caption=channel_message_start,
                    parse_mode=ParseMode.HTML
                )
            else:
                await context.bot.send_message(
                    chat_id=Config.CHANNEL_CHAT_ID,
                    text=channel_message_start,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
            
            self.db.add_sent_action(card_id, 'channel_start_sent')
            await query.answer("✅ Сообщение о начале отправлено в канал")
            await self.update_all_action_buttons(card_id, context)
        
        except Exception as e:
            logger.error(f"Error sending start message to channel: {e}")
            await query.answer(f"❌ Ошибка отправки: {str(e)[:100]}")
    
    async def handle_channel_scheduled_action(self, query, context, card_id, shift_info):
        """Обработка отправки сообщения о запланированной смене"""
        sent_actions = self.db.get_sent_actions(card_id)
        if sent_actions and sent_actions.get('channel_scheduled_sent'):
            await query.answer("❌ Сообщение о запланированной смене уже было отправлено в канал ранее")
            return
        
        if not Config.CHANNEL_CHAT_ID:
            await query.answer("❌ CHANNEL_CHAT_ID не настроен")
            return
        
        from telegram.constants import ParseMode
        
        channel_message_scheduled = (
            f"<b>Новая смена запланирована!</b>\n"
            "\n"
            f"<b>Хост:</b> {shift_info['host']}\n"
            f"<b>Дата и время:</b> {shift_info['date']} {shift_info['time']}\n"
            f"<b>Место:</b> <a href=\"https://www.roblox.com/games/82007520505614/Teremok-Saint-Petersburg-Bolshaya-Morskaya-11\">Санкт-Петербург, Большая Морская улица 11А</a>\n"
            "\n"
            "<i>Будем ждать вас!</i>"
        )
        
        try:
            if hasattr(Config, 'IMAGE_URL_SCHEDULED') and Config.IMAGE_URL_SCHEDULED:
                await context.bot.send_photo(
                    chat_id=Config.CHANNEL_CHAT_ID,
                    photo=Config.IMAGE_URL_SCHEDULED,
                    caption=channel_message_scheduled,
                    parse_mode=ParseMode.HTML
                )
            else:
                await context.bot.send_message(
                    chat_id=Config.CHANNEL_CHAT_ID,
                    text=channel_message_scheduled,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=False
                )
            
            self.db.add_sent_action(card_id, 'channel_scheduled_sent')
            await query.answer("✅ Сообщение о запланированной смене отправлено в канал")
            await self.update_all_action_buttons(card_id, context)
        
        except Exception as e:
            logger.error(f"Error sending scheduled message to channel: {e}")
            await query.answer(f"❌ Ошибка отправки: {str(e)[:100]}")
    
    async def show_status_menu(self, query, card_id):
        """Показ меню выбора статуса"""
        status_keyboard = [
            [
                InlineKeyboardButton("🟡 ПРОИСХОДИТ", callback_data=f"h_{card_id}"),
                InlineKeyboardButton("🟢 ПРОВЕДЕН", callback_data=f"d_{card_id}")
            ],
            [
                InlineKeyboardButton("🔙 Назад", callback_data=f"b_{card_id}")
            ]
        ]
        status_markup = InlineKeyboardMarkup(status_keyboard)
        
        await query.edit_message_reply_markup(reply_markup=status_markup)
        await query.answer("Выберите новый статус")
    
    async def handle_status_action(self, query, context, action_type, card_id, shift_info, user_name):
        """Обработка изменения статуса"""
        if action_type == 'b':  # back
            await self.update_message_buttons(query, card_id, context)
            await query.answer("Вернулись к основным действиям")
            return
        
        # Определяем новый статус
        if action_type == 'h':  # happening
            new_label = Config.TRELLO_LABEL_HAPPENING
            status_name = "ПРОИСХОДИТ"
        elif action_type == 'd':  # done
            new_label = Config.TRELLO_LABEL_DONE
            status_name = "ПРОВЕДЕН"
        else:
            await query.answer("❌ Неизвестный статус")
            return
        
        # Обновляем статус в Trello
        logger.info(f"Changing status for card {card_id} to {new_label}")
        result = self.trello_manager.update_card_label(shift_info['card_url'], new_label)
        
        if result['success']:
            await query.answer(f"✅ Статус изменен на {status_name}")
            await self.update_all_action_buttons(card_id, context)
            logger.info(f"Статус смены {card_id} изменен на {new_label} пользователем @{user_name}")
        else:
            logger.error(f"Error updating status: {result['error']}")
            await query.answer(f"❌ {result['error']}")
    
    async def update_all_action_buttons(self, card_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Обновление кнопок во всех сообщениях для этой карточки"""
        try:
            shift_info = self.db.get_approved_shift(card_id)
            if not shift_info:
                return
            
            sent_actions = self.db.get_sent_actions(card_id)
            
            # Определяем текст кнопок
            poll_text = "📊 Опрос в стафф группу"
            channel_start_text = "📢 В канал (начало)"
            channel_scheduled_text = "📅 В канал (запланирована)"
            
            if sent_actions:
                if sent_actions.get('poll_sent'):
                    poll_text = "✅ Опрос отправлен"
                if sent_actions.get('channel_start_sent'):
                    channel_start_text = "✅ Начало отправлено"
                if sent_actions.get('channel_scheduled_sent'):
                    channel_scheduled_text = "✅ Запланирована отправлена"
            
            # Создаем обновленные кнопки
            keyboard = [
                [
                    InlineKeyboardButton(poll_text, callback_data=f"p_{card_id}"),
                    InlineKeyboardButton(channel_start_text, callback_data=f"c1_{card_id}"),
                    InlineKeyboardButton(channel_scheduled_text, callback_data=f"c2_{card_id}")
                ],
                [
                    InlineKeyboardButton("🔄 Изменить статус", callback_data=f"s_{card_id}")
                ],
                [
                    InlineKeyboardButton("❌ Отмена смены", callback_data=f"cancel_{card_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Получаем все сообщения для этой карточки
            messages = self.db.get_all_user_messages_for_card(card_id)
            
            # Обновляем каждое сообщение
            for user_id, message_id in messages.items():
                try:
                    await context.bot.edit_message_reply_markup(
                        chat_id=user_id,
                        message_id=message_id,
                        reply_markup=reply_markup
                    )
                except Exception as e:
                    logger.error(f"Error updating buttons for user {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error updating all action buttons: {e}")
    
    async def update_message_buttons(self, query, card_id: str, context: ContextTypes.DEFAULT_TYPE):
        """Обновление кнопок в конкретном сообщении"""
        try:
            shift_info = self.db.get_approved_shift(card_id)
            if not shift_info:
                return
            
            sent_actions = self.db.get_sent_actions(card_id)
            
            # Определяем текст кнопок
            poll_text = "📊 Опрос в стафф группу"
            channel_start_text = "📢 Начало"
            channel_scheduled_text = "📅 Планирование"
            
            if sent_actions:
                if sent_actions.get('poll_sent'):
                    poll_text = "✅ Опрос отправлен"
                if sent_actions.get('channel_start_sent'):
                    channel_start_text = "✅ Начало отправлено"
                if sent_actions.get('channel_scheduled_sent'):
                    channel_scheduled_text = "✅ Запланирование отправлено"
            
            # Создаем обновленные кнопки
            keyboard = [
                [
                    InlineKeyboardButton(poll_text, callback_data=f"p_{card_id}"),
                    InlineKeyboardButton(channel_start_text, callback_data=f"c1_{card_id}"),
                    InlineKeyboardButton(channel_scheduled_text, callback_data=f"c2_{card_id}")
                ],
                [
                    InlineKeyboardButton("🔄 Изменить статус", callback_data=f"s_{card_id}")
                ],
                [
                    InlineKeyboardButton("❌ Отмена смены", callback_data=f"cancel_{card_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_reply_markup(reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error updating message buttons: {e}")
    
    async def reject_request(self, query, context: ContextTypes.DEFAULT_TYPE, request_id: str, admin_name: str, admin_id: int):
        """Отказ в заявке"""
        try:
            request = self.db.get_pending_request(request_id)
            if not request:
                await query.edit_message_text("❌ Заявка не найдена или уже обработана")
                return
            
            new_text = (
                f"❌ ЗАЯВКА ОТКЛОНЕНА\n\n"
                f"👤 Отклонил: @{admin_name}\n"
                f"👤 Хост: {request['host']}\n"
                f"👥 Со-Хост: {request['cohost']}\n"
                f"📅 Дата: {request['date']}\n"
                f"⏰ Время: {request['time']}\n"
            )
            await query.edit_message_text(new_text)
            
            reject_text = (
                f"❌ Ваша заявка на смену отклонена.\n\n"
                f"👤 Хост: {request['host']}\n"
                f"👥 Со-Хост: {request['cohost']}\n"
                f"📅 Дата: {request['date']}\n"
                f"⏰ Время: {request['time']}\n\n"
                f"ℹ️ По вопросам обращайтесь к руководству."
            )
            await context.bot.send_message(
                chat_id=request['user_id'],
                text=reject_text
            )
            
            # Удаляем заявку из базы данных
            self.db.delete_pending_request(request_id)
            logger.info(f"Заявка {request_id} отклонена администратором @{admin_name}")
            
        except Exception as e:
            logger.error(f"Error rejecting request: {e}")
            await query.edit_message_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def myshifts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать мои смены с кнопками управления"""
        try:
            user_id = update.effective_user.id
            
            # Получаем смены пользователя из базы данных
            user_shifts = self.db.get_user_shifts(user_id)
            
            if not user_shifts:
                await update.message.reply_text("📭 У вас нет одобренных смен.")
                return
            
            for shift in user_shifts:
                # Отправляем сообщение с кнопками для каждой смены
                await self.send_user_shift_controls(context, shift['card_id'], user_id)
            
            await update.message.reply_text(f"📋 Отправлено {len(user_shifts)} смен с кнопками управления.")
            
        except Exception as e:
            logger.error(f"Error in myshifts_command: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    async def shifts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать все запланированные смены"""
        try:
            # Получаем смены из Trello и из базы данных
            trello_cards = self.trello_manager.get_all_cards()
            db_shifts = self.db.get_all_approved_shifts()
            
            if not trello_cards and not db_shifts:
                await update.message.reply_text("📭 Нет запланированных смен.")
                return
            
            # Собираем все смены
            all_shifts = []
            
            # Добавляем смены из Trello
            for card in trello_cards:
                shift_info = {
                    'name': card.get('name', 'Без названия'),
                    'url': card.get('url', 'Нет ссылки'),
                    'labels': card.get('labels', []),
                    'host': 'Не указан',
                    'cohost': 'Не указан',
                    'date_time': 'Не указано'
                }
                
                if card.get('description'):
                    lines = card['description'].split('\n')
                    for line in lines:
                        if line.startswith('Host:'):
                            shift_info['host'] = line.replace('Host:', '').strip()
                        elif line.startswith('Co-Host:'):
                            shift_info['cohost'] = line.replace('Co-Host:', '').strip()
                        elif 'Дата и время:' in line:
                            shift_info['date_time'] = line.replace('Дата и время:', '').strip()
                
                all_shifts.append(shift_info)
            
            # Добавляем смены из базы данных (если их нет в Trello)
            for shift in db_shifts:
                # Проверяем, есть ли уже эта смена в списке
                found = False
                for trello_shift in all_shifts:
                    if shift['card_url'] == trello_shift['url']:
                        found = True
                        break
                
                if not found:
                    all_shifts.append({
                        'name': f"Смена {shift['date']} {shift['time']}",
                        'url': shift['card_url'],
                        'labels': ['Из базы данных'],
                        'host': shift['host'],
                        'cohost': shift['cohost'],
                        'date_time': f"{shift['date']} {shift['time']}"
                    })
            
            # Разбиваем на группы по 5 смен в сообщении
            for i in range(0, len(all_shifts), 5):
                message = "📋 ЗАПЛАНИРОВАННЫЕ СМЕНЫ:\n\n"
                batch = all_shifts[i:i+5]
                
                for shift in batch:
                    status = ", ".join(shift['labels']) if shift['labels'] else "Не указан"
                    message += (
                        f"📅 {shift['name']}\n"
                        f"👤 Хост: {shift['host']}\n"
                        f"👥 Со-Хост: {shift['cohost']}\n"
                        f"⏰ {shift['date_time']}\n"
                        f"🏷️ Статус: {status}\n"
                        f"🔗 {shift['url']}\n"
                        f"────────────────────\n"
                    )
                
                await update.message.reply_text(message)
                
        except Exception as e:
            logger.error(f"Error in shifts_command: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка при получении смен: {str(e)}")
    
    async def list_pending(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список ожидающих заявок (для админов)"""
        try:
            chat_id = update.effective_chat.id
            if str(chat_id) != str(Config.ADMIN_CHAT_ID):
                await update.message.reply_text("❌ Эта команда только для администраторов")
                return
            
            pending_requests = self.db.get_all_pending_requests()
            
            if not pending_requests:
                await update.message.reply_text("📭 Нет ожидающих заявок.")
                return
            
            message = "📋 Ожидающие заявки:\n\n"
            for req in pending_requests[:10]:
                message += (
                    f"🆔 ID: {req['id']}\n"
                    f"👤 От: @{req['username']}\n"
                    f"👤 Хост: {req['host']}\n"
                    f"👥 Со-Хост: {req['cohost']}\n"
                    f"📅 Дата: {req['date']}\n"
                    f"⏰ Время: {req['time']}\n"
                    f"🕐 Отправлено: {req['timestamp']}\n"
                    f"────────────────────\n"
                )
            
            await update.message.reply_text(message)
            
        except Exception as e:
            logger.error(f"Error in list_pending: {e}")
            await update.message.reply_text(f"❌ Произошла ошибка: {str(e)}")
    
    def run(self):
        """Запуск бота"""
        application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("shift", self.shift_command))
        application.add_handler(CommandHandler("shifts", self.shifts_command))
        application.add_handler(CommandHandler("myshifts", self.myshifts_command))
        application.add_handler(CommandHandler("pending", self.list_pending))
        
        # Обработчик всех callback-ов (включая новую кнопку отмены)
        application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("Бот запущен...")
        application.run_polling(drop_pending_updates=True)
    
    def __del__(self):
        """Деструктор для закрытия соединения с БД"""
        if hasattr(self, 'db'):
            self.db.close()

def main():
    """Основная функция запуска"""
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ Ошибка: TELEGRAM_BOT_TOKEN не найден в .env файле")
        return
    
    if not Config.ADMIN_CHAT_ID:
        print("⚠️ Внимание: ADMIN_CHAT_ID не настроен. Заявки не будут отправляться на одобрение.")
    
    bot = ShiftBot()
    bot.run()

if __name__ == '__main__':
    main()