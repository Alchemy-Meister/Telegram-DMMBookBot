from telegram.ext import (ConversationHandler, CommandHandler, RegexHandler)
from telegram import (ReplyKeyboardMarkup, ReplyKeyboardRemove)

import utilities as utils
from cron_job_manager import CronJobManager
from db_utils import Database
import dmm_ripper as dmm

class StartWizard(ConversationHandler):

    num_states = 4

    def __init__(self, lang, language_codes, initial_stage):
        self.db_manager = Database.get_instance()
        self.scheduler = CronJobManager.get_instance()
        self.lang = lang
        self.language_codes = language_codes
        self.initial_stage = initial_stage

        self.LANGUAGE, self.EMAIL, self.PASSWORD, self.STORE_PASS = range(
            initial_stage, initial_stage + StartWizard.num_states
        )

        self.entry_points = [CommandHandler('start', self.start)]
        self.states = {
            self.LANGUAGE: [RegexHandler('.*', self.language)],
            self.EMAIL: [RegexHandler('.*', self.email)],
            self.STORE_PASS: [RegexHandler('.*', self.save_credentials)],
            self.PASSWORD: [RegexHandler('.*', self.password)],
        }
        self.fallbacks = [
            CommandHandler('10aec35353f9c4096a71c38654c3d402', self.cancel)
        ]

        ConversationHandler.__init__(self,
            entry_points=self.entry_points,
            states=self.states,
            fallbacks=self.fallbacks
        )
    
    def get_final_stage_num(self):
        return self.initial_stage + StartWizard.num_states

    def start(self, bot, update):
        user_id = update.message.from_user.id
        user = self.db_manager.get_user(user_id)

        if user == None:
            user = self.db_manager.insert_user(user_id)

        if user.language_code == None:
            self.keyboard_request(
                update,
                '{} {}\n\n{} {}'.format(
                    self.lang['en']['welcome_text'],
                    self.lang['en']['select_language'],
                    self.lang['ja']['welcome_text'],
                    self.lang['ja']['select_language']),
                [['English'], ['日本語']])

            return self.LANGUAGE

        else:
            language_code = user.language_code
            update.message.reply_text('{}'.format(
                self.lang[user.language_code]['welcome_text'])
            )

            if user.email == None:
                self.request_email(update, user)
                return self.EMAIL
            elif user.save_credentials == None \
                or (user.save_credentials == True and user.password == None):
                
                self.keyboard_request(
                    update, 
                    self.lang[language_code]['save_pass_confirm'], 
                    [
                        [self.lang[language_code]['yes']],
                        [self.lang[language_code]['no']]
                    ]
                )
                return self.STORE_PASS
            else:
                return ConversationHandler.END

    def language(self, bot, update):
        user_id = update.message.from_user.id
        reply_language = update.message.text

        language_code = utils.get_key_with_value(
            self.language_codes, reply_language.lower()
        )

        if language_code == None:
            self.keyboard_request(update,
                '{}\n\n{}'.format(
                    self.lang['en']['invalid_language'],
                    self.lang['ja']['invalid_language']),
                [['English'], ['日本語']]
            )

            return self.LANGUAGE

        else:
            self.db_manager.set_user_language(user_id, language_code)
            user = self.db_manager.get_user(user_id)
            self.request_email(
                update,
                user,
                concat_message='long_selected_language'
            )

            return self.EMAIL

    def request_email(self, update, user, concat_message=None):
        language_code = user.language_code
        messages = ['account_explanation', 'request_email']
        
        if concat_message != None:
            messages = [concat_message] + messages
        
        self.send_message(
            update, language_code, messages, reply_markup=ReplyKeyboardRemove()
        )

    def email(self, bot, update):
        user_id = update.message.from_user.id
        reply_email = update.message.text
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if utils.is_valid_email(reply_email):
            self.db_manager.set_user_email(user_id, reply_email)
            self.keyboard_request(
                update, 
                self.lang[language_code]['save_pass_confirm'], 
                [
                    [self.lang[language_code]['yes']],
                    [self.lang[language_code]['no']]
                ]
            )

            return self.STORE_PASS

        else:
            self.send_message(update, language_code, ['invalid_email'])

            return self.EMAIL

    def save_credentials(self, bot, update):
        user_id = update.message.from_user.id
        reply_confirm = update.message.text
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        if reply_confirm == self.lang[language_code]['yes']:
            self.db_manager.set_save_credentials(user_id, True)
            self.send_message(
                update,
                language_code,
                ['request_password'],
                reply_markup=ReplyKeyboardRemove()
            )
            return self.PASSWORD

        else:
            self.db_manager.set_save_credentials(user_id, False)
            self.send_message(
                update,
                language_code, 
                ['ready'], 
                reply_markup=ReplyKeyboardRemove()
            )

            return ConversationHandler.END
    

    def password(self, bot, update):
        user_id = update.message.from_user.id
        reply_password = update.message.text
        self.db_manager.set_user_password(user_id, reply_password)
        
        user = self.db_manager.get_user(user_id)
        language_code = user.language_code

        self.send_message(
            update,
            language_code,
            ['checking_credentials'],
            reply_markup=ReplyKeyboardRemove()
        )

        try:
            session = dmm.get_session(user.email, reply_password, True)
            self.scheduler.add_user_cache_scheduler(user, session)
            update.message.reply_text(self.lang[language_code]['ready'])
        except Exception as e:
            print(e)
            self.send_message(update,
                language_code,
                ['long_invalid_credentials']
            )
        return ConversationHandler.END

    def cancel(bot, update):
        pass

    def send_message(self, update, language_code, message_codes,
        reply_markup=None):

        text = self.lang[language_code][message_codes.pop(0)]
        for message_code in message_codes:
            text += '\n\n' + self.lang[language_code][message_code]
        update.message.reply_text(text, reply_markup=reply_markup)

    def keyboard_request(self, update, message, button_list):
        reply_markup = ReplyKeyboardMarkup(button_list, one_time_keyboard=True,
            resize_keyboard=True)
        update.message.reply_text(message, reply_markup=reply_markup)