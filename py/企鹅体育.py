#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import math
import re

class Spider(Spider):
    def getName(self):
        return "企鹅体育"

    def init(self,extend=""):
        pass

    def isVideoFormat(self,url):
        pass

    def manualVideoCheck(self):
        pass

    def homeContent(self,filter):
        result = {}
        cateManual = {
            "全部": "",
            "足球": "Football",
            "篮球": "Basketball",
            "NBA": "NBA",
            "台球": "Billiards",
            "搏击": "Fight",
            "网排": "Tennis",
            "游戏": "Game",
            "其他": "Others",
            "橄棒冰": "MLB"
        }
        classes = []
        for k in cateManual:
            classes.append({
                'type_name': k,
                'type_id': cateManual[k]
            })

        result['class'] = classes
        if filter:
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        result = {}
        return result

    def categoryContent(self,tid,pg,filter,extend):
        result = {}
        url = 'https://live.qq.com/api/live/vlist?page_size=60&shortName={0}&page={1}'.format(tid, pg)
        rsp = self.fetch(url, headers=self.header)
        content = rsp.text
        jo = json.loads(content)
        videos = []
        vodList = jo['data']['result']
        numvL = len(vodList)
        pgc = math.ceil(numvL/15)
        for vod in vodList:
            aid = vod['room_id']
            title = vod['room_name'].strip()
            img = vod['room_src']
            remark = vod['game_name'].strip()
            videos.append({
                "vod_id": aid,
                "vod_name": title,
                "vod_pic": img,
                "vod_remarks": remark
            })
        result['list'] = videos
        result['page'] = pg
        result['pagecount'] = pgc
        result['limit'] = numvL
        result['total'] = numvL
        return result

    def detailContent(self,array):
        aid = array[0]
        url = "https://m.live.qq.com/{0}".format(aid)
        rsp = self.fetch(url, headers=self.header)
        html = self.cleanText(rsp.text)

        if self.regStr(reg=r'\"show_status\":\"(\d)\"', src=html) == '1':
            title = self.regStr(reg=r'\"room_name\":\"(.*?)\"', src=html)
            pic = self.regStr(reg=r'\"room_src\":\"(.*?)\"', src=html)
            typeName = self.regStr(reg=r'\"game_name\":\"(.*?)\"', src=html)
            remark = self.regStr(reg=r'\"nickname\":\"(.*?)\"', src=html)
        else:
            return {}

        vod = {
            "vod_id": aid,
            "vod_name": title,
            "vod_pic": pic,
            "type_name": typeName,
            "vod_year": "",
            "vod_area": "",
            "vod_remarks": remark,
            "vod_actor": '',
            "vod_director":'',
            "vod_content": ''
        }

        # 只传房间ID，不在详情页拿过期流
        playUrl = '{0}${1}#'.format(typeName, aid)
        vod['vod_play_from'] = '企鹅体育'
        vod['vod_play_url'] = playUrl

        result = {
            'list': [vod]
        }
        return result

    def searchContent(self,key,quick):
        return {}

    def playerContent(self,flag,id,vipFlags):
        result = {}
        # 每次播放时，实时获取最新直播流（解决2分钟过期卡顿）
        room_id = id
        url = f"https://m.live.qq.com/{room_id}"
        rsp = self.fetch(url, headers=self.header)
        html = self.cleanText(rsp.text)

        # 提取最新hls地址
        purl = self.regStr(r'\"hls_url\":\"(.*?)\"', html)
        if not purl:
            purl = self.regStr(r'url\":\"(.*?m3u8)\"', html)

        header = {
            'Referer': 'https://m.live.qq.com/',
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148'
        }

        result["parse"] = 1
        result["playUrl"] = ""
        result["url"] = purl
        result["header"] = header
        return result

    config = {
        "player": {},
        "filter": {}
    }

    header = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
        "Referer": "https://m.live.qq.com/",
        "Origin": "https://m.live.qq.com"
    }

    def localProxy(self,param):
        action = {
            'url':'',
            'header':'',
            'param':'',
            'type':'string',
            'after':''
        }
        return [200, "video/MP2T", action, ""]
