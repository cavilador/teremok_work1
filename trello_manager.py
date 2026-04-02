# coding: utf-8

from trello import TrelloClient
from trello.exceptions import ResourceUnavailable
from datetime import datetime
import pytz
import re
import logging
from typing import Optional, Dict, List, Any
from config import Config
import requests

logger = logging.getLogger(__name__)

class TrelloTimeManager:
    """Класс для работы с временем в Trello"""
    
    MOSCOW_TZ = pytz.timezone('Europe/Moscow')
    
    @staticmethod
    def parse_datetime_from_string(time_str: str) -> Optional[datetime]:
        """Парсинг даты и времени из строки с учетом московского времени"""
        try:
            # Пытаемся найти полный формат: дд.мм.гггг чч:мм-чч:мм
            full_match = re.search(r'(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})', time_str)
            if full_match:
                date_str = full_match.group(1)
                time_str = full_match.group(2)
                dt_naive = datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
                return TrelloTimeManager.MOSCOW_TZ.localize(dt_naive)
            
            # Пытаемся найти дату без времени
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', time_str)
            if date_match:
                date_str = date_match.group(1)
                dt_naive = datetime.strptime(date_str, "%d.%m.%Y")
                # Устанавливаем время на 00:00
                dt_naive = dt_naive.replace(hour=0, minute=0)
                return TrelloTimeManager.MOSCOW_TZ.localize(dt_naive)
            
            return None
        except Exception as e:
            logger.error(f"Ошибка парсинга времени из строки '{time_str}': {e}")
            return None
    
    @staticmethod
    def to_utc_for_trello(moscow_dt: datetime) -> Optional[datetime]:
        """Конвертация московского времени в UTC для Trello"""
        try:
            return moscow_dt.astimezone(pytz.UTC)
        except Exception as e:
            logger.error(f"Ошибка конвертации времени в UTC: {e}")
            return None
    
    @staticmethod
    def extract_date_for_card_name(time_str: str) -> str:
        """Извлечение даты для названия карточки"""
        try:
            date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', time_str)
            if date_match:
                return date_match.group(1)
            
            date_match = re.search(r'(\d{2}\.\d{2})', time_str)
            if date_match:
                return date_match.group(1)
            
            # Если дата не найдена, используем текущую
            return datetime.now(TrelloTimeManager.MOSCOW_TZ).strftime('%d.%m.%Y')
        except Exception as e:
            logger.error(f"Ошибка извлечения даты: {e}")
            return datetime.now(TrelloTimeManager.MOSCOW_TZ).strftime('%d.%m.%Y')


class TrelloCardManager:
    """Класс для управления карточками Trello"""
    
    def __init__(self, client):
        self.client = client
    
    def extract_card_id(self, card_url: str) -> Optional[str]:
        """Извлечение ID карточки из URL"""
        try:
            # Убираем пробелы в начале и конце
            card_url = card_url.strip()
            
            # Убираем возможные угловые скобки
            card_url = card_url.strip('<>')
            
            # Если это уже ID (24 символа), возвращаем как есть
            if len(card_url) == 24 and card_url.isalnum():
                return card_url
            
            # Разные паттерны для извлечения ID
            patterns = [
                r'trello\.com/c/([a-zA-Z0-9]{8})',  # 8 символов для коротких URL
                r'/([a-fA-F0-9]{24})/',  # 24 символа в середине URL
                r'/([a-fA-F0-9]{24})$',  # 24 символа в конце
                r'/([a-fA-F0-9]{24})\?', # 24 символа перед параметрами
                r'/c/([a-zA-Z0-9]{8,})',  # Короткий ID (8+ символов)
            ]
            
            for pattern in patterns:
                match = re.search(pattern, card_url)
                if match:
                    return match.group(1)
            
            # Если есть /c/ в URL, берем следующий сегмент
            if '/c/' in card_url:
                parts = card_url.split('/c/')
                if len(parts) > 1:
                    # Берем первый сегмент после /c/
                    possible_id = parts[1].split('/')[0].split('?')[0]
                    if len(possible_id) >= 8:  # Минимум 8 символов
                        return possible_id
            
            # Пробуем найти ID в любой части URL
            url_parts = card_url.split('/')
            for part in url_parts:
                if len(part) >= 8 and part.isalnum():
                    return part
            
            logger.warning(f"Не удалось извлечь ID из URL: {card_url}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка при извлечении ID: {e}")
            return None
    
    def get_card_by_url(self, card_url: str) -> Optional[Any]:
        """Получение карточки по URL"""
        card_id = self.extract_card_id(card_url)
        if not card_id:
            logger.error(f"Не удалось извлечь ID из URL: {card_url}")
            return None
        
        try:
            return self.client.get_card(card_id)
        except Exception as e:
            logger.error(f"Ошибка получения карточки {card_id}: {e}")
            return None
    
    def get_card_by_id(self, card_id: str) -> Optional[Any]:
        """Получение карточки по ID"""
        try:
            return self.client.get_card(card_id)
        except Exception as e:
            logger.error(f"Ошибка получения карточки {card_id}: {e}")
            return None


