from telegram.ext import (ConversationHandler, CommandHandler, RegexHandler)
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup)

from cron_job_manager import CronJobManager
from db_utils import Database
import dmm_ripper as dmm
import utilities as utils
import json

class ListBookHandler(ConversationHandler):

    num_stages = 1

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
            button_library = [InlineKeyboardButton(x.title, \
                callback_data=x.url) \
                for x in self.db_manager.get_user_library(user_id)]

            self.inline_keyboard_request(update, language_code, \
                'library_request', utils.build_menu(button_library))
        elif user.now_caching:
            self.send_message(update, language_code, ['building_cache'])
        else:
            self.send_message(update, language_code, ['request_update_library'])

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
