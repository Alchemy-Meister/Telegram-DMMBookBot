#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Updater, CommandHandler, MessageHandler)
from conversation import (StartWizard, ConfigWizard, ListBookHandler, 
    BookSearchHandler, BookDownloadHandler)
from data.config import Config
from cron_job_manager import CronJobManager
from db_utils import Database
from languages import common, english, japanese

import logging
import signal
import sys
import utilities as utils

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logging.Formatter.converter = utils.logging_tz
logger = logging.getLogger(__name__)

lang = {'en': english.en, 'ja': japanese.ja, 'common': common.common}
language_codes = {'en': ['english', '英語'], 'ja': ['japanese','日本語']}

db_manager = Database.get_instance()
scheduler = CronJobManager.get_instance(
    languages=lang, max_upload_size=Config.MAX_UPLOAD_SIZE, \
    webdriver_config=Config.WEBDRIVER
)
scheduler.set_download_path(Config.DOWNLOAD_PATH)

def error_callback(bot, update, error):
    logger.exception(error)

def shutdown():
    scheduler.close_dmm_ripper()

def main():
    updater = Updater(Config.TOKEN, \
        request_kwargs={'read_timeout': 10, 'connect_timeout': 10})
    dispatcher = updater.dispatcher

    intro_wizard_handler = StartWizard(lang, language_codes, 0)
    config_handler = ConfigWizard(
        lang,
        language_codes,
        intro_wizard_handler.get_final_state_num()
    )
    list_books_handler = ListBookHandler(lang, language_codes)
    search_book_handler = BookSearchHandler(lang)
    book_download_handler = BookDownloadHandler(
        Config.MAX_UPLOAD_SIZE,
        Config.DOWNLOAD_PATH,
        lang,
        config_handler.get_final_state_num()
    )

    dispatcher.add_handler(intro_wizard_handler)
    dispatcher.add_handler(config_handler)
    dispatcher.add_handler(list_books_handler)
    dispatcher.add_handler(search_book_handler)
    dispatcher.add_handler(book_download_handler)
    dispatcher.add_error_handler(error_callback)

    updater.start_polling()
    updater.idle()

    shutdown()
    sys.exit(0)

if __name__ == '__main__':
    main()