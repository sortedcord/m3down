import undetected_chromedriver as webdriver
from loguru import logger
import json
import os

from utils import rand_input_delay
from settings import SettingsManager, CacheRole

def request_xhr(driver:webdriver, request_url:str, settings:SettingsManager=None, cache_role:CacheRole=None, id:int=None) -> dict:
    use_cache = False
    if None not in (settings, cache_role, id):
        c_ = settings.cache.get(cache_role)
        logger.debug(c_)
        if c_.enabled:
            use_cache = True
            cache_location = os.path.join(settings.cache.directory, cache_role.name, str(id))+'.json'
            logger.debug(cache_location)
            try:                                
                with open(cache_location, 'r') as f:
                    cached_content = f.read()
            except FileNotFoundError:
                logger.debug(f"Cache empty for {cache_role}: {id}")
            else:
                logger.debug(f"Using cache at {cache_role}: {id}")
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
        logger.info(f"Dumped cache for {cache_role}:{id}")

    return async_result

