from telegram.ext import (ConversationHandler, CommandHandler, RegexHandler)
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup)

from datetime import timedelta

from cron_job_manager import CronJobManager
from db_utils import Database
import dmm_ripper as dmm
import utilities as utils
import json
import pytz

class ListBookHandler(CommandHandler):

    time_zone = pytz.timezone('Asia/Tokyo')

    def __init__(self, lang, language_codes):
        self.db_manager = Database.get_instance()
        self.lang = lang
        self.language_codes = language_codes
        self.scheduler = CronJobManager.get_instance()

        CommandHandler.__init__(self, 'my_library', self.my_library)

    def my_library(self, bot, update):
        user_id = update.message.from_user.id
        session = self.db_manager.create_session()
        user = self.db_manager.get_user(session, user_id)
        language_code = user.language_code

        if user.cache_built:
            if user.language_code == 'ja':
                date = user.cache_expire_date.replace(tzinfo=self.time_zone)
                date = (date - timedelta(days=1)).strftime('%Y/%m/%d')
            else:
                date = user.cache_expire_date.replace(tzinfo=None)
                date = (date - timedelta(days=1)).strftime('%Y/%d/%m')
            num_titles = len(
                    self.db_manager.get_user_library(session, user_id)
                )
            num_books = len(user.book_collection)
            if user.login_error:
                message = '{}\n\n{}'.format(
                    self.lang[language_code]['update_library_error'],
                    self.lang[language_code]['library_request'] \
                        .format(date, num_titles, num_books)
                )
            else:
                message = self.lang[language_code]['library_request'] \
                    .format(date, num_titles, num_books)

            button_library = [InlineKeyboardButton(
                self.lang[language_code]['search_library'],
                switch_inline_query_current_chat=''
            )]

            reply_markup = InlineKeyboardMarkup(
                utils.build_menu(button_library)
            )
            update.message.reply_text(message, reply_markup=reply_markup)
        elif user.now_caching:
            self.send_message(update, language_code, ['building_cache'])
        else:
            if user.login_error: 
                message = 'build_library_error'
            else:
                message = 'request_update_library'
            self.send_message(
                    update, language_code, [message]
                )
        self.db_manager.remove_session()
        return ConversationHandler.END

    def send_message(self, update, language_code, message_codes, 
        reply_markup=None):
        
        text = self.lang[language_code][message_codes.pop(0)]
        for message_code in message_codes:
            text += '\n\n' + self.lang[language_code][message_code]
        update.message.reply_text(text, reply_markup=reply_markup)

    def inline_query_callback(bot, update):
        query = update.callback_query
        user_id = update.callback_query.from_user.id

        logger.info("query: %s", query.data)

        callback = json.loads(query.data)

        if callback['command'] == 'language_menu':
            language_menu(bot, query)
        elif callback['command'] == 'set_language':
            change_language_callback(bot, query, user_id, callback['value'])
