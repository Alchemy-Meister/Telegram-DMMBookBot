#!/usr/bin/env python
# -*- coding: utf-8 -*-
#

from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove,
    InlineKeyboardButton, InlineKeyboardMarkup)
from telegram.ext import (Updater, CommandHandler, MessageHandler, 
    CallbackQueryHandler)
from conversation import StartWizard, ConfigWizard, ListBookHandler
from cron_job_manager import CronJobManager
from db_utils import Database
from languages import common, english, japanese
from datetime import datetime
from pytz import timezone, utc
import config
import logging
import json
import utilities as utils

def logging_tz(*args):
    utc_dt = utc.localize(datetime.utcnow())
    my_tz = timezone('Asia/Tokyo')
    converted = utc_dt.astimezone(my_tz)
    return converted.timetuple()

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO)
logging.Formatter.converter = logging_tz
logger = logging.getLogger(__name__)

db_manager = Database.get_instance()
app_config = config.Config
scheduler = CronJobManager.get_instance()
scheduler.set_download_path(app_config.DOWNLOAD_PATH)

lang = {'en': english.en, 'ja': japanese.ja, 'common': common.common}
language_codes = {'en': ['english', '英語'], 'ja': ['japanese','日本語']}

def error(bot, update, error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, error)

def main():
    updater = Updater(app_config.TOKEN)
    dispatcher = updater.dispatcher

    intro_wizard_handler = StartWizard(lang, language_codes, 0)
    config_handler = ConfigWizard(
        lang,
        language_codes,
        intro_wizard_handler.get_final_stage_num()
    )
    list_books_handler = ListBookHandler(
        lang,
        language_codes,
        config_handler.get_final_stage_num()
    )

    dispatcher.add_handler(intro_wizard_handler)
    dispatcher.add_handler(config_handler)
    dispatcher.add_handler(list_books_handler)
    dispatcher.add_error_handler(error)

    updater.start_polling(timeout=40)
    updater.idle()

if __name__ == '__main__':
    main()