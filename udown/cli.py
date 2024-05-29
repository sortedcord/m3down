import undetected_chromedriver as webdriver
from loguru import logger

from utils import slugify
from settings import SettingsManager, parse_cookies
from objects import Course
from web import setup_selenium, authenticate_user
from api import fetch_purchased_courses


if __name__ == '__main__':
    SETTINGS = SettingsManager()

    driver:webdriver = setup_selenium(SETTINGS.selenium.webdriver_path, SETTINGS.selenium.browser_path)
    logger.debug("Created driver instance")

    if SETTINGS.auth == 'password':
        SETTINGS.credentials.load(SETTINGS.credentials_file)            
        authenticate_user(driver, SETTINGS.credentials.email, SETTINGS.credentials.password)

    elif SETTINGS.auth == 'cookies':
        cookies: tuple[dict] = parse_cookies(SETTINGS.cookies_file)

        for cookie in cookies:
            if cookie['name'] == "ud_last_auth_information":
                SETTINGS.credentials.email = slugify(cookie['value']).split("-user-email-")[-1].split('-suggested-')[0]

        driver.get("https://udemy.com")

        for cookie in cookies:
            if 'sameSite' in cookie:
                if cookie['sameSite'] in ('strict', 'lax'):
                    cookie['sameSite'] = cookie['sameSite'].title()
                else:
                    cookie['sameSite'] = 'None'
            driver.add_cookie(cookie)
        driver.refresh()
        logger.debug("Loaded cookies")
    
    # LIST PURCHASED COURSES
    
    purchased_courses_response:tuple[dict] = fetch_purchased_courses(driver, SETTINGS)

    purchased_courses:list[Course] = []
    for menu_index, result in enumerate(purchased_courses_response):
        course_title:str = result['title']
        purchased_courses.append(Course(result['id'], SETTINGS, driver, course_title, result['url']))

        print(f"{menu_index} - {course_title}")
    
    selected_index = int(input("Select Course: "))

    selected_course: Course = purchased_courses[selected_index]
    selected_course.fetch(driver, SETTINGS)

    for section in selected_course.content:
        logger.info(f"Downloading section {section}")

        for lesson in section['lessons']:
            lesson.download(SETTINGS, driver)
    
