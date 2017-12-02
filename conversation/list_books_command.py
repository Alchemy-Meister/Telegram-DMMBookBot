from telegram.ext import (ConversationHandler, CommandHandler, RegexHandler)
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup)

from datetime import timedelta

from cron_job_manager import CronJobManager
from db_utils import Database
import dmm_ripper as dmm
import utilities as utils
import json
import pytz

class ListBookHandler(ConversationHandler):

    num_stages = 1
    time_zone = pytz.timezone('Asia/Tokyo')

    def __init__(self, lang, language_codes, initial_stage):
        self.db_manager = Database.get_instance()
        self.lang = lang
        self.language_codes = language_codes
        self.initial_stage = initial_stage

        self.scheduler = CronJobManager.get_instance()

        self.PROCESS_PASSWORD = range(
            initial_stage, initial_stage + ListBookHandler.num_stages
        )

        self.entry_points = [CommandHandler(
            'my_library', self.my_library)]

        self.states = {
            self.PROCESS_PASSWORD: [RegexHandler('.*',
                self.request_session
            )]
        }

        self.fallbacks=[RegexHandler('finish|Finish', self.cancel)]

        ConversationHandler.__init__(
            self,
            self.entry_points,
            self.states,
            self.fallbacks
        )

    def get_final_stage_num(self):
        return self.initial_stage + ListBookHandler.num_states

    def my_library(self, bot, update):
        user_id = update.message.from_user.id
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if user.cache_built:
            if user.login_error:
                if user.language_code == 'ja':
                    date = user.cache_expire_date.replace(tzinfo=self.time_zone)
                    date = (date - timedelta(days=1)).strftime('%Y/%m/%d')
                else:
                    date = user.cache_expire_date.replace(tzinfo=None)
                    date = (date - timedelta(days=1)).strftime('%Y/%d/%m')

                message = '{}\n\n{}'.format(
                    self.lang[language_code]['update_library_error'],
                    self.lang[language_code]['last_library_request'] \
                        .format(date)
                )
            else:
                message = self.lang[language_code]['library_request']
            
            button_library = [InlineKeyboardButton(x.title, \
                callback_data=x.url) \
                for x in self.db_manager.get_user_library(user_id)]

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

        return ConversationHandler.END

    def request_session(self, bot, update):
        pass

    def cancel(self, bot, update):
        pass

    def send_message(self, update, language_code, message_codes, 
        reply_markup=None):
        
        text = self.lang[language_code][message_codes.pop(0)]
        for message_code in message_codes:
            text += '\n\n' + self.lang[language_code][message_code]
        update.message.reply_text(text, reply_markup=reply_markup)

    def inline_keyboard_request(self, update, language_code, message_code,
        button_list):

        reply_markup = InlineKeyboardMarkup(button_list)
        update.message.reply_text(self.lang[language_code][message_code],
            reply_markup=reply_markup)

    def inline_query_callback(bot, update):
        query = update.callback_query
        user_id = update.callback_query.from_user.id

        logger.info("query: %s", query.data)

        callback = json.loads(query.data)

        if callback['command'] == 'language_menu':
            language_menu(bot, query)
        elif callback['command'] == 'set_language':
            change_language_callback(bot, query, user_id, callback['value'])
