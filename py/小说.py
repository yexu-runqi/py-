"""
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  类型: '小说',
  title: '493D小说',
  lang: 'hipy',
})
"""

# -*- coding: utf-8 -*-
import sys
import re
import urllib.parse
import json
import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append('..')
from base.spider import Spider

class Spider(Spider):
    
    _categories_cache = []

    def getName(self):
        return "493D小说"

    def init(self, extend=""):
        self.host = "https://www.493d.com"

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        pass

    def getHeader(self):
        return {
            "User-Agent": "Mozilla/5.0 (Linux; Android 11; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
            "Referer": f"{self.host}/"
        }

    def homeContent(self, filter):
        if Spider._categories_cache:
            return {"class": Spider._categories_cache, "filters": {}}

        classes = [{"type_name": "总排行榜", "type_id": "top_allvisit"}]
        
        try:
            r = requests.get(f"{self.host}/xuanhuan/1.html", headers=self.getHeader(), timeout=5, verify=False)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')
            
            for a in soup.select('._tab a'):
                name = a.text.strip()
                if name and name != "首页":
                    href = a.get('href', '')
                    match = re.search(r'/([a-zA-Z0-9_]+)/', href)
                    if match:
                        tid = match.group(1)
                        if not any(c['type_id'] == tid for c in classes):
                            classes.append({"type_name": name, "type_id": tid})
                            
            if len(classes) > 1:
                Spider._categories_cache = classes
        except Exception:
            pass

        if len(classes) <= 1:
            classes = [
                {"type_name": "总排行榜", "type_id": "top_allvisit"},
                {"type_name": "玄幻奇幻", "type_id": "xuanhuan"},
                {"type_name": "武侠仙侠", "type_id": "wuxia"},
                {"type_name": "都市生活", "type_id": "dushi"},
                {"type_name": "历史军事", "type_id": "lishi"},
                {"type_name": "游戏竞技", "type_id": "youxi"},
                {"type_name": "科幻未来", "type_id": "kehuan"}
            ]
        
        return {"class": classes, "filters": {}}

    def homeVideoContent(self):
        return self.categoryContent("top_allvisit", "1", None, {})

    def categoryContent(self, tid, pg, filter, extend):
        url = f"{self.host}/{tid}/{pg}.html"
        
        try:
            r = requests.get(url, headers=self.getHeader(), timeout=10, verify=False)
            r.encoding = r.apparent_encoding
            
            if r.status_code != 200:
                return {"list": [{"vod_name": f"加载失败: HTTP {r.status_code}", "vod_id": "error", "vod_pic": ""}]}
                
            soup = BeautifulSoup(r.text, 'html.parser')
            videos = []
            
            items = soup.select('.g_row li')
            if not items:
                return {"list": [{"vod_name": "未找到小说列表(路径失效或被拦截)", "vod_id": "error", "vod_pic": ""}]}
                
            for book in items:
                a_tag = book.select_one('a')
                if not a_tag: continue
                
                vid = a_tag.get('href', '')
                if not vid.startswith('http'):
                    vid = urllib.parse.urljoin(self.host, vid)
                    
                name = a_tag.get('title') or a_tag.text.strip()
                if not name: name = "未知小说"
                
                img_tag = book.select_one('img')
                pic = ""
                if img_tag:
                    pic = img_tag.get('_src') or img_tag.get('src') or ""
                    if pic and not pic.startswith('http'):
                        pic = urllib.parse.urljoin(self.host, pic)
                        
                author_tag = book.select_one('span')
                author = author_tag.text.strip() if author_tag else ""
                
                videos.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": f"作者: {author}"
                })
            
            return {"list": videos, "page": pg, "pagecount": 9999, "limit": 20, "total": 999999}
        except Exception as e:
            return {"list": [{"vod_name": f"报错: {str(e)}", "vod_id": "error", "vod_pic": ""}]}

    def searchContent(self, key, quick, pg="1"):
        try:
            encoded_key = urllib.parse.quote(key)
            url = f"{self.host}/modules/article/search.php?searchkey={encoded_key}&searchtype=articlename&page={pg}"
            
            r = requests.get(url, headers=self.getHeader(), timeout=10, verify=False, allow_redirects=True)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')
            videos = []
            
            if '/book/' in r.url or 'info' in r.url or soup.select_one('.cover img'):
                img_tag = soup.select_one('.cover img')
                name = img_tag.get('alt') if img_tag else key
                pic = img_tag.get('src') if img_tag else ""
                if pic and not pic.startswith('http'):
                    pic = urllib.parse.urljoin(self.host, pic)
                    
                tags = soup.select('._tags span')
                author = tags[0].text.strip() if len(tags) > 0 else "未知"
                
                videos.append({
                    "vod_id": r.url, 
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": f"作者: {author}"
                })
                return {"list": videos, "page": pg}
            
            items = soup.select('.j_list_container li')
            for book in items:
                h3 = book.select_one('h3')
                if not h3: continue
                name = h3.text.strip()
                
                a_tag = book.select_one('a')
                vid = a_tag.get('href', '') if a_tag else ""
                if vid and not vid.startswith('http'):
                    vid = urllib.parse.urljoin(self.host, vid)
                    
                img_tag = book.select_one('img')
                pic = ""
                if img_tag:
                    pic = img_tag.get('_src') or img_tag.get('src') or ""
                    if pic and not pic.startswith('http'):
                        pic = urllib.parse.urljoin(self.host, pic)
                        
                remark_tag = book.select_one('.vam')
                remark = remark_tag.text.strip() if remark_tag else "小说"
                
                videos.append({
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "vod_remarks": remark
                })
            return {"list": videos, "page": pg}
        except Exception as e:
            return {"list": [{"vod_name": f"搜索异常: {str(e)}", "vod_id": "error", "vod_pic": ""}]}

    def detailContent(self, ids):
        vid = ids[0]
        if vid == "error": return {"list": []}
        
        try:
            r = requests.get(vid, headers=self.getHeader(), timeout=10, verify=False)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')
            
            img_tag = soup.select_one('.cover img')
            name = img_tag.get('alt') if img_tag else "未知书名"
            pic = img_tag.get('src') if img_tag else ""
            if pic and not pic.startswith('http'):
                pic = urllib.parse.urljoin(self.host, pic)
                
            tags = soup.select('._tags span')
            author = tags[0].text.strip() if len(tags) > 0 else ""
            type_name = tags[1].text.strip() if len(tags) > 1 else ""
            
            desc_tag = soup.select_one('.h112')
            desc = desc_tag.text.strip() if desc_tag else "暂无简介"
            
            chapters = []
            for li in soup.select('#chapterList li'):
                a_tag = li.select_one('a')
                if not a_tag: continue
                c_title = a_tag.text.strip()
                c_url = a_tag.get('href', '')
                if c_url and not c_url.startswith('http'):
                    c_url = urllib.parse.urljoin(vid, c_url)
                chapters.append(f"{c_title}${c_url}")
                
            return {
                "list": [{
                    "vod_id": vid,
                    "vod_name": name,
                    "vod_pic": pic,
                    "type_name": type_name,
                    "vod_actor": author,
                    "vod_remarks": type_name,
                    "vod_content": desc,
                    "vod_play_from": "全文阅读",
                    "vod_play_url": "#".join(chapters)
                }]
            }
        except Exception:
            return {"list": []}

    def playerContent(self, flag, id, vipFlags):
        try:
            r = requests.get(id, headers=self.getHeader(), timeout=10, verify=False)
            r.encoding = r.apparent_encoding
            soup = BeautifulSoup(r.text, 'html.parser')
            
            title_tag = soup.select_one('h1')
            title = title_tag.text.strip() if title_tag else "章节正文"
            
            content_tag = soup.select_one('#TextContent')
            if content_tag:
                for script in content_tag.select('script'):
                    script.decompose()
                    
                for br in content_tag.select('br'):
                    br.replace_with('\n')
                    
                content = content_tag.text
                
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                content = "\n\n　　".join(lines)
                if content:
                    content = "　　" + content
            else:
                content = "正文获取失败，内容可能为空或需要VIP。"

            result = {
                "title": title,
                "content": content
            }
            
            return {
                "parse": 0,
                "playUrl": "",
                "url": f"novel://{json.dumps(result, ensure_ascii=False)}",
                "header": ""
            }
        except Exception as e:
            return {"parse": 0, "playUrl": "", "url": "", "header": ""}

    def localProxy(self, param):
        pass

if __name__ == "__main__":
    spider = Spider()
    print(spider.getName())
