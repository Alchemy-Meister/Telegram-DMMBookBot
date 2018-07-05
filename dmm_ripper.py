#!/usr/bin/python
# -*-coding:utf-8 -*-

from bs4 import BeautifulSoup
from dmm_browser_reader import DMMBrowserReader
from selenium import webdriver
from selenium.webdriver.common.alert import Alert
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import logging
import os
import re
import requests
import sys
import utilities

blank_url = 'about:blank'
redirect_url = 'https://www.dmm.com/my/-/redirect/=/rurl='
book_url = 'https://book.dmm.com'
library_url = book_url + '/library/'
driver_timeout = 10

class DMMRipper():
    logger = logging.getLogger(__name__)
    __instance = None

    def __init__(self, webdriver_config):
        if DMMRipper.__instance != None:
            raise Exception('This class is a singleton!')
        else:
            self.webdriver_config = webdriver_config
            firefox_profile = FirefoxProfile()
            firefox_profile.set_preference(
                'browser.privatebrowsing.autostart', True
            )
            options = Options()
            options.set_headless(headless=webdriver_config['HEADLESS'])

            self.driver = webdriver.Firefox(firefox_options=options, \
                executable_path = webdriver_config['GECKO_PATH'])
            self.driver.set_window_size( \
                webdriver_config['DRIVER_WINDOW_SIZE'][0], \
                webdriver_config['DRIVER_WINDOW_SIZE'][1] \
                + webdriver_config['FIREFOX_HEADER_SIZE']
            )
            self.browser_reader = None
            DMMRipper.__instance = self

    @staticmethod
    def get_instance(webdriver_config=None):
        if DMMRipper.__instance == None:
            DMMRipper.logger.info('DMMRipper singleton instantiated')
            DMMRipper(webdriver_config)
        return DMMRipper.__instance

    def add_cookies(self, cookies):
        for cookie in cookies:
            try:
                self.driver.add_cookie(cookie)
            except Exception as e:
                print(e)

    def add_domain_based_cookies(self, domain, cookies):
        self.driver.get(domain)
        self.add_cookies(cookies)

    def remove_cookies(self, cookies):
        for cookie in cookies:
            try:
                self.driver.delete_cookie(cookie['name'])
            except Exception as i:
                pass

    def get_login_url(self, fast):
        login_url = 'https://www.dmm.com/my/-/login/' \
                + '=/path=DRVESRUMTh1aCl5THVILWk8GWVsf/channel=book'

        if fast:
            return login_url
        else:
            response = requests.get(book_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            try:
                return soup.find('a', attrs={'class': 'hd-btn--login'}) \
                    .get('href')
            except:
                return login_url

    def get_session_cookies(self, email, password, fast=False,
        remove_cookies=False):
        
        login_url = self.get_login_url(fast)
        self.driver.get(login_url)

        WebDriverWait(self.driver, driver_timeout).until( \
            EC.presence_of_element_located((By.ID, 'login_id')))
        inputElement = self.driver.find_element_by_id('login_id')
        inputElement.send_keys(email)
        inputElement = self.driver.find_element_by_id('password')
        inputElement.send_keys(password)

        login_button = self.driver.find_element_by_xpath( \
            '//*[@id="loginbutton_script_on"]/span/input' )
        login_button.submit()

        try:
            WebDriverWait(self.driver, driver_timeout).until( \
                lambda x: redirect_url in self.driver.current_url)
            cookies = self.driver.get_cookies()
            if remove_cookies:
                self.driver.delete_all_cookies()
            self.driver.get(blank_url)

            return cookies
        except TimeoutException:
            raise Exception('Error: Redirect not happening, ' \
                'wrong DMM email or password?')

    def get_session(self, email, password, fast=False):
        cookies = self.get_session_cookies(email, password, fast)
        session = requests.Session()
        for cookie in cookies:
            session.cookies.set(cookie['name'], cookie['value'])
        return session

    def close_session(self):
        self.driver.delete_all_cookies()

    def close_driver(self):
        DMMRipper.logger.info('Closing webdriver.')
        self.driver.quit()

    def get_books_list(self, soup):
        books = []

        try:
            book_list = soup.find('ul', {'class': \
                'm-boxListBookProductLarge__list'})

            book_divs = book_list.findChildren(attrs={'class': \
                'm-boxListBookProductBlock__wrap'})

            for book_div in book_divs:
                try:
                    book_link = book_div.findChild(attrs={'class': \
                        'm-boxListBookProductBlock__item'}).findChild()['href']
                    title_div = book_div.findChild(attrs={'class': \
                        'm-boxListBookProductBlock__main__info__ttl'})
                    book_details_url = title_div.findChild()['href']
                    title = title_div.findChild().contents[0]

                    thumbnail = book_div.findChild(
                        attrs={'class': 'm-boxListBookProductBlock__main__tmb'}
                    ).findChild('img')['src']

                    url = book_url + book_link

                    books.append({
                        'name': title,
                        'url': url,
                        'details_url': book_details_url,
                        'thumbnail': thumbnail
                    })
                except Exception as e:
                    pass # Book not purchased if book_link missing.
        except Exception as e:
            raise Exception('No book found.')

        return books

    def get_purchased_books(self, session, max_attempts=5):
        books = []
        library_end = False
        page = 1
        error = False
        attempt_num = 0

        while not library_end:
            while (not attempt_num) or (error and attempt_num < max_attempts):
                response = requests.get(library_url,
                    params={'page': page},
                    cookies=session.cookies.get_dict()
                )
                if response.status_code == 200:
                    DMMRipper.logger.info('Successfully requested page %d ' \
                        'of purchased books', page)
                    try:
                        books.extend(self.get_books_list(
                            BeautifulSoup(response.text, 'html.parser'))
                        )
                        page += 1
                        error = False
                        attempt_num = 0
                    except:
                        DMMRipper.logger.info('Purchased book library ended')
                        library_end = True
                        break
                else:
                    DMMRipper.logger.info('Failed to obtain response for '
                        + 'page {} of purchased books, attempt {} out of {}' \
                        .format(
                            page, attempt_num + 1, max_attempts
                        )
                    )
                    error = True
                    attempt_num += 1

        if error:
            raise Exception('Unable to obtain all the purchased books.')
            
        for book in books:
            book['series'] = False
            if 'series' in book['url']:
                book['series'] = True
        
        return books

    def get_book_volumes(self, session, book, max_attempts=5):
        volumes = []
        if 'series' not in book:
            volumes.append(dict(book))
            del volumes[0]['series']
        else:
            last_page = False
            page = 1
            error = False
            attempt_num = 0
            while not last_page:
                while (error and attempt_num < max_attempts) \
                    or (not attempt_num):
                    
                    response = requests.get(book['url'],
                        params={'page': page},
                        cookies=session.cookies.get_dict()
                    )
                    if response.status_code == 200:
                        DMMRipper.logger.info('Successfully requested page ' \
                            '%d of volumes of series', page)
                        soup = BeautifulSoup(response.text, 'html.parser')
                        try:
                            pagination = soup.find('ul', 
                                {'class': 'm-boxPagenation__list'}
                            )
                            last_soup_page = pagination.findChildren('li',
                                {'class': 'm-boxPagenation__list__item'}
                            )[-1]
                            try:
                                volumes.extend(self.get_books_list(soup))
                            except Exception:
                                raise Exception('Unable to obtain all the ' \
                                    + 'volumes in series')
                            try:
                                #if not last page it should contain a link.
                                last_soup_page.findChild()['href']
                                page += 1
                                error = False
                                attempt_num = 0
                            except:
                                last_page = True
                                break
                        except:
                            DMMRipper.logger.exception('Pagination system ' \
                                + 'incompatible.')
                    else:
                        DMMRipper.logger.info('Failed to obtain response for ' \
                            + 'page {} of volumes of series, attempt {} out ' \
                            + 'of {}'.format(
                                page, attempt_num + 1, max_attempts
                            )
                        )
                        error = True
                        attempt_num += 1

            if error:
                raise Exception('Unable to obtain all the volumes in series.')

        return list(reversed(volumes))

    def get_book_details(self, session, details_url):
        details = None
        try:
            response = requests.get(details_url, \
                cookies=session.cookies.get_dict())
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                description = soup.find(
                    'div', {'class': 'm-boxDetailProduct__info__story'}
                ).contents[0].strip()
                product_info = soup.find('div', \
                    {'class': 'm-boxDetailProductInfo'})
                pages = re.match(
                    r'^([0-9]+)ページ', 
                    product_info.findChildren(
                        'dd', \
                        {'class': 'm-boxDetailProductInfo__list__description'}
                    )[2].contents[0].strip()
                ).group(1) 
                details = {'description': description, 'pages': pages}
        except Exception as e:
            print(e)
        return details

    def download_image(self, url, path):
     response = requests.get(url, stream=True)
     if response.status_code == 200:
         with open(path, 'wb') as f:
             for chunk in response.iter_content(chunk_size=1024):
                 f.write(chunk)

    def download_book_toc(self, book, path):
        if self.browser_reader == None:
            self.browser_reader = DMMBrowserReader(
                self.driver,
                book,
                self.webdriver_config
            )
        try:
            self.browser_reader.download_table_of_contents(path)
        except Exception as e:
            DMMRipper.logger.exception(e)

    def download_book_page(self, book, page_num, path, attempts=2):
        if attempts <= 0:
            raise Exception('Page downloads attemps exceeded.')
        try:
            if self.browser_reader == None:
                self.browser_reader = DMMBrowserReader(
                    self.driver,
                    book,
                    self.webdriver_config
                )
            self.browser_reader.download_page(page_num, path)
        except Exception as e:
            DMMRipper.logger.exception(e)
            self.download_book_page(book, page_num, path, attempts=attempts - 1)

    def close_broser_reader(self):
        if self.browser_reader:
            self.browser_reader.close()
            self.browser_reader = None

def download_book(session, book, path):
    response = requests.get(book['url'], cookies=session.cookies.get_dict())
    if response.status_code == 200:
        book_vars = get_book_vars(response.text)
        num_pages = book_vars[var_ids[5]]
        for page in range(1, int(num_pages) + 1):
            page_url = get_page_download_url(book_vars, page)

            response = requests.get(page_url, stream=True)
            if response.status_code == 200:
                with open(get_image_path(path, book_vars, page), \
                    'wb') as f:
                    
                    for chunk in response.iter_content(1024):
                        if chunk:
                            f.write(chunk)

def main(argv):
    DMM_EMAIL = argv[0] 
    DMM_PASSWORD = argv[1]

    dmm = DMMRipper.get_instance(True)
    session = dmm.get_session(DMM_EMAIL, DMM_PASSWORD)
    books = dmm.get_purchased_books(session)
    volumes = dmm.get_book_volumes(session, books[0])
    dmm.close_driver()

if __name__ == '__main__':
    main(sys.argv[1:])
