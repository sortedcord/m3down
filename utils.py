import re
from os import system, name
import time
import random
from enum import Enum
import requests
import os

class ExtendedEnum(Enum):
    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))

def slugify(s):
  s = s.lower().strip()
  s = re.sub(r'[^\w\s-]', '', s)
  s = re.sub(r'[\s_-]+', '-', s)
  s = re.sub(r'^-+|-+$', '', s)
  return s

class LinkType(Enum):
    M3U = 'M3U'
    TS = 'TS'
    LINK = 'LINK'
    VTT = 'VTT'


def get_filename_from_link(link: str) -> str:
    return link.split('.ts')[0].split('/')[-1]


def get_link_type(link:str) -> LinkType:

    if '.ts' in link:
        return LinkType.TS
    elif '.m3u' in link:
        return LinkType.M3U
    elif '.vtt' in link:
        return LinkType.VTT
    else:
        return LinkType.LINK


def clear_screen() -> None:
    if name == 'nt':
        _ = system('cls') 
    else:
        _ = system('clear')

def rand_input_delay(delay:int=None):
    if delay is None:
        time.sleep(delay)
        return
    time.sleep(random.randint(50,90)*0.01)

def parse_m3u(url:str) -> list[str]:
    response = requests.get(url)
    ts_files = []
    for line in response.text.split('\n'):
        if not line.startswith('http'):
            continue
        if get_link_type(line) == LinkType.TS:
            ts_files.append(line)
    return ts_files

def download_ts(link:str):
    file_name = get_filename_from_link(link)
    if os.path.exists(file_name+'.ts'):
        return
    
    stream_content = requests.get(link)    
    with open(file_name+'.ts', 'wb') as f:
        f.write(stream_content.content)