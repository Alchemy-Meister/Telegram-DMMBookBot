from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from PIL import Image


import io
import logging
import math
import time

blank_url = 'about:blank'

class DMMBrowserReader():
    logger = logging.getLogger(__name__)

    def __init__(self, driver, book, webdriver_config):
        self.webdriver_config = webdriver_config
        self.driver = driver
        self.book = book
        self.current_page = None
        self.__open_book_reader(book)
        self.toc_menu_button = self.driver \
            .find_element_by_id('showTableOfContents')
        self.settings_menu_button = self.driver \
            .find_element_by_id('showSettingPanelMenuField')
        self.page_counter = self.driver.find_element_by_id('pageSliderCounter')
        self.__enable_settings_menu(True)
        self.__show_pages_individually()
        self.__disable_page_animation()
        self.__enable_settings_menu(False)
        WebDriverWait(self.driver, 10).until( \
            lambda _: not self.__is_settings_menu_enabled())
        DMMBrowserReader.logger.info('Settings of DMM browser reader have ' \
            + 'changed.')

    def __open_book_reader(self, book):
        DMMBrowserReader.logger.info('Opening DMM browser reader for ' \
            + 'volume %s.' % book.id)
        self.driver.get(book.url)
        WebDriverWait(self.driver, 30).until( \
            lambda _: self.driver.find_element_by_id('loaderStatusDialog') \
            .value_of_css_property('display') == 'none' \
            and self.driver.find_element_by_id('contentProgress') \
            .value_of_css_property('display') == 'none' \
            and self.__is_page_ready())
        DMMBrowserReader.logger.info('DMM browser reader now ready.')
        css_rules = open('./constants/css_rules.js', 'r').read()
        self.driver.execute_script(css_rules)
        DMMBrowserReader.logger.info('Disabled DMM browser reader\'s css ' \
            + 'transition effects.')
        if self.webdriver_config['DEBUG_DRIVER']:
            print_mouse = open('./constants/print_mouse.js', 'r').read()
            self.driver.execute_script(print_mouse)
            DMMBrowserReader.logger.info('Mouse tracking enabled for debug.')

    def __click_element(self, element):
        action = ActionChains(self.driver)
        action.move_to_element(element)
        action.click()
        action.perform()
        time.sleep(0.5)

    def __press_key(self, key):
        action = ActionChains(self.driver)
        action.key_down(key).key_up(key)
        action.perform()

    def __click_with_offset(self, element, x_offset, y_offset):
        action = ActionChains(self.driver)
        action.move_to_element(element)
        action.move_by_offset(x_offset, y_offset)
        action.click()
        action.perform()
        time.sleep(0.5)

    def __is_reader_menu_enabled(self):
        menu = self.driver.find_element_by_id('menu')
        for css_class in menu.get_attribute('class').split():
            if css_class == 'show':
                return True
        return False

    def __is_settings_menu_enabled(self):
        settings_panel = self.driver.find_elements_by_xpath(
            '//div[contains(@class, "dialogSettingPanel")]'
        )[0]
        if settings_panel.value_of_css_property('display') == 'none':
            return False
        return True

    def __is_table_of_contents_menu_enabled(self):
        toc_panel = self.driver.find_elements_by_xpath(
            '//div[contains(@class, "dialogTableOfContents")]'
        )[0]
        if toc_panel.value_of_css_property('display') == 'none':
            return False
        return True

    def __enable_reader_menu(self, enable, attempts=5):
        if attempts == 0:
            raise TimeoutException('Attempts to {} menu exceeded.'
                .format('open' if enable else 'close')
            )
        if self.__is_reader_menu_enabled() != enable:
            canvas = self.driver.find_elements_by_xpath(
                '//div[@class="currentScreen"]'
            )[0]
            self.__click_element(canvas)
            try:
                WebDriverWait(self.driver, 10).until(
                    lambda _: self.__is_reader_menu_enabled() == enable
                )
            except TimeoutException:
                DMMBrowserReader.logger.info(
                    'Failed to {} menu, trying again.'
                        .format('open' if enable else 'close')
                )
                WebDriverWait(self.driver, 30).until(
                    lambda _: self.__is_page_ready())
                self.__enable_reader_menu(enable, attempts=attempts - 1)

    def __enable_settings_menu(self, enable, attempts=5):
        if attempts == 0:
            raise TimeoutException(
                'Attempts to {} settings menu exceeded.'
                    .format('open' if enable else 'close')
            )
        if self.__is_settings_menu_enabled() != enable:
            try:
                self.__enable_reader_menu(True, attempts=1)
                self.__click_element(self.settings_menu_button)
                WebDriverWait(self.driver, 10).until(
                    lambda _: self.__is_settings_menu_enabled() == enable
                )
            except TimeoutException:
                DMMBrowserReader.logger.info(
                    'Failed to {} settings menu, trying again.'
                    .format('open' if enable else 'close')
                )
                self.__enable_settings_menu(enable, attempts=attempts - 1)

    def __enable_table_of_contents_menu(self, enable, attempts=5):
        if attempts == 0:
            raise TimeoutException(
                'Attempts to {} toc menu exceeded.'
                    .format('open' if enable else 'close')
            )
        if self.__is_table_of_contents_menu_enabled() != enable:
            try:
                self.__enable_reader_menu(enable, attempts=1)
                self.__click_element(self.toc_menu_button)
                WebDriverWait(self.driver, 10).until(
                    lambda _:
                        self.__is_table_of_contents_menu_enabled() == enable
                )
            except TimeoutException:
                DMMBrowserReader.logger.info(
                    'Failed to {} toc menu, trying again.'
                        .format('open' if enable else 'close')
                )
                self.__enable_table_of_contents_menu(
                    enable,
                    attempts=attempts - 1
                )

    def __show_pages_individually(self):
        single_page_input = self.driver.find_element_by_id('spread_false')
        self.__click_element(single_page_input)

    def __disable_page_animation(self):
        page_off_input = self.driver.find_element_by_id('animationPattern_off')
        self.__click_element(page_off_input)

    def __previous_page(self):
        DMMBrowserReader.logger.info('Moving on to previos page.')
        self.__press_key(Keys.RIGHT)
        # window_size = self.driver.get_window_size()
        # self.__click_with_offset(
        #     self.body, window_size['width'], window_size['height'] / 2
        # )
        time.sleep(0.25)

    def __next_page(self):
        DMMBrowserReader.logger.info('Moving on to next page.')
        self.__press_key(Keys.LEFT)
        # window_size = self.driver.get_window_size()
        # self.__click_with_offset(
        #     self.body, 0, window_size['height'] / 2
        # )
        time.sleep(0.25)

    def __move_to_page(self, page):
        if self.__is_dialog_activated():
            raise Exception('Dialog is activated, most likely ' \
                + ' session has been dismissed.')
        else:
            self.current_page = int(self.page_counter.text.split('/')[0])
            DMMBrowserReader.logger.info('Current page: %s' % self.current_page)
            if self.current_page != page:
                move_num_pages = page - self.current_page
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
                    slider_with = slider.size['width']
                    slide_bar_width = slide_bar.size['width']
                    slider_step = slide_bar_width / self.book.pages
                    
                    print("slide_bar width: %s" % slide_bar_width)
                    print("slider step: %s" % slider_step)
                    print("current_page %s" % self.current_page)
                    print("num pages to move: %s" % move_num_pages)

                    action = ActionChains(self.driver)
                    action.click_and_hold(slider)
                    action.move_by_offset(
                        math.ceil(-1 * move_num_pages * slider_step), 0
                    )
                    action.release()
                    action.perform()
                    time.sleep(1)

    def __is_dialog_activated(self):
        dialog = self.driver.find_elements_by_xpath(
            '//div[contains(@class, "messageDialog")]'
        )[0]
        if dialog.value_of_css_property('display') == 'block':
            return True
        return False

    def __is_page_ready(self):
        loadings = self.driver.find_elements_by_xpath( \
            '//div[@class="loading"]')
        for loading in loadings:
            if loading.value_of_css_property('visibility') == 'visible':
                return False
        canvas = self.driver.find_elements_by_xpath(
            '//div[@class="currentScreen"]'
        )[0]
        if canvas.value_of_css_property('visibility') == 'hidden':
            return False
        return True

    def __save_page(self, path):
        WebDriverWait(self.driver, 30).until( \
            lambda _: self.__is_page_ready())
        self.__enable_reader_menu(False)
        png_path = path + '.png'
        DMMBrowserReader.logger.info('Saving screenshot of page: %s' \
            % self.current_page)
        png_img = Image.open(io.BytesIO(self.driver.get_screenshot_as_png()))
        jpg_img = png_img.convert('RGB')
        jpg_img.save(path + '.jpg', 'JPEG', \
             optimize=True, progressive=True, quality=85)

    def download_page(self, page_num, path, attempt=3):
        self.__move_to_page(page_num)
        while self.current_page != page_num and attempt > 0:
            DMMBrowserReader.logger.info('Failed moving to page ' \
                + '%s, trying again.' % page_num)
            self.__move_to_page(page_num)
            attempt = attempt - 1
        if attempt == 0:
            raise Exception('Page movements attempts exceeded.')
        self.__save_page(path)

    def download_table_of_contents(self, path):
        DMMBrowserReader.logger.info(
            'Scanning table of contents for volume %s.' % self.book.id
        )
        self.__enable_table_of_contents_menu(True)
        WebDriverWait(self.driver, 30).until(
            lambda _:
                len(
                    self.driver.find_elements_by_xpath(
                        '//div[@id="tableOfContents"]//div'
                    )
                ) != 0
        )
        num_toc_items = len(self.driver.find_elements_by_xpath( \
            '//div[@id="tableOfContents"]//div'))
        toc_file = open(path, 'w')
        if num_toc_items > 0:
            for index in range(num_toc_items):
                self.__enable_table_of_contents_menu(True)
                toc_items = self.driver.find_elements_by_xpath( \
                    '//div[@id="tableOfContents"]//div')
                if toc_items:
                    toc_item = toc_items[index]
                    toc_item_text = toc_item.text
                    self.__click_element(toc_item)
                    WebDriverWait(self.driver, 30).until( \
                        lambda _: 
                            (not self.__is_table_of_contents_menu_enabled())
                            and self.__is_page_ready()
                    )
                    self.current_page = int(
                        self.page_counter.text.split('/')[0]
                    )
                    toc_file.write('{}\t{}\n'.format(
                        toc_item_text, self.current_page)
                    )
                    DMMBrowserReader.logger.info(
                        'Found {} - {} ToC entry.'
                            .format(toc_item_text, self.current_page))
                    if toc_item_text == '目次':
                        DMMBrowserReader.logger.info(
                            'Now on ToC page, avoiding ToC links.')
                        self.__move_to_page(self.current_page + 1)
                        WebDriverWait(self.driver, 30).until( \
                            lambda _: self.__is_page_ready()
                        )
        DMMBrowserReader.logger.info('Table of contents for volume ' \
            + '%s saved.' % self.book.id)
        toc_file.close()

    def close(self):
        self.driver.delete_all_cookies()
        self.driver.get(blank_url)
