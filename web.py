import undetected_chromedriver as webdriver
from loguru import logger
import json
import os
import time

from utils import rand_input_delay
from settings import SettingsManager, CacheRole

import undetected_chromedriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException

def wait_until_element_loads(driver:webdriver, parameter, query:str, is_array:bool=False) -> WebElement | tuple[WebElement]:
    if is_array:
        call_function = driver.find_elements
    else:
        call_function = driver.find_element
    
    try:
        element_s = call_function(parameter, query)
    except NoSuchElementException:
        time.sleep(0.2)
        return wait_until_element_loads(driver, parameter, query, is_array)
    
    return element_s


def suppress_exception_in_del(uc:webdriver) -> None:
    old_del = uc.Chrome.__del__

    def new_del(self) -> None:
        try:
            old_del(self)
        except:
            pass
    setattr(uc.Chrome, '__del__', new_del)


def setup_selenium(webdriver_path:str, browser_binary:str, run_headless:bool=True) -> webdriver:
    suppress_exception_in_del(webdriver)

    service = Service(executable_path=webdriver_path)
    options = webdriver.ChromeOptions()
    if run_headless:
        options.add_argument("--headless=new")
    options.binary_location = browser_binary
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = webdriver.Chrome(service=service, options=options)

    return driver


def request_xhr(driver:webdriver, request_url:str, settings:SettingsManager=None, cache_role:CacheRole=None, cache_id:int=None) -> dict:
    logger.debug(request_url)
    use_cache = False
    if None not in (settings, cache_role, cache_id):
        c_ = settings.cache.get(cache_role)
        logger.debug(c_)
        if c_.enabled:
            use_cache = True
            cache_location = os.path.join(settings.cache.directory, cache_role.name, str(cache_id))+'.json'
            logger.debug(cache_location)
            try:                                
                with open(cache_location, 'r') as f:
                    cached_content = f.read()
            except FileNotFoundError:
                logger.debug(f"Cache empty for {cache_role}: {cache_id}")
            else:
                logger.debug(f"Using cache at {cache_role}: {cache_id}")
                return json.loads(cached_content)


    if 'udemy.com' not in driver.current_url:
        driver.get("https://udemy.com")
        rand_input_delay(2)
    
    fetch_script = 'fetch("' + request_url + '", {' + settings.xhr_headers + """,
  "referrerPolicy": "strict-origin-when-cross-origin",
  "body": null,
  "method": "GET",
  "mode": "cors",
  "credentials": "include"
})
.then(response => response.json())
.then(data => {
  arguments[0](data);  // Resolving the promise with data
})
.catch(error => {
  console.error('Error:', error);
  arguments[0](null);  // Resolving the promise with null in case of error
});
"""

    async_result = driver.execute_async_script(fetch_script)

    # Dump cache
    if use_cache:
        with open(cache_location, 'w') as f:
            f.write(json.dumps(async_result))
        logger.info(f"Dumped cache for {cache_role}:{cache_id}")

    return async_result


def authenticate_user(driver: webdriver, email:str, password:str) -> None:
    LOGIN_URL:str = "https://www.udemy.com/join/login-popup/?locale=en_US"
    driver.get(LOGIN_URL)

    email_input:WebElement = wait_until_element_loads(driver, By.XPATH, """//*[@cache_id="form-group--1"]""")
    email_input.click()
    email_input.send_keys(email)

    password_input = driver.find_element(By.XPATH, """//*[@cache_id="form-group--3"]""")
    password_input.click()
    password_input.send_keys(password)

    submit_button = driver.find_element(By.XPATH, """//*[@cache_id="udemy"]/div[1]/div[2]/div/div/form/button""")
    submit_button.click()


def quit_browser(driver: webdriver) -> None:
    try:
        driver.close()
        driver.quit()
    except Exception as e:
        logger.error(e)
        logger.error("Could not stop selenium instance")
    else:
        logger.info("Stopped selenium instance")

