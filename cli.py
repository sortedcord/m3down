import sys
import os

from enum import Enum
import json
from loguru import logger

import undetected_chromedriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from utils import clear_screen, rand_input_delay, slugify
from settings import CacheRole, SettingsManager, CookieProcessType, process_cookies
from objects import Course, Lesson, LessonType
from web import request_xhr


def suppress_exception_in_del(uc:webdriver):
    old_del = uc.Chrome.__del__

    def new_del(self) -> None:
        try:
            old_del(self)
        except:
            pass
    
    setattr(uc.Chrome, '__del__', new_del)


def setup_selenium(settings:SettingsManager) -> webdriver:
    webdriver_path = settings.selenium.webdriver_path
    browser_binary = settings.selenium.browser_path

    suppress_exception_in_del(webdriver)
    logger.debug("Supressed undetected_chromedirver exception")
    service = Service(executable_path=webdriver_path)
    logger.debug(f"Set chromedriver path to '{webdriver_path}'")
    options = webdriver.ChromeOptions()
    options.binary_location = "chrome/chrome.exe"
    logger.debug(f"Set browser binary path to '{browser_binary}'")
    options.add_argument("--disable-blink-features=AutomationControlled")
    logger.debug("Starting browser")
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_window_size(1566, 500)
    driver.set_window_position(0,0)
    return driver


def macro_view_course(course:Course, driver:webdriver, *args, **kwargs):
    driver.get(course.redirect_link)


def macro_login(driver: webdriver, email:str, password:str):
    rdy = rand_input_delay

    driver.get("https://www.udemy.com/join/login-popup/?locale=en_US")

    while True:
        try:
            email_input = driver.find_element(By.XPATH, """//*[@id="form-group--1"]""")
        except:
            rdy()
        else:
            break
    email_input.click()
    rdy()
    email_input.send_keys(email)
    rdy()
    password_input = driver.find_element(By.XPATH, """//*[@id="form-group--3"]""")
    password_input.click()
    rdy()
    password_input.send_keys(password)
    rdy()
    submit_button = driver.find_element(By.XPATH, """//*[@id="udemy"]/div[1]/div[2]/div/div/form/button""")
    submit_button.click()
        

def macro_search_course(driver:webdriver, query:str):
    if "udemy.com" not in driver.current_url:
        driver.get("https://udemy.com")
    
    i = 0
    while True:
        try:
            search_input = driver.find_elements(By.TAG_NAME, "input")
            for i in search_input:
                if i.get_attribute("placeholder") is not None:
                    if i.get_attribute("placeholder") == "Search for anything":
                        search_input = i
                        break      
        except Exception as e:
            if i==5:
                logger.warning("Could not find search bar, redirecting to homepage...")
                driver.get("https://udemy.com")
                i+=1
                continue
            if i == 10:
                logger.error("Could not find search after 5 tries, cancelling search...")
                return
            i+= 1
            logger.error("Could not get element; trying again")
            logger.error(e)
            rand_input_delay()
            continue
        else:
            if search_input is not None:
                break
    
    search_input.clear()
    search_input.send_keys(query)
    search_input.send_keys(Keys.RETURN)


def get_purchased_courses(driver:webdriver, settings:SettingsManager) -> list:
    data = request_xhr(driver=driver, 
                       settings=settings,
                       request_url="https://www.udemy.com/api-2.0/users/me/subscribed-courses/?ordering=-last_accessed&fields%5Bcourse%5D=title,url&fields%5Buser%5D=@min,job_title&page=1&page_size=120&is_archived=false", 
                       cache_role=CacheRole.purchasedCourses, 
                       id=slugify(settings.credentials.email))['results']
    logger.debug(f"Found {len(data)} purchased courses")
    courses:list[Course] = []
    for result in data:
        courses.append(Course(id=result['id'], settings=settings, driver=driver, title=result['title']))
    
    logger.info(f"Fetched {len(courses)} purchased courses.")
    return courses


