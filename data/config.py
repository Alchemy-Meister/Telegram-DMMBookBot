class Config():
    TOKEN = 'TELEGRAM_BOT_TOKEN'
    SECRET_KEY = 'DB_PASS_ENCRYPTION_KEY'
    WEBDRIVER = {
        'GECKO_PATH': 'SELENIUM_GECKO_DRIVER_PATH',
        'DEBUG_DRIVER': False,
        'FIREFOX_HEADER_SIZE': 74,
        'DRIVER_WINDOW_SIZE': [900, 1280]
    }
    DATABASE = 'dmm.db'
    DOWNLOAD_PATH = 'books/images'
    LANGUAGE = {'ja': '日本語', 'en': 'English'}
    MAX_UPLOAD_SIZE = 50 * 1024 * 1024 #bytes
