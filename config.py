import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')
    STAFF_CHAT_ID = os.getenv('STAFF_CHAT_ID')
    TOPIC_STAFF_ID=os.getenv('TOPIC_STAFF_ID')
    CHANNEL_CHAT_ID = os.getenv('CHANNEL_CHAT_ID')
    TRELLO_API_KEY = os.getenv('TRELLO_API_KEY')
    TRELLO_API_SECRET = os.getenv('TRELLO_API_SECRET')
    TRELLO_TOKEN = os.getenv('TRELLO_TOKEN')
    TRELLO_BOARD_ID = os.getenv('TRELLO_BOARD_ID')
    TRELLO_LIST_NAME = os.getenv('TRELLO_LIST_NAME', 'Смены')
    TRELLO_LABEL_WAITING = os.getenv('TRELLO_LABEL_WAITING', 'ОЖИДАНИЕ')
    TRELLO_LABEL_HAPPENING = os.getenv('TRELLO_LABEL_HAPPENING', 'ПРОИСХОДИТ')
    TRELLO_LABEL_DONE = os.getenv('TRELLO_LABEL_DONE', 'ПРОВЕДЕН')
    IMAGE_URL_START = os.getenv('IMAGE_URL_START', '')  # Картинка для "начало смены"
    IMAGE_URL_SCHEDULED = os.getenv('IMAGE_URL_SCHEDULED', '')  # Картинка для "запланирована"
    APPROVAL_TIMEOUT = int(os.getenv('APPROVAL_TIMEOUT', 86400))