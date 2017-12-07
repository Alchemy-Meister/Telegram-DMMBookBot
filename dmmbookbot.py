#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Updater, CommandHandler, MessageHandler)
from conversation import (StartWizard, ConfigWizard, ListBookHandler, 
    BookSearchHandler)
from cron_job_manager import CronJobManager
from db_utils import Database
from languages import common, english, japanese
from config import Config
import logging
import json
import utilities as utils

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logging.Formatter.converter = utils.logging_tz
logger = logging.getLogger(__name__)

def inline_result(bot, update):
    print(update)

def main():
    lang = {'en': english.en, 'ja': japanese.ja, 'common': common.common}
    language_codes = {'en': ['english', '英語'], 'ja': ['japanese','日本語']}

    db_manager = Database.get_instance()
    scheduler = CronJobManager.get_instance()
    scheduler.set_download_path(Config.DOWNLOAD_PATH)

    updater = Updater(Config.TOKEN)
    dispatcher = updater.dispatcher

    intro_wizard_handler = StartWizard(lang, language_codes, 0)
    config_handler = ConfigWizard(
        lang,
        language_codes,
        intro_wizard_handler.get_final_stage_num()
    )
    list_books_handler = ListBookHandler(lang, language_codes)
    search_book_handler = BookSearchHandler(lang)

    dispatcher.add_handler(intro_wizard_handler)
    dispatcher.add_handler(config_handler)
    dispatcher.add_handler(list_books_handler)
    dispatcher.add_handler(search_book_handler)

    updater.start_polling(timeout=60)
    updater.idle()

if __name__ == '__main__':
    main()