def render_menu(options: dict, title:str="Menu", clear_screen_:bool=False):
    if clear_screen_:
        clear_screen()

    width = os.get_terminal_size()[0]

    # RENDER TITLE
    dec_line = "="*width
    title_line = dec_line[:width//2]+" "+title+" "+dec_line[:width//2]
    cut_ = (len(title_line)-len(dec_line))//2
    title_line = title_line[cut_:-cut_]
    print(title_line)

    # RENDER OPTIONS
    i = 0
    for _, description in options.items():
        print(f"{i} - {description}")
        i+=1


def option_search_course(driver: webdriver, settings:SettingsManager):
    query = input("Enter Search Query: ")
    macro_search_course(driver, query)


def option_purchased_courses(driver: webdriver, settings:SettingsManager):
    logger.debug("Fetching purchased Courses")
    purchased_courses = get_purchased_courses(driver=driver, settings=settings)

    # Select Course Menu
    courses_options = {}
    for i, course in enumerate(purchased_courses):
        courses_options[f"{i}"] = course.title

    courses_options['b'] = "Go Back To Main Menu!"

    while True:
        render_menu(options=courses_options, title="SELECT COURSE")
        while True:
            try:
                course_sel = int(input("Select Course: "))         
            except:
                logger.error("Not a valid integer, try again...")
                continue
            
            if course_sel == len(purchased_courses):
                return
            
            if course_sel not in list(range(len(purchased_courses))):
                logger.error("Option not in range, try again")
                continue
            break

        current_course:Course = purchased_courses[course_sel]
        current_course.fetch(driver=driver, settings=settings)

        for lesson in current_course.content[0]['lessons']:
            lesson:Lesson = lesson
            lesson.download(settings, driver)
            option_quit(driver, settings)
        

def option_quit(driver: webdriver, settings:SettingsManager):
    try:
        driver.close()
        driver.quit()
    except Exception as e:
        logger.error(e)
        logger.error("Could not stop selenium instance")
    else:
        logger.info("Stopped selenium instance")
    
    logger.info("Quitting Application")
    quit()


def main_menu(driver: webdriver, settings:SettingsManager) -> str:
    options = {option_search_course: "Search for Courses", 
               option_purchased_courses: "View purchased Courses", 
               option_quit: "Quit Application"}

    render_menu(options, "MAIN MENU")

    choice = int(input("Enter Choice: "))

    av = list(range(len(options.items())))
    if choice not in av:
        logger.debug(f"Available: {av}")
        logger.error("Entered option not available")
        return main_menu(driver)
    
    # Handle Options
    return list(options.keys())[int(choice)](driver, settings=settings)


if __name__ == '__main__':
    SETTINGS = SettingsManager()
    logger.info(f'Set Authorization Method: {SETTINGS.auth}')

    if SETTINGS.auth == 'cookies':
        SETTINGS = process_cookies(CookieProcessType.LOAD, settings=SETTINGS)
        if SETTINGS.cookies is None:
            logger.error("Cookies could not be loaded")
            quit()
        logger.debug(f"Parsed {len(SETTINGS.cookies)} cookies.")

    elif SETTINGS.auth == 'password':
        SETTINGS.credentials.load(SETTINGS.credentials_file)            
        logger.info(f"Using email: {SETTINGS.credentials.email}")
    
    driver = setup_selenium(SETTINGS)
    logger.info("Initialized selenium instance.")

    # Log into udemy
    if SETTINGS.auth == 'password':
        macro_login(driver, SETTINGS.credentials.email, SETTINGS.credentials.password)
        logger.success("Logged in Successfully")
    
    if SETTINGS.auth == 'cookies':
        driver.get("https://udemy.com")
        logger.debug("Redirected to udemy.com")

        # Fix keys, (generally when exported using editThisCookie extension)
        for cookie in SETTINGS.cookies:
            if 'sameSite' in cookie:
                logger.debug("Fixing sameSite key")
                if cookie['sameSite'] == 'strict':
                    cookie['sameSite'] = 'Strict'
                elif cookie['sameSite'] == 'lax':
                    cookie['sameSite'] = 'Lax'
                else:
                    cookie['sameSite'] = 'None'

            driver.add_cookie(cookie)

        logger.debug(f"Injected {len(SETTINGS.cookies)} cookies.")
        logger.debug("Refreshing page")
        driver.refresh()
    
    logger.debug("Drawing main menu...")
    while True:
        main_menu(driver, SETTINGS)

