import json
import os
import undetected_chromedriver as webdriver
from loguru import logger
from enum import Enum
import requests
import re
import concurrent.futures

from rich.progress import Progress

from settings import SettingsManager, CacheRole
from web import request_xhr
from utils import slugify, parse_m3u, get_filename_from_link, download_ts
from api import fetch_lesson_data, fetch_article_body


class Course():
    def __init__(self, id:int, settings:SettingsManager, driver:webdriver, title:str=None, url:str=None) -> None:
        if title is None:
            title = ""

        self.id = id
        self.title = title

        if url is not None:
            self.slug = url.split("/course/")[-1].split("/")[0]
            if "https://udemy.com" not in url:
                url = "https://udemy.com" + url
            self.url = url
            self.__dump_lookup__(settings)
        else:
            self.__lookup__(driver, settings)

    def fetch(self, driver:webdriver, settings:SettingsManager) -> None:
        logger.debug(f"Requesting Course Content for {self.title} ({self.id})")
        try:
            _ = request_xhr(driver, 
                            f"https://www.udemy.com/api-2.0/courses/{self.id}/subscriber-curriculum-items/?page_size=1200&fields%5Blecture%5D=title,object_index,asset,supplementary_assets&fields%5Bquiz%5D=title,object_index,is_published,sort_order,type&fields%5Bpractice%5D=title,object_index,is_published,sort_order&fields%5Bchapter%5D=title,object_index,is_published,sort_order&fields%5Basset%5D=title,filename,asset_type,is_external&caching_intent=True",
                            settings=settings,
                            cache_role=CacheRole.courseContent,
                            cache_id=self.id)
            
            response = _['results']
        except KeyError:
            logger.error(_)
            logger.error("Could not fetch course content.")
            return
            
        logger.debug("Parsing Course content")
        sections = []
        current_section = None
        section_lesson = 1

        logger.debug(f"Fetched {len(response)} items")
        for item in response:
            if item['_class'] == "chapter":
                section_lesson=1
                sections.append({
                    'id': item['id'],
                    'index': item['object_index'],
                    'title': item['title'],
                    'lessons': []
                })
                current_section = item['object_index']
                continue
            
            if item['_class'] == "lecture":
                title = item['title']
                match item['asset']['asset_type']:                
                    case "Video":
                        lesson_type = LessonType.VIDEO
                        filename = item['asset']['filename']
                    case "Article":
                        lesson_type = LessonType.ARTICLE
                        filename = slugify(title)+".md"

                sections[current_section-1]['lessons'].append(Lesson(
                    id=item['id'],
                    course=self,
                    title=title,
                    lesson_type=lesson_type,
                    course_index=item['object_index'],
                    hierarchal_index=(current_section, section_lesson),
                    filename=filename
                ))
                section_lesson+=1
        
        self.content = sections
        logger.success(f"Parsed {len(self.content)} course sections.")
    
    def __lookup__(self, driver, settings:SettingsManager):
        logger.debug("Fetching course information")
        try:
            data = request_xhr(driver, f"https://www.udemy.com/api-2.0/courses/{self.id}/?fields%5Bcourse%5D=title,url", settings, CacheRole.courseIdLookup, self.id)
        except Exception as e:
            driver.close()
            driver.quit()
            raise e
        
        self.title = data['title']
        self.slug = data['url'].replace('/course/','')[:-1]
        self.url = 'https://udemy.com'+data['url']
        logger.debug(f"Fetched data: ID={self.id} TITLE={self.title} URL={self.url}")

    def __dump_lookup__(self, settings:SettingsManager) -> None:
        dump_loc = os.path.join(settings.cache.directory, CacheRole.courseIdLookup.name, str(self.id))

        if os.path.exists(dump_loc):
            return
        
        with open(dump_loc, "w") as f:
            f.write(json.dumps({"_class":"course", "id": self.id, "title": self.title, "url": self.url.split(".com")}))

class LessonType(Enum):
    VIDEO = 'VIDEO'
    ARTICLE = 'ARTICLE'

