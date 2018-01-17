class Config():
    TOKEN = TELEGRAM_BOT_TOKEN
    SECRET_KEY = DB_PASS_ENCRYPTION_KEY
    DATABASE = 'dmm.db'
    DOWNLOAD_PATH = 'books/images'
    LANGUAGE = {'ja': '日本語', 'en': 'English'}
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024 #bytes
