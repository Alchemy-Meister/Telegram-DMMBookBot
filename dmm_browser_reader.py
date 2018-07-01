from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait

import math
import logging
import time

blank_url = 'about:blank'

class DMMBrowserReader():
    logger = logging.getLogger(__name__)

    def __init__(self, driver, book):
        self.driver = driver
        self.book = book
        self.__open_book_reader(book)
        self.menu = self.driver.find_element_by_id('menu')
        self.settings_menu_button = self.driver \
            .find_element_by_id('showSettingPanelMenuField')
        self.settings_panel = self.driver.find_elements_by_xpath( \
            '//div[contains(@class, "dialogSettingPanel")]')[0]
        self.page_counter = self.driver.find_element_by_id('pageSliderCounter')
        self.__enable_settings_menu(True)
        self.__show_pages_individually()
        self.__disable_page_animation()
        self.__enable_settings_menu(False)

    def __open_book_reader(self, book):
        DMMBrowserReader.logger.info('Opening DMM browser reader for ' \
            + '%s volume.' % book.title)
        self.driver.get(book.url)
        WebDriverWait(self.driver, 30).until( \
            lambda x: self.driver.find_element_by_id('loaderStatusDialog') \
            .value_of_css_property('display') == 'none' \
            and self.driver.find_element_by_id('contentProgress') \
            .value_of_css_property('display') == 'none')
        DMMBrowserReader.logger.info('DMM browser reader now ready.')
        css_rules = open('./constants/css_rules.js','r').read()
        self.driver.execute_script(css_rules)
        DMMBrowserReader.logger.info('Disabled DMM browser reader\'s css ' \
            + 'transition effects.')

    def __click_element(self, element):
        action = ActionChains(self.driver)
        action.move_to_element(element)
        action.click()
        action.perform()
        time.sleep(0.5)

    def __click_middle_reader(self):
        body = self.driver.find_element_by_css_selector('body')
        window_size = self.driver.get_window_size()
        action = ActionChains(self.driver)
        action.move_to_element_with_offset(
            body, window_size['width'] / 2, window_size['height'] / 2
        )
        action.click()
        action.perform()
        time.sleep(0.5)

    def __is_reader_menu_enabled(self):
        for css_class in self.menu.get_attribute('class').split():
            if css_class == 'show':
                return True
        return False

    def __is_settings_menu_enabled(self):
        if self.settings_panel.value_of_css_property('display') == 'none':
            return False
        return True

    def __enable_reader_menu(self, enable):
        if self.__is_reader_menu_enabled() != enable:
            self.__click_middle_reader()

    def __enable_settings_menu(self, enable):
        if self.__is_settings_menu_enabled() != enable:
            self.__enable_reader_menu(True)
            self.__click_element(self.settings_menu_button)

    def __show_pages_individually(self):
        single_page_input = self.driver.find_element_by_id('spread_false')
        self.__click_element(single_page_input)

    def __disable_page_animation(self):
        page_off_input = self.driver.find_element_by_id('animationPattern_off')
        self.__click_element(page_off_input)

    def __previous_page(self):
        action = ActionChains(self.driver)
        action.key_down(Keys.RIGHT).key_up(Keys.RIGHT)
        action.perform()

    def __next_page(self):
        action = ActionChains(self.driver)
        action.key_down(Keys.LEFT).key_up(Keys.LEFT)
        action.perform()

    def __move_to_page(self, page):
        current_page = int(self.page_counter.text.split('/')[0])
        if current_page != page:
            move_num_pages = page - current_page
            if move_num_pages == -1:
                self.__previous_page()
            elif move_num_pages == 1:
                self.__next_page()
            else:
                self.__enable_reader_menu(True)
                slide_bar = self.driver.find_element_by_id('pageSliderBar')
                slider = self.driver.find_elements_by_xpath(
                    '//div[@id="pageSliderBarPositioning"]' \
                    + '//div[contains(@class, "ui-slider-handle")]'
                )[0]
                slide_bar_width = slide_bar.size['width']
                slider_step = slide_bar_width / self.book.pages
                
                print("slide_bar width: %s" % slide_bar_width)
                print("slider step: %s" % slider_step)
                print("current_page %s" % int(current_page))
                print("num pages to move: %s" % move_num_pages)

                action = ActionChains(self.driver)
                action.drag_and_drop_by_offset(slider, \
                    math.ceil(-1 * move_num_pages * slider_step), 0)
                action.perform()

    def __is_reader_page_ready(self):
        loadings = self.driver.find_elements_by_xpath( \
            '//div[@class="currentScreen"]//div[@class="loading"]')
        
        page_ready = True
        for loading in loadings:
            if loading.value_of_css_property('visibility') == 'visible':
                page_ready = False
                break
        return page_ready

    def __save_screenshot(self, path):
        WebDriverWait(self.driver, 30).until( \
            lambda x: self.__is_reader_page_ready())
        self.__enable_reader_menu(False)
        self.driver.save_screenshot(path)
        time.sleep(0.5)

    def download_page(self, page_num, path):
        self.__move_to_page(page_num)
        self.__save_screenshot(path)

    def close(self):
        self.driver.delete_all_cookies()
        self.driver.get(blank_url)