class Lesson():
    url = "https://www.udemy.com/$course-slug/learn/lecture/$lesson-id"
    def __init__(self, id:int, course:Course, title:str="Lesson Title", lesson_type:LessonType=LessonType.VIDEO, course_index:int=0, hierarchal_index:tuple[int]=(0,0), filename:str = "lesson.mp4"):
        self.id = id
        self.course = course

        self.title = title
        self.lesson_type = lesson_type
        self.course_index = course_index
        self.h_index = hierarchal_index
        self.filename = filename

        self.url = self.url.replace('$course-slug', self.course.slug) \
                            .replace('$lesson-id', str(self.id))
    
    def get_section(self) -> dict:
        for section in self.course.content:
            if self in section['lessons']:
                return section    
        logger.error(f"Could not find section containing {self.title}")

    def download(self, settings:SettingsManager, driver:webdriver) -> None:
        logger.debug(f"Download {self.title}")

        if self.lesson_type == LessonType.VIDEO:
            ext = "mkv"
        elif self.lesson_type == LessonType.ARTICLE:
            ext = "html"

        download_location = settings.download_location.replace('$course-slug', self.course.slug) \
                                                      .replace('$section-slug', slugify(self.get_section()['title'])) \
                                                      .replace('$ind-section-slug', f"{self.h_index[0]}-{slugify(self.get_section()['title'])}") \
                                                      .replace('$lesson-slug', slugify(self.title)) \
                                                      .replace('$ind-lesson-slug', f"{self.h_index[0]}.{self.h_index[1]}-{slugify(self.title)}") \
                                                      .replace('$ext', ext)
        
        logger.debug(f"Set download location as {download_location}")
        os.makedirs(os.path.dirname(download_location), exist_ok=True)

        if os.path.exists(download_location):
            logger.success(f"Downloaded Lesson{self.h_index[0]}.{self.h_index[1]} {self.title}")
            return

        lesson_data = fetch_lesson_data(self.course.id, self.id, driver, settings)

        if self.lesson_type == LessonType.VIDEO:
            stream_id = int(f"{self.course.id}{self.id}")

            stream_qualities_url = lesson_data['asset']['media_sources'][0]['src']

            # Get streams
            content = requests.get(stream_qualities_url).text

            video_streams = []
            for stream in content.split('#EXT-X-STREAM-INF:')[1:]:
                stream = {
                    "url": stream.split('\n')[1],
                    "resolution": re.search(r'RESOLUTION=([0-9]+x[0-9]+)', stream).group(1),
                    "bandwidth": re.search(r'BANDWIDTH=([0-9]+)', stream).group(1),
                    "frame_rate": re.search(r'FRAME-RATE=([0-9]+)', stream).group(1),
                    "codecs": re.search(r'CODECS="([^"]+)"', stream).group(1)
                }
                video_streams.append(stream)
            
            try:
                match settings.download_video_resolution:
                    case "max":
                        sel_stream = video_streams[-1]
                    case _:
                        sel_stream = video_streams[0]
            except IndexError:
                logger.error("Stream data cache has expired and is no longer valid. Fetching stream again.")
                settings.cache.delete(CacheRole.lessonStreams, stream_id)
                logger.debug(f"Deleted cache {CacheRole.lessonStreams.name}:{stream_id}")
                return self.download(settings, driver)
            
            logger.info(f"Selected Stream: {sel_stream['resolution']} CODEC: {sel_stream['codecs']}")
            
            # Download stream
            stream_segment_urls = parse_m3u(stream['url'])
            stream_segment_files = [f"file '{get_filename_from_link(x)}.ts'\n" for x in stream_segment_urls]
            with open('.udownsegments', 'w') as f:
                f.writelines(stream_segment_files)
            
            # Start Download
            with Progress() as progress:
                task1 = progress.add_task("[red]Downloading lesson...", total=len(stream_segment_urls))

                with concurrent.futures.ThreadPoolExecutor(max_workers=settings.download_threads) as executor:
                    future_to_url = {executor.submit(download_ts, url): url for url in stream_segment_urls}
                    
                    for future in concurrent.futures.as_completed(future_to_url):
                        url = future_to_url[future]
                        try:
                            future.result()
                        except Exception as e:
                            print(f"Error downloading {url}: {str(e)}") 
                        else:
                            progress.update(task1, advance=1)
            logger.debug(f"Downloaded Stream segments for Lesson{self.h_index[0]}.{self.h_index[1]} {self.title}")

            caption_ffmpeg = ""
            caption_input = ""
            caption_map = ""
            caption_metadata = ""

            # Download captions
            if settings.download_captions:
                caption_streams = lesson_data['asset']['captions']

                caption_files = []
                # Save captions
                logger.debug(f"Downloading {len(caption_streams)} caption streams")
                for caption_stream in caption_streams:
                    i = caption_streams.index(caption_stream)
                    file_name = f"sub_{caption_stream['locale_id']}.vtt"

                    if not os.path.exists(file_name):
                        with open(file_name, 'wb') as subfile:
                            subfile.write(requests.get(caption_stream['url']).content)
                    caption_files.append(file_name)

                    caption_input += f"-i {file_name} "
                    caption_map += f"-map {i} "
                    caption_metadata += f"-metadata:s:s:{i} language={caption_stream['video_label'].split(' ')[0]} "
                    logger.debug(f"Downloaded {caption_stream['video_label']} captions")
                
                caption_ffmpeg = caption_input + caption_map + caption_metadata

            # Merge into single file
            ffmpeg_command = f'ffmpeg -f concat -i .udownsegments {caption_ffmpeg} -acodec copy -vcodec copy "{download_location}"'
            logger.debug(ffmpeg_command)
            os.system(ffmpeg_command)

            # Clean Up
            for file in stream_segment_files:
                file_path = file.split("'")[1].split("'")[0]
                try:
                    os.remove(file_path)
                except:
                    logger.error(f"Could not remove {file_path}")
            logger.debug("Removed stream segments.")
            os.remove('.udownsegments')
            for file in caption_files:
                os.remove(file)
        
        elif self.lesson_type == LessonType.ARTICLE:
            asset_id = lesson_data['asset']['id']
            lesson_body = fetch_article_body(asset_id, self.id, self.course.id, driver, settings)

            with open(download_location, 'w') as f:
                f.write(lesson_body['body'])
        
        logger.success(f"Downloaded Lesson{self.h_index[0]}.{self.h_index[1]} {self.title}")
            