class TrelloLabelManager:
    """Класс для управления метками Trello"""
    
    def __init__(self, board):
        self.board = board
        self._labels_cache = None
    
    def get_all_labels(self) -> List[Any]:
        """Получение всех меток доски"""
        if self._labels_cache is None:
            try:
                self._labels_cache = self.board.get_labels()
            except Exception as e:
                logger.error(f"Ошибка получения меток: {e}")
                self._labels_cache = []
        return self._labels_cache
    
    def get_label_by_name(self, label_name: str) -> Optional[Any]:
        """Получение метки по имени"""
        labels = self.get_all_labels()
        for label in labels:
            if label.name.lower() == label_name.lower():
                return label
        return None
    
    def update_card_labels(self, card, new_label_name: str, status_labels_to_remove: List[str]) -> bool:
        """Обновление меток карточки"""
        try:
            # Удаляем старые метки статуса
            current_labels = card.labels
            for label in current_labels:
                if label.name in status_labels_to_remove:
                    logger.info(f"Удаление старой метки: {label.name}")
                    card.remove_label(label)
            
            # Добавляем новую метку
            new_label = self.get_label_by_name(new_label_name)
            if new_label:
                logger.info(f"Добавление новой метки: {new_label_name}")
                card.add_label(new_label)
                return True
            else:
                logger.error(f"Метка '{new_label_name}' не найдена")
                return False
        except Exception as e:
            logger.error(f"Ошибка обновления меток: {e}")
            return False


