import json
from loguru import logger
from utils import ExtendedEnum
import os
from enum import Enum

from utils import slugify

class CacheRole(ExtendedEnum):
    courseIdLookup = "courseIdLookup"
    courseContent = "courseContent"
    lessonStreams = "lessonStreams"
    purchasedCourses = "purchasedCourses"

class CacheSetting():
    def __init__(self, role:CacheRole, enabled:bool, expire:int) -> None:
        self.role = role
        self.enabled = enabled
        self.expire = expire
    
    def __str__(self) -> str:
        return f"{self.role}; enabled: {self.enabled}; Expiry: {self.expire}"

class CacheManager():
    cache_settings:list[CacheSetting] = []
    directory = ".ud_cache"

    def __init__(self, directory:str, settings:dict) -> None:
        self.directory = directory

        try:
            os.mkdir(self.directory)
        except FileExistsError:
            pass

        
        for _role in CacheRole.list():
            try:
                self.cache_settings.append(
                    CacheSetting(role=CacheRole[_role], 
                                enabled=settings[_role]['use_cache'],
                                expire=settings[_role]['expire'])
                )

                try:
                    os.mkdir(os.path.join(self.directory, _role))
                except FileExistsError:
                    pass
                
            except KeyError as k:
                logger.error(f"Settings file is missing cache paramter: {k}")
                quit()
        
    
    def get(self, role:CacheRole) -> CacheSetting:
        for cache_setting in self.cache_settings:
            if cache_setting.role == role:
                return cache_setting
    
    def location(self, role:CacheRole, id:int=None) -> str:
        if id is None: id = ""
        return os.path.join(self.directory, role.name, id)

    def delete(self, role:CacheRole, id:int):
        location = self.location(role, id)
        if os.location.exists(location):
            os.remove(location)
        else:
            logger.warn(f"Tried to delete cache file at {location} does not exist.")
        

class CredentialsObject():
    def __init__(self, email:str, password:str) -> None:
        self.email = email
        self.password = password
    
    def load(self, credentials_file:str):
        try:
            with open(credentials_file, 'r') as file:
                content = file.read()
        except FileNotFoundError:
                logger.error(f"Credentials file {credentials_file} does not exist.")
                quit()
        except IOError:
            logger.error(f"Credentials file {credentials_file} could not be read")
            quit()
        
        if content.strip() == "":
            logger.error("Credentials file is empty")
            quit()
        
        try:
            credentials = json.loads(content)
        except json.decoder.JSONDecodeError:
            logger.error(f"Credentials file {credentials_file} could not be parsed")
            quit()
        
        try:
            if "none" in (credentials['email'], credentials['password']):
                logger.error("Placeholder login details cannot be used.")
                quit()
        except KeyError:
            logger.error("Credentials file has not been formatted correctly.")
            quit()
        
        self.email = credentials['email']
        self.password = credentials['password']
        

class SeleniumSettings():
    def __init__(self, webdriver_path:str="chrome/chromedriver.exe", browser_path:str="chrome/chrome.exe", headless:bool=False) -> None:
        self.webdriver_path = webdriver_path
        self.browser_path = browser_path
        self.headless = headless


class CookieProcessType(Enum):
    LOAD = 'LOAD'
    DUMP = 'DUMP'


class SettingsManager():
    settings_file = "settings.json"
    credentials_file = "credentials.json"
    credentials = CredentialsObject("none", "none")
    cookies = []

    download_video_resolution = "max"
    download_location = "downloads/$course-slug/$section-slug/$lesson-slug"
    download_captions = True
    download_threads = 4

    def __init__(self) -> None:
        self.load()

    def load(self, settings_file:str=None):        
        if settings_file is None:
            settings_file = self.settings_file
        logger.info(f"Using settings file {settings_file}")

        try:
            with open(settings_file, "r") as f:
                content = f.read()
                settings_dict = json.loads(content)
        except FileNotFoundError:
            logger.error(f"Settings file does not exist at {settings_file}.")
            quit()
        except json.decoder.JSONDecodeError:
            logger.error(f"Could not parse settings into json format.")
            quit()
        try:
            self.auth = settings_dict['auth']
            
            self.cookies_file = settings_dict['cookies']
            self.credentials_file = settings_dict['credentials']['file']
            self.selenium = SeleniumSettings(
                webdriver_path=settings_dict["selenium"]["webdriver_path"],
                browser_path=settings_dict["selenium"]["browser_path"],
                headless=settings_dict["selenium"]["headless"]
            )

            self.download_video_resolution = settings_dict['downloads']['video_resolution']
            self.location = settings_dict['downloads']['location']
            self.download_threads = settings_dict['downloads']['threads']
            self.download_captions = settings_dict['downloads']['captions']
            self.download_location = settings_dict['downloads']['location']

            _fi = settings_dict['xhr_headers']
            with open(_fi, 'r') as f:
                self.xhr_headers = f.read()

            
            self.cache = CacheManager(settings_dict['cache']['directory'], settings_dict['cache']['settings'])
        except KeyError as e:
            logger.error(f"Settings file is missing {e} parameter..")            
            quit()


def process_cookies(process:CookieProcessType, settings:SettingsManager) -> tuple[dict, SettingsManager]:
    if process == CookieProcessType.LOAD:
        try:
            with open('cookies.json', 'r') as file:
                content = file.read()
        except FileNotFoundError:
            logger.error("Cookies file does not exist. Cookies are to be stored in cookies.json")
            quit()
        except IOError:
            logger.error("Cookies file could not be read")
            quit()
        
        if content.strip() == "":
            logger.error("Cookies file is empty")
            quit()
        
        try:
            cookies = json.loads(content)
        except:
            logger.error("Cookies file could not be parsed")
            quit()

        try:
            for cookie in cookies:
                if cookie['name'] == "ud_last_auth_information":
                    settings.credentials.email = slugify(cookie['value']).split("-user-email-")[-1].split('-suggested-')[0]
        except:
            pass

        settings.cookies = cookies
        
        return settings