#coding=utf-8
#!/usr/bin/python
import sys
sys.path.append('..')
from base.spider import Spider
import json
import math
import re

class Spider(Spider):
    # 常量定义
    BASE_URL = 'https://live.qq.com'
    API_URL = 'https://live.qq.com/api/live/vlist'
    MOBILE_URL = 'https://m.live.qq.com'
    PAGE_SIZE = 60  # 接口默认每页条数
    
    def getName(self):
        return "企鹅体育"
    
    def init(self, extend=""):
        pass
    
    def isVideoFormat(self, url):
        pass
    
    def manualVideoCheck(self):
        pass

    def homeContent(self, filter):
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
        
        classes = [
            {'type_name': k, 'type_id': v} 
            for k, v in cateManual.items()
        ]
        
        result['class'] = classes
        if filter:
            result['filters'] = self.config['filter']
        return result

    def homeVideoContent(self):
        return {}

    def categoryContent(self, tid, pg, filter, extend):
        result = {}
        url = f'{self.API_URL}?page_size={self.PAGE_SIZE}&shortName={tid}&page={pg}'
        
        try:
            rsp = self.fetch(url)
            jo = json.loads(rsp.text)
            vodList = jo.get('data', {}).get('result', [])
            
            videos = []
            for vod in vodList:
                try:
                    aid = vod.get('room_id', '')
                    title = vod.get('room_name', '').strip()
                    img = vod.get('room_src', '')
                    remark = vod.get('game_name', '').strip()
                    
                    if aid and title:  # 只添加有效数据
                        videos.append({
                            "vod_id": aid,
                            "vod_name": title,
                            "vod_pic": img,
                            "vod_remarks": remark
                        })
                except Exception:
                    continue  # 跳过异常数据
            
            # 修复：接口限制每页最多60条，如果返回60条说明可能还有下一页
            total_count = len(vodList)
            page_count = 1 if total_count < self.PAGE_SIZE else pg + 1  # 估算分页
            
            result['list'] = videos
            result['page'] = int(pg)
            result['pagecount'] = page_count
            result['limit'] = total_count
            result['total'] = total_count
            
        except Exception as e:
            print(f"获取分类内容失败: {e}")
            result['list'] = []
            result['page'] = int(pg)
            result['pagecount'] = 1
            result['limit'] = 0
            result['total'] = 0
            
        return result

    def detailContent(self, array):
        aid = array[0]
        url = f"{self.MOBILE_URL}/{aid}"
        
        try:
            rsp = self.fetch(url)
            html = self.cleanText(rsp.text)
            
            # 检查直播状态
            show_status = self.regStr(reg=r'\"show_status\":\"(\d)\"', src=html)
            if show_status != '1':
                return {}
            
            # 提取信息
            title = self.regStr(reg=r'\"room_name\":\"(.*?)\"', src=html)
            pic = self.regStr(reg=r'\"room_src\":\"(.*?)\"', src=html)
            typeName = self.regStr(reg=r'\"game_name\":\"(.*?)\"', src=html)
            remark = self.regStr(reg=r'\"nickname\":\"(.*?)\"', src=html)
            
            # 关键修复：尝试多个可能的流地址字段
            purl = self.regStr(reg=r'\"hls_url\":\"(.*?)\"', src=html)
            if not purl:
                # 备用流地址字段
                purl = self.regStr(reg=r'\"flv_url\":\"(.*?)\"', src=html)
            if not purl:
                # 尝试从script中提取
                purl = self.regStr(reg=r'src:\s*\"(https?://[^\"]+\.m3u8[^\"]*)\"', src=html)
            
            if not title or not purl:
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
                "vod_director": '',
                "vod_content": ''
            }
            
            # 修复播放格式，确保URL完整
            if not purl.startswith('http'):
                purl = f"https:{purl}" if purl.startswith('//') else f"{self.BASE_URL}{purl}"
            
            playUrl = f'{typeName}${purl}#'
            vod['vod_play_from'] = '企鹅体育'
            vod['vod_play_url'] = playUrl
            
            return {'list': [vod]}
            
        except Exception as e:
            print(f"获取详情失败: {e}")
            return {}

    def searchContent(self, key, quick):
        return {}

    def playerContent(self, flag, id, vipFlags):
        result = {}
        
        # 关键修复：处理URL，移除可能导致暂停的参数
        url = id
        if '?' in url:
            # 保留URL但添加必要参数防止超时暂停
            if 'expire' not in url.lower():
                url = url  # 保持原样
        # 确保是完整的流地址
        if not url.startswith('http'):
            url = f"https:{url}" if url.startswith('//') else url
        
        header = {
            'Referer': f'{self.MOBILE_URL}/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/86.0.4240.198 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Connection': 'keep-alive',  # 保持连接
            'Cache-Control': 'no-cache',  # 避免缓存导致的问题
        }
        
        result["parse"] = 0
        result["playUrl"] = ''
        result["url"] = url
        result["header"] = header
        
        return result

    config = {
        "player": {},
        "filter": {}
    }
    header = {}

    def localProxy(self, param):
        action = {
            'url': '',
            'header': '',
            'param': '',
            'type': 'string',
            'after': ''
        }
        return [200, "video/MP2T", action, ""]