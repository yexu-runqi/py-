import requests
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin
from base.spider import Spider
import sys
sys.path.append('..')

xurl = "https://www.baihetv.com/"
headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 13; M2102J2SC Build/TKQ1.221114.001; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/144.0.7559.31 Mobile Safari/537.36',
    'Referer': xurl,
}

class Spider(Spider):
    def getName(self):
        return "百合影院"

    def init(self, extend):
        pass

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
        resp = requests.get(xurl, headers=headers, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, 'lxml')
        class_items = []
        nav_items = soup.select('.stui-header__menu li')
        for item in nav_items[:7]:
            a = item.select_one('a')
            if not a:
                continue
            href = a.get('href')
            name = a.get_text(strip=True)
            match = re.search(r'/list/([^/.]+)\.html', href)
            if match:
                class_items.append({
                    "type_id": match.group(1),
                    "type_name": name
                })
        return {
            "class": class_items,
            "filters": {}
        }

    def _parse_video_items(self, soup):
        videos = []
        items = soup.select('li')
        for li in items:
            a = li.select_one('.lazyload')
            if not a:
                continue
            href = a.get('href')
            name = a.get('title', '').strip()
            pic = a.get('data-original', '')
            if pic and not pic.startswith('http'):
                pic = urljoin(xurl, pic)
            remark_tag = li.select_one('.text-right')
            remark = remark_tag.get_text(strip=True) if remark_tag else ''
            videos.append({
                "vod_id": href,
                "vod_name": name,
                "vod_pic": pic,
                "vod_remarks": remark
            })
        return videos

    def homeVideoContent(self):
        resp = requests.get(xurl, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {'list': self._parse_video_items(soup)}

    def categoryContent(self, cid, pg, filter, ext):
        page = int(pg) if pg else 1
        cateId = ext.get('cateId', cid) if ext else cid
        class_ = ext.get('class', '') if ext else ''
        area = ext.get('area', '') if ext else ''
        lang = ext.get('lang', '') if ext else ''
        letter = ext.get('letter', '') if ext else ''
        year = ext.get('year', '') if ext else ''
        by = ext.get('by', '') if ext else ''
        url = f"{xurl}/tags/{cateId}-{area}-{by}-{class_}-{lang}-{letter}---{page}---{year}.html"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {
            'list': self._parse_video_items(soup),
            'page': page,
            'pagecount': page + 1,
            'limit': 90,
            'total': 9999
        }

    def detailContent(self, ids):
        did = ids[0]
        if not did.startswith('http'):
            did = urljoin(xurl, did)
        resp = requests.get(did, headers=headers, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, 'lxml')
        vod = {}

        vod["vod_id"] = did

        title_tag = soup.select_one('h1')
        vod["vod_name"] = title_tag.get_text(strip=True) if title_tag else ''

        img_tag = soup.select_one('.stui-content__thumb img')
        if img_tag:
            pic = img_tag.get('data-original') or img_tag.get('src') or ''
            if pic and not pic.startswith('http'):
                pic = urljoin(xurl, pic)
            vod["vod_pic"] = pic
        else:
            vod["vod_pic"] = ''

        year_tag = soup.select_one('p:contains("年份")')
        if year_tag:
            year_text = year_tag.get_text(strip=True)
            year_match = re.search(r'(\d{4})', year_text)
            vod["vod_year"] = year_match.group(1) if year_match else ''
        else:
            vod["vod_year"] = ''

        area_tag = soup.select_one('p:contains("地区")')
        if area_tag:
            area_text = area_tag.get_text(strip=True).replace('地区：', '')
            vod["vod_area"] = area_text.strip()
        else:
            vod["vod_area"] = ''

        status_tag = soup.select_one('p:contains("状态")')
        if status_tag:
            status_text = status_tag.get_text(strip=True).replace('状态：', '')
            vod["vod_remarks"] = status_text.strip()
        else:
            vod["vod_remarks"] = ''

        type_tags = soup.select('p:contains("类型") a')
        if type_tags:
            vod["type_name"] = '/'.join([a.get_text(strip=True) for a in type_tags])
        else:
            vod["type_name"] = ''

        actor_tags = soup.select('p:contains("演员") a')
        vod["vod_actor"] = '/'.join(filter(None, [a.get_text(strip=True) for a in actor_tags]))

        director_tags = soup.select('p:contains("导演") a')
        vod["vod_director"] = '/'.join(filter(None, [a.get_text(strip=True) for a in director_tags]))

        intro_tag = soup.select_one('span.detail-content')
        if intro_tag:
            intro_text = intro_tag.get_text(strip=True)
            intro_text = re.sub(r'^剧情[：:]\s*', '', intro_text)
            vod["vod_content"] = intro_text
        else:
            vod["vod_content"] = ''

        tabs = soup.select('.stui-vodlist__head h4')
        playlists = soup.select('.stui-content__playlist')
        play_from = []
        play_url = []
        seen = set()
        for i, tab in enumerate(tabs):
            if i >= len(playlists):
                break
            name = tab.get_text(strip=True)
            name = re.sub(r'\s*\d+$', '', name).strip()
            if name in ['猜您喜欢', '同类型', '同主演', '同'] or name in seen:
                continue
            seen.add(name)
            eps = []
            for a in playlists[i].select('li a'):
                href = a.get('href')
                title = a.get_text(strip=True)
                if href and '1080P' not in title:
                    if not href.startswith('http'):
                        href = urljoin(xurl, href)
                    eps.append(f"{title}${href}")
            if eps:
                play_from.append(name)
                play_url.append('#'.join(eps))

        vod["vod_play_from"] = '$$$'.join(play_from)
        vod["vod_play_url"] = '$$$'.join(play_url)

        return {'list': [vod]}
        
    def searchContent(self, key, quick, page='1'):
        page = int(page) if page else 1
        url = f"{xurl}/search/{key}----------{page}---.html"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'lxml')
        return {
            'list': self._parse_video_items(soup),
            'page': page,
            'pagecount': page + 1,
            'limit': 90,
            'total': 9999
        }

    def playerContent(self, flag, id, vipFlags):
        try:
            play_url = id if id.startswith('http') else xurl + id
            resp = requests.get(play_url, headers=headers, timeout=10)
            html = resp.text

            pattern = r'var\s+player_\w+\s*=\s*(\{[\s\S]+?\});'
            match = re.search(pattern, html)
            video_url = ''

            if match:
                obj_str = match.group(1)
                obj_str = re.sub(r'(\w+):', r'"\1":', obj_str)
                try:
                    config = json.loads(obj_str)
                    video_url = config.get('url') or ''
                except json.JSONDecodeError:
                    pass

            if not video_url:
                url_match = re.search(r'"url":"([^"]+)"', html)
                if url_match:
                    video_url = url_match.group(1)

            if video_url and re.search(r'm3u8|mp4|mkv', video_url, re.I):
                parse = 0
                if not video_url.startswith('http'):
                    video_url = urljoin(xurl, video_url)
            else:
                parse = 1
                video_url = play_url

            return {"parse": parse, "playUrl": "", "url": video_url, "header": headers}
        except Exception as e:
            print(f"playerContent error: {e}")
            return {"parse": 1, "playUrl": "", "url": xurl + id, "header": headers}

    def localProxy(self, params):
        if params['type'] == "m3u8":
            return self.proxyM3u8(params)
        if params['type'] == "media":
            return self.proxyMedia(params)
        if params['type'] == "ts":
            return self.proxyTs(params)
        return None
