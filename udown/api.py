from web import request_xhr
from settings import SettingsManager, CacheRole
from utils import slugify

from enum import Enum
import undetected_chromedriver as webdriver

class ApiEndpointUrl(Enum):
    purchasedCourses = "https://www.udemy.com/api-2.0/users/me/subscribed-courses/?ordering=-last_accessed&fields%5Bcourse%5D=title,url&fields%5Buser%5D=@min,job_title&page=1&page_size=120&is_archived=false"
    courseContent = "https://www.udemy.com/api-2.0/courses/$course-id$/subscriber-curriculum-items/?page_size=1200&fields%5Blecture%5D=title,object_index,asset,supplementary_assets&fields%5Bquiz%5D=title,object_index,is_published,sort_order,type&fields%5Bpractice%5D=title,object_index,is_published,sort_order&fields%5Bchapter%5D=title,object_index,is_published,sort_order&fields%5Basset%5D=title,filename,asset_type,is_external&caching_intent=True"
    lessonContent = "https://www.udemy.com/api-2.0/users/me/subscribed-courses/$course-id$/lectures/$lesson-id$/?fields[lecture]=asset&fields[asset]=asset_type,media_sources,captions&q=0.03258319668748011"
    lessonArticle = "https://www.udemy.com/api-2.0/assets/$asset-id$/?fields[asset]=@min,body&course_id=$course-id$&lecture_id=$lesson_id$"


def fetch_purchased_courses(driver:webdriver, settings:SettingsManager) -> tuple[dict]:
    data = request_xhr(driver=driver, 
                       settings=settings,
                       request_url=ApiEndpointUrl.purchasedCourses.value, 
                       cache_role=CacheRole.purchasedCourses, 
                       cache_id=slugify(settings.credentials.email))['results']

    return data

def fetch_article_body(asset_id:int, lesson_id:int,course_id:int,driver:webdriver, settings:SettingsManager) -> str:
    format_params = {
        '$course-id$':str(course_id),
        '$asset-id$': str(asset_id),
        '$lesson-id$': str(lesson_id)
    }
    
    url = ApiEndpointUrl.lessonArticle.value

    for template, value in format_params.items():
        url = url.replace(template, value)
    
    data = request_xhr(driver, url, settings, CacheRole.articleBody, str(course_id)+str(lesson_id))
    return data

    """
    {
    "_class": <str>,
    "id": <int>,
    "asset_type": "Article"<str>,
    "title": ""<str>,
    "created": "2024-01-02T07:31:27Z"<str:datetime>,
    "body": "body of the article (html code)"<str>,
}
    """


def fetch_lesson_data(course_id:int, lesson_id:int, driver:webdriver, settings:SettingsManager) -> dict:
    format_params = {
        '$course-id$':str(course_id),
        '$lesson-id$': str(lesson_id)
    }

    url = ApiEndpointUrl.lessonContent.value

    for template, value in format_params.items():
        url = url.replace(template, value)

    data = request_xhr(driver, url, settings, CacheRole.lessonStreams, str(course_id)+str(lesson_id))

    return data

    """
    {
    "_class": "lecture",
    "asset": {
        "_class": "asset",
        "asset_type": "Video",
        "captions": [
            {
                "_class": "caption",
                "asset_id": 48608076,
                "created": "2023-05-07T06:01:10Z",
                "file_name": "b70911a9-82cf-4341-b198-1e277246c41e.vtt",
                "id": 35525496,
                "locale_id": "en_US",
                "source": "manual",
                "status": 1,
                "title": "chat-app-21-storing-a-username.vtt",
                "url": "",
                "video_label": "English"
            },
           
        ],
        "id": 48608076,
        "media_sources": [
            {
                "label": "auto",
                "src": "https://www.udemy.com/assets/48608076/files/2023-05-05_14-42-48-364b6efc0e4b74dd51c1faecee5f7b61/2/aa00506e4624d288b2c903d67b96e5f48647.m3u8?token=eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJwYXRoIjoiMjAyMy0wNS0wNV8xNC00Mi00OC0zNjRiNmVmYzBlNGI3NGRkNTFjMWZhZWNlZTVmN2I2MS8yLyIsImV4cCI6MTcxNjk0NjMzOX0.d6ekHEA7me9eCWlROxJG1KnTBaexOKEj3H4qCMmmit0&provider=cloudfront&v=1",
                "type": "application/x-mpegURL"
            }
        ],
    },
    "id": 37736680
}
    """

