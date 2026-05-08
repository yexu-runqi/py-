# -*- coding: utf-8 -*-
# 本资源来源于互联网公开渠道，仅可用于个人学习爬虫技术。
# 严禁将其用于任何商业用途，下载后请于 24 小时内删除，搜索结果均来自源站，本人不承担任何责任。

import re,sys,json,urllib3
from base.spider import Spider
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.path.append('..')

class Spider(Spider):
    def_headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    
    host = 'https://www.budaichuchen.net'
    parser_base = 'https://zzrs.mfdyvip.com'
    parser_referer = 'https://www.budaichuchen.net/'
    
    # 自营线路过滤列表
    self_operated = ['自营t', '自营y', '自营r']

    def homeContent(self, filter):
        return {'class':[
            {'type_id':'1','type_name':'电影'},
            {'type_id':'2','type_name':'电视剧'},
            {'type_id':'3','type_name':'综艺'},
            {'type_id':'4','type_name':'动漫'},
        ]}

    def homeVideoContent(self):
        return self.categoryContent('1', 1, {}, {})

    def categoryContent(self, tid, pg, filter, extend):
        url = f'{self.host}/type/{tid}-{pg}.html'
        if not tid:
            url = f'{self.host}/'
        
        try:
            response = self.fetch(url, headers=self.def_headers, verify=False)
            html = response.text
            videos = self._extractList(html)
            hasNext = f'-{int(pg)+1}.html' in html or f'/{int(pg)+1}' in html
            pagecount = int(pg) + 1 if hasNext else int(pg)
            return {'list': videos, 'pagecount': pagecount, 'page': int(pg)}
        except Exception as e:
            return {'list': [], 'pagecount': 1, 'page': int(pg)}

    def searchContent(self, key, quick, pg='1'):
        if str(pg) != '1':
            return None
        
        url = f'{self.host}/index.php/ajax/suggest'
        params = {'mid': '1', 'wd': key, 'limit': '30'}
        
        try:
            response = self.fetch(url, params=params, headers=self.def_headers, verify=False)
            data = json.loads(response.text)
            videos = []
            for item in data.get('list', []):
                videos.append({
                    'vod_id': str(item.get('id')),
                    'vod_name': item.get('name'),
                    'vod_pic': item.get('pic', ''),
                    'vod_remarks': '',
                })
            return {'list': videos, 'page': pg}
        except Exception as e:
            return {'list': [], 'page': pg}

    def detailContent(self, ids):
        vod_id = ids[0]
        
        try:
            url = f'{self.host}/detail/{vod_id}.html'
            response = self.fetch(url, headers=self.def_headers, verify=False)
            html = response.text
            
            # 提取基本信息
            vod_name = ''
            name_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
            if name_match:
                vod_name = re.sub(r'<[^>]+>', '', name_match.group(1)).strip()
            
            vod_pic = ''
            pic_match = re.search(r'<img[^>]*src="([^"]+)"[^>]*class="[^"]*(?:pic|img|poster)[^"]*"', html, re.S)
            if pic_match:
                vod_pic = pic_match.group(1)
            
            # 提取简介 - 优先从meta description
            vod_content = ''
            meta_match = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', html)
            if meta_match:
                vod_content = meta_match.group(1)
                # 清理前缀
                vod_content = re.sub(r'\[.*?\],?', '', vod_content).strip()
                # 提取"剧情介绍："之后的内容
                if '剧情介绍：' in vod_content:
                    vod_content = vod_content.split('剧情介绍：', 1)[1].strip()
            
            # 如果还是获取不到，固定为思牧影视
            if not vod_content:
                vod_content = '思牧影视'
            
            # 加上前缀
            vod_content = '【by：轻狂书生】\n' + vod_content
            
            # 提取线路名称和播放列表
            lines = {}
            
            # 匹配线路名称
            line_matches = re.findall(r'<a class="swiper-slide"[^>]*>[\s\S]*?&nbsp;([^<]+)<span class="badge">', html)
            
            # 匹配播放链接
            all_play_matches = re.findall(r'href="/play/(\d+)-(\d+)-(\d+)\.html"[^>]*>(.*?)</a>', html)
            
            # 按线路号分组
            line_groups = {}
            for vid, line_num, ep, name in all_play_matches:
                if line_num not in line_groups:
                    line_groups[line_num] = []
                clean_name = re.sub(r'<[^>]+>', '', name).strip()
                line_groups[line_num].append(f'{clean_name}${vid}-{line_num}-{ep}')
            
            # 构建线路名称和播放列表（过滤自营）
            play_from = []
            play_url = []
            
            for i, line_name in enumerate(line_matches):
                line_name = line_name.strip()
                # 过滤自营线路
                if line_name in self.self_operated:
                    continue
                
                line_num = str(i + 1)
                if line_num in line_groups and line_groups[line_num]:
                    play_from.append(line_name)
                    play_url.append('#'.join(line_groups[line_num]))
            
            video = {
                'vod_id': vod_id,
                'vod_name': vod_name,
                'vod_pic': vod_pic,
                'vod_content': vod_content,
                'vod_play_from': '$$$'.join(play_from) if play_from else '',
                'vod_play_url': '$$$'.join(play_url) if play_url else '',
            }
            
            return {'list': [video]}
        except Exception as e:
            return {'list': []}

    def playerContent(self, flag, vid, vip_flags):
        # vid 格式: vod_id-line-ep
        jx = 0
        url = ''
        
        try:
            # 获取播放页
            play_url = f'{self.host}/play/{vid}.html'
            response = self.fetch(play_url, headers=self.def_headers, verify=False)
            html = response.text
            
            # 提取 player_aaaa - 注意JSON后面有</script>，需要截断
            player_match = re.search(r'player_aaaa\s*=\s*({.+?})</script>', html, re.S)
            if not player_match:
                # 尝试不带</script>的匹配
                player_match = re.search(r'player_aaaa\s*=\s*({.+?});', html, re.S)
            
            if player_match:
                # 清理JSON字符串，确保能解析
                json_str = player_match.group(1)
                # 移除尾部可能的HTML标签
                json_str = re.sub(r'<[^>]+>$', '', json_str).strip()
                
                try:
                    player_data = json.loads(json_str)
                    video_url = player_data.get('url', '')
                    
                    if video_url:
                        # 解码Unicode转义
                        video_url = video_url.encode('utf-8').decode('unicode_escape') if '\\u' in video_url else video_url
                        
                        # 直接是m3u8或mp4
                        if '.m3u8' in video_url or '.mp4' in video_url:
                            url = video_url
                            jx = 0
                        # 如果是VIP平台链接，需要解析
                        elif re.search(r'(?:www\.iqiyi|v\.qq|v\.youku|www\.mgtv|www\.bilibili)\.com', video_url):
                            parsed = self._parse_video(video_url)
                            if parsed:
                                url = parsed
                                jx = 0
                            else:
                                url = video_url
                                jx = 1
                        else:
                            url = video_url
                            jx = 0
                except json.JSONDecodeError as je:
                    # JSON解析失败，尝试直接提取url字段
                    url_match = re.search(r'"url"\s*:\s*"([^"]+)"', json_str)
                    if url_match:
                        url = url_match.group(1).encode('utf-8').decode('unicode_escape') if '\\u' in url_match.group(1) else url_match.group(1)
                        jx = 0 if '.m3u8' in url or '.mp4' in url else 1
            
            if not url:
                url = vid
                jx = 1
                
        except Exception as e:
            url = vid
            jx = 1
        
        return {
            'jx': jx,
            'parse': 0,
            'url': url,
            'header': {
                **self.def_headers,
                'Referer': self.host + '/',
            }
        }

    def _parse_video(self, video_url):
        """调用解析接口获取真实播放地址"""
        try:
            # 第1步：获取token
            player_page = f'{self.parser_base}/player/?url={video_url}'
            headers = {
                **self.def_headers,
                'Referer': self.parser_referer,
            }
            
            response = self.fetch(player_page, headers=headers, verify=False)
            html = response.text
            
            # 提取token
            token_match = re.search(r'data-te="([^"]+)"', html)
            if not token_match:
                return None
            token = token_match.group(1)
            
            # 第2步：获取真实地址
            api_url = f'{self.parser_base}/player/mplayer.php'
            post_data = f'url={video_url}&token={token}'
            
            post_headers = {
                **self.def_headers,
                'Referer': self.parser_referer,
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Requested-With': 'XMLHttpRequest',
            }
            
            response = self.post(api_url, data=post_data, headers=post_headers, verify=False)
            data = json.loads(response.text)
            
            if data.get('code') == 200:
                return data.get('url')
            
            return None
        except Exception as e:
            return None

    def _extractList(self, html):
        """从HTML提取视频列表"""
        videos = []
        
        # 匹配详情链接和图片（支持data-src懒加载）
        # 先找到每个视频块
        blocks = re.findall(
            r'<a[^>]*href="/detail/(\d+)\.html"[^>]*>([\s\S]*?)</a>',
            html, re.S
        )
        
        for vid, block in blocks:
            # 在块内找图片
            pic_match = re.search(r'data-src="([^"]+)"', block) or re.search(r'src="([^"]+)"', block)
            pic = pic_match.group(1) if pic_match else ''
            
            # 解码HTML实体 &amp; -> &
            pic = pic.replace('&amp;', '&')
            
            # 在块内找标题
            title_match = re.search(r'alt="([^"]*)"', block) or re.search(r'title="([^"]*)"', block)
            title = title_match.group(1) if title_match else ''
            
            # 过滤掉无效条目（没有图片或标题的）
            if not pic or not title:
                continue
            
            # 过滤掉占位图（图片URL包含特定关键词）
            if 'data:image' in pic or pic.startswith('//'):
                continue
            
            # 去重检查
            if not any(v['vod_id'] == vid for v in videos):
                videos.append({
                    'vod_id': vid,
                    'vod_name': title,
                    'vod_pic': pic,
                    'vod_remarks': '',
                })
        
        return videos

    def init(self, extend=''):
        pass

    def getName(self):
        return '枫叶4K'

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def localProxy(self, param):
        pass