class TrelloManager:
    def __init__(self):
        self.client = TrelloClient(
            api_key=Config.TRELLO_API_KEY,
            api_secret=Config.TRELLO_API_SECRET,
            token=Config.TRELLO_TOKEN
        )
        self.time_manager = TrelloTimeManager()
        self.card_manager = TrelloCardManager(self.client)
        self._board_cache = None
    
    def get_board(self) -> Any:
        """Получение доски Trello"""
        if self._board_cache is None:
            try:
                self._board_cache = self.client.get_board(Config.TRELLO_BOARD_ID)
            except ResourceUnavailable:
                raise Exception(f"Доска с ID {Config.TRELLO_BOARD_ID} не найдена")
            except Exception as e:
                raise Exception(f"Ошибка получения доски: {str(e)}")
        return self._board_cache
    
    def get_list_by_name(self, list_name: str) -> Optional[Any]:
        """Получение списка по имени"""
        try:
            board = self.get_board()
            lists = board.list_lists()
            for lst in lists:
                if lst.name.lower() == list_name.lower():
                    return lst
            return None
        except Exception as e:
            logger.error(f"Ошибка получения списка '{list_name}': {e}")
            return None
    
    def create_card(self, host: str, cohost: str, time_info: str) -> Dict[str, Any]:
        """Создание карточки с правильным временем"""
        try:
            board = self.get_board()
            
            # Получаем список
            trello_list = self.get_list_by_name(Config.TRELLO_LIST_NAME)
            if not trello_list:
                raise Exception(f"Список '{Config.TRELLO_LIST_NAME}' не найден")
            
            # Получаем метку
            label_manager = TrelloLabelManager(board)
            waiting_label = label_manager.get_label_by_name(Config.TRELLO_LABEL_WAITING)
            
            # Создаем описание
            description = f"Host: {host}\nCo-Host: {cohost}\nДата и время: {time_info}"
            
            # Создаем название карточки
            card_date = self.time_manager.extract_date_for_card_name(time_info)
            card_name = f"Смена от {card_date}"
            
            # Создаем карточку
            logger.info(f"Создание карточки '{card_name}'")
            card = trello_list.add_card(name=card_name, desc=description)
            
            # Добавляем метку
            if waiting_label:
                card.add_label(waiting_label)
            
            # Устанавливаем срок (due date)
            moscow_dt = self.time_manager.parse_datetime_from_string(time_info)
            if moscow_dt:
                utc_dt = self.time_manager.to_utc_for_trello(moscow_dt)
                if utc_dt:
                    try:
                        card.set_due(utc_dt)
                        logger.info(f"Установлен срок: {moscow_dt.strftime('%d.%m.%Y %H:%M MSK')}")
                        
                        if hasattr(card, 'set_reminder'):
                            try:
                                card.set_reminder(60)
                                logger.info("Установлено напоминание за 60 минут")
                            except Exception as e:
                                logger.warning(f"Не удалось установить напоминание: {e}")
                    except Exception as e:
                        logger.warning(f"Не удалось установить срок через datetime объект: {e}")
                        
                        try:
                            iso_date = utc_dt.isoformat()
                            card.set_due(iso_date)
                            logger.info(f"Установлен срок через ISO строку: {iso_date}")
                        except Exception as e2:
                            logger.warning(f"Не удалось установить срок через ISO строку: {e2}")
            
            return {
                'success': True,
                'card_url': card.url,
                'card_name': card_name,
                'card_id': card.id,
                'card_description': description,
                'due_date_set': moscow_dt is not None,
                'short_url': card.short_url if hasattr(card, 'short_url') else card.url
            }
            
        except Exception as e:
            logger.error(f"Ошибка создания карточки: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Получение всех карточек из списка смен"""
        try:
            trello_list = self.get_list_by_name(Config.TRELLO_LIST_NAME)
            if not trello_list:
                logger.error(f"Список '{Config.TRELLO_LIST_NAME}' не найден")
                return []
            
            cards = trello_list.list_cards()
            card_data = []
            
            for card in cards:
                try:
                    due_date = None
                    if hasattr(card, 'due_date') and card.due_date:
                        try:
                            due_str = str(card.due_date)
                            if 'Z' in due_str:
                                utc_dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                            elif '+' in due_str:
                                utc_dt = datetime.fromisoformat(due_str)
                            else:
                                due_date = due_str
                                utc_dt = None
                            
                            if utc_dt:
                                moscow_dt = utc_dt.astimezone(self.time_manager.MOSCOW_TZ)
                                due_date = moscow_dt.strftime('%d.%m.%Y %H:%M MSK')
                        except Exception as dt_error:
                            logger.warning(f"Ошибка парсинга даты {card.due_date}: {dt_error}")
                            due_date = str(card.due_date)
                    
                    card_info = {
                        'name': card.name,
                        'url': card.url,
                        'description': card.desc if hasattr(card, 'desc') else '',
                        'labels': [label.name for label in card.labels] if hasattr(card, 'labels') else [],
                        'due_date': due_date,
                        'card_id': card.id,
                        'short_url': card.short_url if hasattr(card, 'short_url') else card.url
                    }
                    card_data.append(card_info)
                except Exception as e:
                    logger.error(f"Ошибка обработки карточки {card.id}: {e}")
                    continue
            
            return card_data
            
        except Exception as e:
            logger.error(f"Ошибка получения карточек: {e}")
            return []
    
    def update_card_label(self, card_url: str, new_label_name: str) -> Dict[str, Any]:
        """Обновление метки карточки"""
        try:
            card = self.card_manager.get_card_by_url(card_url)
            if not card:
                # Попробуем получить карточку по ID, если передан не URL
                if len(card_url) >= 8 and card_url.isalnum():
                    card = self.card_manager.get_card_by_id(card_url)
                
                if not card:
                    return {
                        'success': False,
                        'error': 'Карточка не найдена'
                    }
            
            board = self.get_board()
            label_manager = TrelloLabelManager(board)
            
            # Список меток статуса для удаления
            status_labels = [
                Config.TRELLO_LABEL_WAITING,
                Config.TRELLO_LABEL_HAPPENING,
                Config.TRELLO_LABEL_DONE
            ]
            
            # Обновляем метки
            success = label_manager.update_card_labels(card, new_label_name, status_labels)
            if not success:
                return {
                    'success': False,
                    'error': f'Не удалось обновить метку "{new_label_name}"'
                }
            
            # Обновляем описание
            self._update_card_description(card, new_label_name)
            
            return {
                'success': True,
                'message': f'Статус изменен на "{new_label_name}"',
                'card_url': card.url if hasattr(card, 'url') else card_url,
                'card_id': card.id
            }
            
        except Exception as e:
            logger.error(f"Ошибка обновления метки: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _update_card_description(self, card, new_label_name: str):
        """Обновление описания карточки"""
        try:
            current_desc = card.desc if hasattr(card, 'desc') and card.desc else ""
            
            lines = current_desc.split('\n')
            updated_lines = []
            status_updated = False
            
            for line in lines:
                if line.startswith('Статус:'):
                    updated_lines.append(f"Статус: {new_label_name}")
                    status_updated = True
                else:
                    updated_lines.append(line)
            
            if not status_updated:
                updated_lines.append(f"Статус: {new_label_name}")
            
            new_desc = '\n'.join(updated_lines)
            card.set_desc(new_desc)
            logger.info(f"Обновлено описание карточки {card.id}")
            
        except Exception as e:
            logger.warning(f"Не удалось обновить описание: {e}")
    
    def get_card_info(self, card_url: str) -> Dict[str, Any]:
        """Получение информации о карточке"""
        card = self.card_manager.get_card_by_url(card_url)
        if not card:
            return {'success': False, 'error': 'Карточка не найдена'}
        
        try:
            due_date = None
            if hasattr(card, 'due_date') and card.due_date:
                try:
                    due_str = str(card.due_date)
                    if 'Z' in due_str:
                        utc_dt = datetime.fromisoformat(due_str.replace('Z', '+00:00'))
                    elif '+' in due_str:
                        utc_dt = datetime.fromisoformat(due_str)
                    else:
                        due_date = due_str
                        utc_dt = None
                    
                    if utc_dt:
                        moscow_dt = utc_dt.astimezone(self.time_manager.MOSCOW_TZ)
                        due_date = moscow_dt.strftime('%d.%m.%Y %H:%M MSK')
                except Exception as dt_error:
                    logger.warning(f"Ошибка парсинга даты {card.due_date}: {dt_error}")
                    due_date = str(card.due_date)
            
            return {
                'success': True,
                'card': {
                    'name': card.name,
                    'description': card.desc if hasattr(card, 'desc') else '',
                    'url': card.url,
                    'short_url': card.short_url if hasattr(card, 'short_url') else card.url,
                    'labels': [label.name for label in card.labels] if hasattr(card, 'labels') else [],
                    'due_date': due_date,
                    'card_id': card.id,
                    'list_id': card.list_id if hasattr(card, 'list_id') else None
                }
            }
        except Exception as e:
            logger.error(f"Ошибка получения информации о карточке: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_all_labels(self) -> Dict[str, Any]:
        """Получение всех меток доски"""
        try:
            board = self.get_board()
            label_manager = TrelloLabelManager(board)
            labels = label_manager.get_all_labels()
            
            return {
                'success': True,
                'labels': [label.name for label in labels],
                'count': len(labels)
            }
        except Exception as e:
            logger.error(f"Ошибка получения меток: {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_card(self, card_id: str) -> Dict[str, Any]:
        """Удаление карточки в Trello"""
        try:
            logger.info(f"Попытка удаления карточки {card_id}")
            
            # Используем Trello API напрямую для удаления
            url = f"https://api.trello.com/1/cards/{card_id}"
            
            params = {
                'key': Config.TRELLO_API_KEY,
                'token': Config.TRELLO_TOKEN
            }
            
            response = requests.delete(url, params=params)
            
            if response.status_code == 200:
                logger.info(f"Карточка {card_id} успешно удалена в Trello")
                return {
                    'success': True,
                    'message': 'Карточка удалена',
                    'card_id': card_id
                }
            else:
                logger.error(f"Ошибка при удалении карточки {card_id}: {response.status_code} - {response.text}")
                return {
                    'success': False,
                    'error': f'Ошибка Trello API: {response.status_code} - {response.text}',
                    'status_code': response.status_code
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Сетевая ошибка при удалении карточки {card_id}: {e}")
            return {
                'success': False,
                'error': f'Сетевая ошибка: {str(e)}'
            }
        except Exception as e:
            logger.error(f"Исключение при удалении карточки {card_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_card_id_from_url(self, card_url: str) -> Optional[str]:
        """Извлечение ID карточки из URL (для совместимости)"""
        return self.card_manager.extract_card_id(card_url)