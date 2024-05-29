from web import request_xhr
from settings import SettingsManager, CacheRole
from utils import slugify

from enum import Enum
import undetected_chromedriver as webdriver

class ApiEndpointUrl(Enum):
    purchasedCourses = "https://www.udemy.com/api-2.0/users/me/subscribed-courses/?ordering=-last_accessed&fields%5Bcourse%5D=title,url&fields%5Buser%5D=@min,job_title&page=1&page_size=120&is_archived=false"
    courseContent = "https://www.udemy.com/api-2.0/courses/$course-id$/subscriber-curriculum-items/?page_size=1200&fields%5Blecture%5D=title,object_index,asset,supplementary_assets&fields%5Bquiz%5D=title,object_index,is_published,sort_order,type&fields%5Bpractice%5D=title,object_index,is_published,sort_order&fields%5Bchapter%5D=title,object_index,is_published,sort_order&fields%5Basset%5D=title,filename,asset_type,is_external&caching_intent=True"

def fetch_purchased_courses(driver:webdriver, settings:SettingsManager) -> tuple[dict]:
    data = request_xhr(driver=driver, 
                       settings=settings,
                       request_url=ApiEndpointUrl.purchasedCourses.value, 
                       cache_role=CacheRole.purchasedCourses, 
                       cache_id=slugify(settings.credentials.email))['results']

    return data
    