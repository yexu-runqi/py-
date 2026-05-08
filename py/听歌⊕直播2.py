# 音乐+在线直播
import sys
import re
import json
import os
import base64
import hashlib
import time
import urllib.parse
import random
import threading
from pathlib import Path
from base.spider import Spider

# ==================== 在线直播配置（默认配置） ====================
# 已删除默认配置，改为从外部JSON文件和lives目录加载

# 默认直播源配置文件路径
LIVE_CONFIG_PATH = "/storage/emulated/0/VodPlus/wwwroot/直播文件/live_config.json"

# 直播源文件目录（存放m3u/txt等直播源文件）
LIVE_FILES_DIR = "/storage/emulated/0/VodPlus/wwwroot/直播文件"

LIVE_CATEGORY_ID = "online_live"
LIVE_CATEGORY_NAME = "📡 在线直播"
LIVE_CACHE_DURATION = 600
LIVE_SOURCES_CACHE_DURATION = 3600

# ==================== 全局请求头自动适配配置 ====================
COMMON_HEADERS_LIST = [
    {
        "name": "Chrome浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "Firefox浏览器",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.8,en-US;q=0.5,en;q=0.3",
            "Connection": "keep-alive"
        }
    },
    {
        "name": "okhttp/3",
        "headers": {
            "User-Agent": "okhttp/3.12.11",
            "Accept": "*/*",
            "Connection": "Keep-Alive"
        }
    }
]

DOMAIN_SPECIFIC_HEADERS = {
    "gongdian.top": [
        {
            "name": "宫殿直播专用",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
                "Referer": "https://gongdian.top/",
                "Connection": "keep-alive"
            }
        }
    ],
    "t.061899.xyz": [
        {
            "name": "t源专用",
            "headers": {
                "User-Agent": "okhttp/3.12.11",
                "Referer": "http://t.061899.xyz/",
                "Accept": "*/*"
            }
        }
    ],
    "rihou.cc": [
        {
            "name": "日后源专用-Chrome",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://rihou.cc:555/",
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            }
        }
    ]
}

# ==================== 音乐路径配置 ====================
MUSIC_PATHS = [
    '/storage/emulated/0/Music/',
    '//storage/emulated/0/Android/data/cn.kuwo.player/files/KuwoMusic/music/',
]

# 递归扫描的最大深度
MAX_SCAN_DEPTH = 10

print("ℹ️ 本地资源管理加载成功 - 音乐+在线直播精简版")

# ==================== 直播源加载函数（带缓存和全局去重） ====================
_live_sources_cache = None
_live_sources_cache_time = 0

def normalize_url_for_dedup(url):
    """标准化URL用于去重比较"""
    if not url:
        return ""
    url_lower = url.lower().strip()
    # 移除 file:// 前缀
    if url_lower.startswith('file://'):
        url_lower = url_lower[7:]
    # 移除 http:// 和 https://
    if url_lower.startswith('http://'):
        url_lower = url_lower[7:]
    elif url_lower.startswith('https://'):
        url_lower = url_lower[8:]
    # 移除末尾的斜杠
    url_lower = url_lower.rstrip('/')
    # 移除 www. 前缀
    if url_lower.startswith('www.'):
        url_lower = url_lower[4:]
    # 移除查询参数
    if '?' in url_lower:
        url_lower = url_lower.split('?')[0]
    return url_lower

def is_url_duplicate(url, existing_urls):
    """检查URL是否重复"""
    if not url:
        return False
    normalized = normalize_url_for_dedup(url)
    for exist_url in existing_urls:
        if normalized == normalize_url_for_dedup(exist_url):
            return True
    return False

def load_live_sources():
    """加载直播源配置（从默认JSON配置文件 + lives目录下的文件），带全局去重"""
    global _live_sources_cache, _live_sources_cache_time
    
    current_time = time.time()
    if _live_sources_cache is not None and current_time - _live_sources_cache_time < LIVE_SOURCES_CACHE_DURATION:
        print(f"ℹ️ 使用缓存的直播源配置，共 {len(_live_sources_cache)} 个源")
        return _live_sources_cache
    
    sources = []
    seen_urls = set()      # 用于URL去重
    seen_names = set()     # 用于名称去重
    seen_ids = set()       # 用于ID去重
    duplicate_count = 0
    
    # ==================== 1. 加载JSON配置文件 ====================
    if os.path.exists(LIVE_CONFIG_PATH):
        try:
            with open(LIVE_CONFIG_PATH, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            external_sources = []
            if isinstance(config, list):
                external_sources = config
            elif isinstance(config, dict) and 'lives' in config and isinstance(config['lives'], list):
                external_sources = config['lives']
            elif isinstance(config, dict) and 'live' in config and isinstance(config['live'], list):
                external_sources = config['live']
            elif isinstance(config, dict) and 'sources' in config and isinstance(config['sources'], list):
                external_sources = config['sources']
            
            json_count = 0
            for ext_src in external_sources:
                if not isinstance(ext_src, dict):
                    continue
                
                # 跳过没有URL的源
                if not ext_src.get('url'):
                    print(f"⚠️ 跳过无效直播源（无URL）: {ext_src.get('name', '未知')}")
                    continue
                
                src_id = ext_src.get('id')
                if not src_id and ext_src.get('name'):
                    src_id = ext_src['name'].lower().replace(' ', '_').replace('(', '').replace(')', '').replace('，', '')
                
                src_url = ext_src.get('url', '')
                src_name = ext_src.get('name', '未知源')
                
                # 全局去重检查
                is_dup = False
                dup_reason = ""
                
                # 检查ID重复
                if src_id and src_id in seen_ids:
                    is_dup = True
                    dup_reason = f"ID重复: {src_id}"
                
                # 检查URL重复
                if not is_dup and is_url_duplicate(src_url, seen_urls):
                    is_dup = True
                    dup_reason = f"URL重复: {src_url}"
                
                # 检查名称重复
                if not is_dup and src_name in seen_names:
                    is_dup = True
                    dup_reason = f"名称重复: {src_name}"
                
                if is_dup:
                    duplicate_count += 1
                    print(f"⚠️ 跳过重复直播源 (JSON): {src_name} - {dup_reason}")
                    continue
                
                converted = {
                    'id': src_id or f"json_{json_count}",
                    'name': src_name,
                    'url': src_url,
                    'color': ext_src.get('color', '#9D65C9'),
                    'remarks': ext_src.get('remarks', '默认直播源'),
                    'type': ext_src.get('type', 'm3u'),
                    'ua': ext_src.get('ua', ''),
                    'playerType': ext_src.get('playerType', 2)
                }
                
                sources.append(converted)
                if src_id:
                    seen_ids.add(src_id)
                seen_urls.add(src_url)
                seen_names.add(src_name)
                json_count += 1
                print(f"➕ 添加JSON直播源: {converted['name']}")
            
            print(f"✅ 从JSON加载直播源完成，共 {json_count} 个源")
            
        except Exception as e:
            print(f"⚠️ 加载默认直播源配置失败: {e}")
    else:
        print(f"ℹ️ 未找到默认直播源配置文件: {LIVE_CONFIG_PATH}")
    
    # ==================== 2. 扫描lives目录下的直播源文件 ====================
    if os.path.exists(LIVE_FILES_DIR) and os.path.isdir(LIVE_FILES_DIR):
        try:
            supported_exts = ('.m3u', '.m3u8', '.txt')
            file_count = 0
            
            for filename in os.listdir(LIVE_FILES_DIR):
                if filename.startswith('.'):
                    continue
                
                file_path = os.path.join(LIVE_FILES_DIR, filename)
                if not os.path.isfile(file_path):
                    continue
                
                # 检查文件扩展名
                ext = os.path.splitext(filename)[1].lower()
                if ext not in supported_exts:
                    continue
                
                # 确定直播源类型
                if ext in ('.m3u', '.m3u8'):
                    src_type = 'm3u'
                else:
                    src_type = 'txt'
                
                # 生成源ID和名称
                base_name = os.path.splitext(filename)[0]
                src_id = f"file_{base_name}"
                src_name = f"📁 {base_name}"
                src_url = f"file://{file_path}"
                
                # 全局去重检查
                is_dup = False
                dup_reason = ""
                
                # 检查ID重复
                if src_id in seen_ids:
                    is_dup = True
                    dup_reason = f"ID重复: {src_id}"
                
                # 检查URL重复
                if not is_dup and is_url_duplicate(src_url, seen_urls):
                    is_dup = True
                    dup_reason = f"URL重复: {src_url}"
                
                # 检查名称重复
                if not is_dup and src_name in seen_names:
                    is_dup = True
                    dup_reason = f"名称重复: {src_name}"
                
                if is_dup:
                    duplicate_count += 1
                    print(f"⚠️ 跳过重复直播源 (文件): {src_name} - {dup_reason}")
                    continue
                
                # 读取文件第一行作为备注
                remarks = f"本地文件: {filename}"
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        first_line = f.readline().strip()
                        if first_line and len(first_line) < 50:
                            remarks = first_line[:40]
                except:
                    pass
                
                converted = {
                    'id': src_id,
                    'name': src_name,
                    'url': src_url,
                    'color': '#4ECDC4',
                    'remarks': remarks,
                    'type': src_type,
                    'ua': '',
                    'playerType': 2
                }
                
                sources.append(converted)
                seen_ids.add(src_id)
                seen_urls.add(src_url)
                seen_names.add(src_name)
                file_count += 1
                print(f"➕ 添加本地文件直播源: {converted['name']} ({filename})")
            
            print(f"✅ 从lives目录加载直播源完成，共 {file_count} 个文件")
            
        except Exception as e:
            print(f"⚠️ 扫描lives目录失败: {e}")
    else:
        print(f"ℹ️ 直播源目录不存在，正在创建: {LIVE_FILES_DIR}")
        try:
            os.makedirs(LIVE_FILES_DIR, exist_ok=True)
            print(f"✅ 已创建直播源目录: {LIVE_FILES_DIR}")
        except Exception as e:
            print(f"⚠️ 创建直播源目录失败: {e}")
    
    # ==================== 去重统计 ====================
    print(f"\n📊 直播源加载统计:")
    print(f"   - 最终加载: {len(sources)} 个直播源")
    if duplicate_count > 0:
        print(f"   - 已去重跳过: {duplicate_count} 个重复源")
    
    # 如果没有加载到任何源，添加一个提示源
    if not sources:
        sources.append({
            'id': 'no_source',
            'name': '⚠️ 无直播源',
            'url': '',
            'color': '#FF6B6B',
            'remarks': '请将直播源文件放入lives目录或配置live_config.json',
            'type': 'm3u',
            'ua': '',
            'playerType': 2
        })
        print(f"⚠️ 没有加载到任何直播源，请检查配置")
    
    _live_sources_cache = sources
    _live_sources_cache_time = current_time
    return sources


# ==================== 主爬虫类 ====================
class Spider(Spider):
    def getName(self):
        return "本地资源管理"
    
    def init(self, extend=""):
        super().init(extend)
        self.music_paths = MUSIC_PATHS
        self.max_scan_depth = MAX_SCAN_DEPTH
        
        # 加载在线直播配置
        self.online_live_sources = load_live_sources()
        self.live_category_id = LIVE_CATEGORY_ID
        self.live_category_name = LIVE_CATEGORY_NAME
        self.live_cache = {}
        self.live_cache_time = {}
        self.live_cache_duration = LIVE_CACHE_DURATION
        self.live_detail_cache = {}
        self.live_detail_cache_time = {}
        
        self.common_headers_list = COMMON_HEADERS_LIST
        self.domain_specific_headers = DOMAIN_SPECIFIC_HEADERS
        
        self.default_colors = ["#FF6B6B", "#4ECDC4", "#FFD93D", "#6BCB77", "#9D65C9"]
        
        # 音乐相关配置
        self.audio_exts = ['mp3', 'm4a', 'aac', 'flac', 'wav', 'ogg', 'wma', 'ape']
        self.lrc_exts = ['lrc', 'krc', 'qrc', 'yrc', 'trc']
        
        self.max_audio_per_scan = 5000
        self.audio_scan_timeout = 10
        self.enable_online_lyrics = True
        self.enable_online_poster = True
        self.audio_cache_duration = 3600
        
        # 缓存
        self.audio_list_cache = {}
        self.audio_list_cache_time = {}
        self.network_lyrics_cache = {}
        self.network_cover_cache = {}
        self.song_info_cache = {}
        self.scan_cache = {}
        self.scan_cache_time = {}
        self.scan_cache_duration = 30
        self.all_music_cache = []
        self.all_music_cache_time = 0
        self.all_music_cache_duration = 300
        
        self.debug_mode = True
        
        # 文件图标
        self.file_icons = {
            'folder': 'https://img.icons8.com/color/96/000000/folder-invoices.png',
            'audio': 'https://img.icons8.com/color/96/000000/audio-file.png',
            'audio_playlist': 'https://img.icons8.com/color/96/000000/musical-notes.png',
            'lrc': 'https://img.icons8.com/color/96/000000/audio-file.png',
            'music_note': 'https://img.icons8.com/color/96/musical-notes.png',
            'cd': 'https://img.icons8.com/color/96/compact-disc.png',
            'song': 'https://img.icons8.com/color/96/song.png',
        }
        
        self.TRANSPARENT_GIF = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7'
        
        self.MP3_PREFIX = 'mp3://'
        self.A_ALL_PREFIX = 'aall://'
        self.LIVE_PREFIX = 'live://'
        self.FOLDER_PREFIX = 'folder://'
        self.ALL_MUSIC_PREFIX = 'allmusic://'
        
        self.lrc_cache = {}
        
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session = requests.Session()
        retries = Retry(total=2, backoff_factor=0.5)
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        # 后台预加载所有音乐
        self._preload_all_music()
    
    def _preload_all_music(self):
        """后台预加载所有音乐"""
        def preload():
            self._scan_all_music_recursive()
        threading.Thread(target=preload, daemon=True).start()
    
    def log(self, msg):
        if self.debug_mode:
            print(f"🔍 [DEBUG] {msg}")
    
    # ==================== 工具函数 ====================
    
    def b64u_encode(self, data):
        if isinstance(data, str):
            data = data.encode('utf-8')
        encoded = base64.b64encode(data).decode('ascii')
        return encoded.replace('+', '-').replace('/', '_').rstrip('=')
    
    def b64u_decode(self, data):
        data = data.replace('-', '+').replace('_', '/')
        pad = len(data) % 4
        if pad:
            data += '=' * (4 - pad)
        try:
            return base64.b64decode(data).decode('utf-8')
        except:
            return ''
    
    def get_file_ext(self, filename):
        idx = filename.rfind('.')
        if idx == -1:
            return ''
        return filename[idx + 1:].lower()
    
    def is_audio_file(self, ext):
        return ext in self.audio_exts
    
    def is_lrc_file(self, ext):
        return ext in self.lrc_exts
    
    def is_playable_url(self, url):
        u = str(url).lower().strip()
        if not u:
            return False
        protocols = ['http://', 'https://', 'file://', 'mp3://']
        if any(u.startswith(p) for p in protocols):
            return True
        exts = ['.mp3', '.m4a', '.aac', '.flac', '.wav', '.m3u8', '.ts']
        return any(ext in u for ext in exts)
    
    # ==================== 递归扫描音乐 ====================
    
    def _scan_all_music_recursive(self):
        """递归扫描所有音乐目录，获取全部音乐文件"""
        current_time = time.time()
        
        if self.all_music_cache and current_time - self.all_music_cache_time < self.all_music_cache_duration:
            return self.all_music_cache
        
        all_audios = []
        for path in self.music_paths:
            if os.path.exists(path):
                self.log(f"递归扫描音乐目录: {path}")
                self._collect_audios_recursive(path, all_audios, depth=0)
        
        seen = set()
        unique_audios = []
        for audio in all_audios:
            if audio['path'] not in seen:
                seen.add(audio['path'])
                unique_audios.append(audio)
        
        unique_audios.sort(key=lambda x: x['name'])
        self.all_music_cache = unique_audios
        self.all_music_cache_time = current_time
        self.log(f"递归扫描完成，共找到 {len(unique_audios)} 首音乐")
        return unique_audios
    
    def _collect_audios_recursive(self, dir_path, audios, depth=0):
        """递归收集目录下的所有音频文件"""
        if depth > self.max_scan_depth:
            return
        
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                return
            
            start_time = time.time()
            try:
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        if time.time() - start_time > self.audio_scan_timeout:
                            return
                        
                        if entry.name.startswith('.'):
                            continue
                        
                        if entry.is_dir(follow_symlinks=False):
                            self._collect_audios_recursive(entry.path, audios, depth + 1)
                        else:
                            ext = self.get_file_ext(entry.name)
                            if ext in self.audio_exts:
                                try:
                                    stat = entry.stat()
                                    if os.access(entry.path, os.R_OK):
                                        audios.append({
                                            'name': entry.name,
                                            'path': entry.path,
                                            'ext': ext,
                                            'mtime': stat.st_mtime,
                                            'dir': dir_path
                                        })
                                except:
                                    pass
            except Exception as e:
                self.log(f"扫描异常 {dir_path}: {e}")
        except Exception as e:
            self.log(f"_collect_audios_recursive错误: {e}")
    
    def scan_music_directory(self, dir_path):
        """扫描单个目录"""
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                return []
            
            cache_key = f"music_scan_{dir_path}"
            current_time = time.time()
            if cache_key in self.scan_cache and current_time - self.scan_cache_time.get(cache_key, 0) < self.scan_cache_duration:
                return self.scan_cache[cache_key]
            
            files = []
            try:
                with os.scandir(dir_path) as entries:
                    for entry in entries:
                        if entry.name.startswith('.'):
                            continue
                        
                        if entry.is_dir(follow_symlinks=False):
                            files.append({
                                'name': entry.name,
                                'path': entry.path,
                                'is_dir': True,
                                'ext': ''
                            })
                        else:
                            ext = self.get_file_ext(entry.name)
                            if ext in self.audio_exts or ext in self.lrc_exts:
                                try:
                                    stat = entry.stat()
                                    files.append({
                                        'name': entry.name,
                                        'path': entry.path,
                                        'is_dir': False,
                                        'ext': ext,
                                        'mtime': stat.st_mtime
                                    })
                                except:
                                    pass
            except Exception as e:
                self.log(f"扫描异常: {e}")
                return []
            
            files.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
            
            self.scan_cache[cache_key] = files
            self.scan_cache_time[cache_key] = current_time
            
            return files
        except Exception as e:
            self.log(f"scan_music_directory错误: {e}")
            return []
    
    def collect_audios_in_dir(self, dir_path, recursive=True):
        """收集目录下的音频文件"""
        if recursive:
            audios = []
            self._collect_audios_recursive(dir_path, audios, depth=0)
            return audios
        else:
            try:
                if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                    return []
                
                current_time = time.time()
                if dir_path in self.audio_list_cache:
                    cache_time = self.audio_list_cache_time.get(dir_path, 0)
                    if current_time - cache_time < self.audio_cache_duration:
                        return self.audio_list_cache[dir_path]
                
                audios = []
                try:
                    with os.scandir(dir_path) as entries:
                        for entry in entries:
                            if entry.name.startswith('.'):
                                continue
                            if entry.is_dir(follow_symlinks=False):
                                continue
                            ext = self.get_file_ext(entry.name)
                            if ext in self.audio_exts:
                                try:
                                    stat = entry.stat()
                                    if os.access(entry.path, os.R_OK):
                                        audios.append({
                                            'name': entry.name,
                                            'path': entry.path,
                                            'ext': ext,
                                            'mtime': stat.st_mtime
                                        })
                                except:
                                    pass
                except Exception as e:
                    self.log(f"扫描异常: {e}")
                
                audios.sort(key=lambda x: x['name'])
                self.audio_list_cache[dir_path] = audios
                self.audio_list_cache_time[dir_path] = current_time
                return audios
            except Exception as e:
                self.log(f"collect_audios_in_dir错误: {e}")
                return []
    
    # ==================== 歌曲信息提取 ====================
    
    def extract_song_info(self, filename):
        name = os.path.splitext(filename)[0]
        name = re.sub(r'^\d+\.\s*', '', name)
        
        patterns_to_remove = [
            r'【.*?】', r'\[.*?\]', r'\{.*?\}', r'（.*?）',
            r'-\s*(?:320k|128k|192k|HQ|SQ|无损|高音质)',
            r'-\s*(?:Live|现场版|演唱会|歌词版|伴奏版)',
            r'\s*\(feat\..*?\)', r'\s*\(Feat\..*?\)',
            r'\s*ft\..*$', r'\s*Ft\..*$',
            r'-\d{8,}-\d+$', r'-\d+$',
        ]
        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.IGNORECASE)
        
        name = re.sub(r'\s+', ' ', name).strip()
        
        artist = ""
        song = name
        
        for sep in [' - ', '-', '–', '—', '：', ':']:
            if sep in name:
                parts = name.split(sep, 1)
                left = parts[0].strip()
                right = parts[1].strip()
                if len(left) < 30 and len(right) > 2:
                    artist, song = left, right
                    break
                elif len(right) < 30 and len(left) > 2:
                    artist, song = right, left
                    break
        
        if not artist and ' - ' in name:
            parts = name.split(' - ', 1)
            song, artist = parts[0].strip(), parts[1].strip()
        
        song = re.sub(r'[《》〈〉『』【】]', '', song).strip()
        artist = re.sub(r'热门歌曲.*$', '', artist).strip()
        artist = re.sub(r'：.*$', '', artist).strip()
        song = re.sub(r'-\d{8,}-\d+$', '', song)
        song = re.sub(r'-\d+$', '', song)
        
        if len(artist) > 30 and len(song) < 20:
            common_artists = ['G.E.M.', '邓紫棋', '周杰伦', '林俊杰', '陈奕迅', '蔡依林', '张惠妹', '王菲', '那英', '孙燕姿', '梁静茹', '洋澜一', '海来阿木', '程响']
            for ca in common_artists:
                if ca in artist:
                    song = artist.replace(ca, '').strip()
                    artist = ca
                    break
        
        return artist, song
    
    # ==================== 修复后的网易云API（URL补全） ====================
    
    def _fix_netease_cover_url(self, pic_url):
        """修复网易云封面URL"""
        if not pic_url:
            return ''
        
        # 修复相对路径
        if pic_url.startswith('//'):
            pic_url = 'https:' + pic_url
        elif pic_url.startswith('/'):
            pic_url = 'https://p1.music.126.net' + pic_url
        elif not pic_url.startswith('http'):
            pic_url = 'https://p1.music.126.net/' + pic_url.lstrip('/')
        
        # 移除旧的尺寸参数，使用300x300
        pic_url = re.sub(r'\?param=\d+x\d+', '', pic_url)
        if '?param=' not in pic_url:
            pic_url += '?param=300y300'
        
        return pic_url
    
    def search_netease_song(self, song_name, artist_name=""):
        """搜索网易云音乐 - 修复版（URL补全+封面尺寸优化）"""
        cache_key = f"net_search_{song_name}_{artist_name}"
        if cache_key in self.song_info_cache:
            cache_time = self.song_info_cache.get(cache_key + "_time", 0)
            if time.time() - cache_time < 3600:
                return self.song_info_cache[cache_key]
        
        try:
            keyword = f"{song_name} {artist_name}".strip() if artist_name else song_name
            # 使用更稳定的API接口
            url = "https://music.163.com/api/cloudsearch/pc"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://music.163.com",
                "Cookie": "appver=2.0.2"
            }
            
            data = {
                "s": keyword,
                "type": 1,
                "offset": 0,
                "limit": 5
            }
            
            resp = self.session.post(url, headers=headers, data=data, timeout=10)
            if resp.status_code == 200:
                result = resp.json()
                songs = result.get('result', {}).get('songs', [])
                if songs:
                    # 尝试找到最佳匹配
                    best_song = None
                    for song in songs:
                        song_name_match = song.get('name', '')
                        if song_name.lower() in song_name_match.lower() or song_name_match.lower() in song_name.lower():
                            best_song = song
                            break
                    if not best_song:
                        best_song = songs[0]
                    
                    # 获取封面URL并修复
                    pic_url = best_song.get('album', {}).get('picUrl', '')
                    pic_url = self._fix_netease_cover_url(pic_url)
                    
                    song_info = {
                        'id': best_song.get('id'),
                        'name': best_song.get('name'),
                        'artist': best_song.get('artists', [{}])[0].get('name', ''),
                        'album': best_song.get('album', {}).get('name', ''),
                        'duration': best_song.get('duration', 0) // 1000,
                        'cover': pic_url
                    }
                    if song_info['id']:
                        self.song_info_cache[cache_key] = song_info
                        self.song_info_cache[cache_key + "_time"] = time.time()
                        self.log(f"网易云搜索成功: {song_info['name']} - {song_info['artist']}")
                        return song_info
            else:
                self.log(f"网易云搜索失败，状态码: {resp.status_code}")
        except Exception as e:
            self.log(f"网易云搜索异常: {e}")
        return None
    
    def get_netease_lyrics(self, song_id):
        """获取网易云歌词 - 修复版"""
        cache_key = f"net_lyrics_{song_id}"
        if cache_key in self.network_lyrics_cache:
            cache_time = self.network_lyrics_cache.get(cache_key + "_time", 0)
            if time.time() - cache_time < 86400:
                return self.network_lyrics_cache[cache_key]
        
        try:
            url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Accept": "application/json, text/plain, */*",
                "Cookie": "appver=2.0.2"
            }
            
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                lyric = data.get('lrc', {}).get('lyric', '')
                if lyric and len(lyric) > 20:
                    self.network_lyrics_cache[cache_key] = lyric
                    self.network_lyrics_cache[cache_key + "_time"] = time.time()
                    self.log(f"网易云歌词获取成功，长度: {len(lyric)}")
                    return lyric
        except Exception as e:
            self.log(f"网易云歌词获取异常: {e}")
        return None
    
    def get_netease_cover(self, song_id):
        """获取网易云封面 - 修复版"""
        cache_key = f"net_cover_{song_id}"
        if cache_key in self.network_cover_cache:
            return self.network_cover_cache[cache_key]
        
        try:
            # 使用更稳定的API
            url = f"https://music.163.com/api/song/detail?id={song_id}"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Accept": "application/json, text/plain, */*",
                "Cookie": "appver=2.0.2"
            }
            
            resp = self.session.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get('songs', [])
                if songs:
                    cover = songs[0].get('album', {}).get('picUrl', '')
                    cover = self._fix_netease_cover_url(cover)
                    if cover:
                        self.network_cover_cache[cache_key] = cover
                        self.log(f"网易云封面获取成功: {cover[:80]}...")
                        return cover
        except Exception as e:
            self.log(f"网易云封面获取异常: {e}")
        return None
    
    def search_qq_song_alternative(self, song_name, artist_name=""):
        """备用：QQ音乐搜索"""
        cache_key = f"qq_search_{song_name}_{artist_name}"
        if cache_key in self.song_info_cache:
            return self.song_info_cache.get(cache_key)
        
        try:
            keyword = f"{song_name} {artist_name}".strip() if artist_name else song_name
            url = "https://c.y.qq.com/soso/fcgi-bin/client_search_cp"
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://y.qq.com/",
                "Accept": "application/json, text/plain, */*"
            }
            
            params = {
                "p": 1,
                "n": 1,
                "w": keyword,
                "format": "json"
            }
            
            resp = self.session.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                songs = data.get('data', {}).get('song', {}).get('list', [])
                if songs:
                    song = songs[0]
                    song_info = {
                        'id': song.get('songmid'),
                        'name': song.get('songname'),
                        'artist': song.get('singer', [{}])[0].get('name', ''),
                        'album': song.get('albumname', ''),
                        'duration': song.get('interval', 0),
                        'cover': f"https://y.gtimg.cn/music/photo_new/T002R300x300M000{song.get('albummid')}.jpg" if song.get('albummid') else ''
                    }
                    self.song_info_cache[cache_key] = song_info
                    self.log(f"QQ音乐搜索成功: {song_info['name']}")
                    return song_info
        except Exception as e:
            self.log(f"QQ音乐搜索异常: {e}")
        return None
    
    def get_network_song_info(self, song_name, artist_name=""):
        """综合获取歌曲信息（优先网易云）"""
        # 优先使用网易云
        song_info = self.search_netease_song(song_name, artist_name)
        
        if not song_info:
            # 备用QQ音乐
            song_info = self.search_qq_song_alternative(song_name, artist_name)
        
        result = {'title': song_name, 'artist': artist_name, 'album': '', 'duration': 0}
        
        if song_info:
            result['title'] = song_info.get('name') or song_name
            result['artist'] = song_info.get('artist') or artist_name
            result['album'] = song_info.get('album') or ''
            result['duration'] = song_info.get('duration', 0)
            
            if self.enable_online_poster and song_info.get('cover'):
                result['cover'] = song_info['cover']
                self.log(f"获取到封面: {result['cover'][:50]}...")
            elif self.enable_online_poster and song_info.get('id'):
                cover = self.get_netease_cover(song_info['id'])
                if cover:
                    result['cover'] = cover
            
            if self.enable_online_lyrics and song_info.get('id'):
                lyrics = self.get_netease_lyrics(song_info['id'])
                if lyrics:
                    result['lyrics'] = lyrics
        
        return result if (result.get('cover') or result.get('lyrics')) else None
    
    # ==================== 本地歌词和封面 ====================
    
    def _get_local_cover(self, file_path):
        audio_dir = os.path.dirname(file_path)
        audio_name = os.path.splitext(os.path.basename(file_path))[0]
        cover_names = [f"{audio_name}.jpg", f"{audio_name}.jpeg", f"{audio_name}.png", f"{audio_name}.JPG", f"{audio_name}.JPEG", f"{audio_name}.PNG", "cover.jpg", "cover.jpeg", "cover.png", "folder.jpg", "album.jpg", "Cover.jpg", "Folder.jpg", "Album.jpg"]
        for cover_name in cover_names:
            cover_path = os.path.join(audio_dir, cover_name)
            if os.path.exists(cover_path) and os.path.isfile(cover_path):
                return f"file://{cover_path}"
        return None
    
    def _get_local_lyrics(self, file_path):
        audio_dir = os.path.dirname(file_path)
        audio_name = os.path.splitext(os.path.basename(file_path))[0]
        try:
            with os.scandir(audio_dir) as entries:
                for entry in entries:
                    if entry.name.startswith('.'):
                        continue
                    if not entry.is_file():
                        continue
                    ext = self.get_file_ext(entry.name)
                    if ext in self.lrc_exts:
                        lrc_name = os.path.splitext(entry.name)[0]
                        if lrc_name == audio_name or lrc_name.lower() == audio_name.lower():
                            try:
                                with open(entry.path, 'r', encoding='utf-8', errors='ignore') as f:
                                    content = f.read()
                                    if content and len(content) > 20:
                                        return content
                            except:
                                pass
        except:
            pass
        
        for subdir in ['Lyrics', 'lyrics', '歌词', 'LRC', 'lrc']:
            lyrics_dir = os.path.join(audio_dir, subdir)
            if os.path.exists(lyrics_dir) and os.path.isdir(lyrics_dir):
                try:
                    with os.scandir(lyrics_dir) as entries:
                        for entry in entries:
                            if entry.name.startswith('.'):
                                continue
                            if not entry.is_file():
                                continue
                            ext = self.get_file_ext(entry.name)
                            if ext in self.lrc_exts:
                                lrc_name = os.path.splitext(entry.name)[0]
                                if lrc_name == audio_name or lrc_name.lower() == audio_name.lower():
                                    try:
                                        with open(entry.path, 'r', encoding='utf-8', errors='ignore') as f:
                                            content = f.read()
                                            if content and len(content) > 20:
                                                return content
                                    except:
                                        pass
                except:
                    pass
        return None
    
    def _add_audio_info_fast(self, result, file_path):
        filename = os.path.basename(file_path)
        artist, song = self.extract_song_info(filename)
        result["title"] = song or filename
        result["artist"] = artist or ""
        
        cover_url = self._get_local_cover(file_path)
        if cover_url:
            result["poster"] = cover_url
            self.log(f"使用本地封面: {cover_url}")
        else:
            result["poster"] = self.file_icons.get('music_note')
        
        lyrics = self._get_local_lyrics(file_path)
        if lyrics:
            result["lrc"] = lyrics
            self.log(f"使用本地歌词")
        
        # 如果没有本地歌词或封面，尝试网络获取
        if (not cover_url and self.enable_online_poster) or (not lyrics and self.enable_online_lyrics):
            if song:
                try:
                    self.log(f"尝试网络获取: 歌曲={song}, 艺术家={artist}")
                    net_info = self.get_network_song_info(song, artist)
                    if net_info:
                        if not cover_url and net_info.get('cover'):
                            result["poster"] = net_info['cover']
                            self.log(f"✅ 获取网络封面成功: {net_info['cover'][:50]}...")
                        if not lyrics and net_info.get('lyrics'):
                            result["lrc"] = net_info['lyrics']
                            self.log(f"✅ 获取网络歌词成功: {len(net_info['lyrics'])} 字符")
                        if net_info.get('album'):
                            result["album"] = net_info['album']
                        if net_info.get('duration'):
                            result["duration"] = net_info['duration']
                    else:
                        self.log(f"⚠️ 网络获取失败，未找到歌曲信息")
                except Exception as e:
                    self.log(f"❌ 网络获取异常: {e}")
            else:
                self.log(f"无法提取歌曲名: {filename}")
    
    # ==================== 彩色图标生成 ====================
    
    def _generate_colored_icon(self, color, text):
        svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" viewBox="0 0 200 200">
            <rect width="200" height="200" rx="40" ry="40" fill="{color}"/>
            <text x="100" y="140" font-size="120" text-anchor="middle" fill="white" font-family="Arial" font-weight="bold">{text}</text>
        </svg>'''
        return f"data:image/svg+xml;base64,{base64.b64encode(svg.encode()).decode()}"
    
    # ==================== 在线直播（修复乱码） ====================
    
    def _detect_and_decode(self, raw_content, source_name=""):
        """检测编码并解码内容 - 保守版：只选择正确的编码，不修改内容"""
        if not raw_content:
            return None
        
        # 按优先级尝试编码
        encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'big5']
        
        best_result = None
        best_score = -1
        
        for encoding in encodings:
            try:
                decoded = raw_content.decode(encoding)
                # 计算解码质量分数
                score = self._calculate_decode_score(decoded)
                if score > best_score:
                    best_score = score
                    best_result = decoded
                # 如果分数很高，直接返回
                if score > 0.85:
                    self.log(f"✅ {source_name} 使用编码: {encoding}, 分数: {score}")
                    return decoded
            except:
                continue
        
        # 尝试使用 chardet 自动检测
        try:
            import chardet
            detected = chardet.detect(raw_content)
            if detected and detected['encoding'] and detected['confidence'] > 0.6:
                try:
                    decoded = raw_content.decode(detected['encoding'])
                    if self._calculate_decode_score(decoded) > 0.7:
                        self.log(f"✅ {source_name} 使用chardet编码: {detected['encoding']}, 置信度: {detected['confidence']}")
                        return decoded
                except:
                    pass
        except ImportError:
            pass
        
        # 返回最佳结果
        if best_result:
            self.log(f"✅ {source_name} 使用最佳编码，分数: {best_score}")
            return best_result
        
        # 最后尝试
        try:
            decoded = raw_content.decode('utf-8', errors='replace')
            return decoded
        except:
            pass
        
        self.log(f"⚠️ {source_name} 解码失败")
        return None
    
    def _calculate_decode_score(self, text):
        """计算解码质量分数"""
        if not text or len(text) < 5:
            return 0
        
        score = 0
        
        # 可打印字符比例
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        printable_ratio = printable / len(text) if len(text) > 0 else 0
        if printable_ratio > 0.9:
            score += 0.35
        elif printable_ratio > 0.7:
            score += 0.2
        
        # 中文字符比例
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        chinese_ratio = chinese / len(text) if len(text) > 0 else 0
        if chinese_ratio > 0.15:
            score += 0.4
        elif chinese_ratio > 0.05:
            score += 0.2
        
        # 常见直播源特征（逗号分隔的频道）
        if ',' in text and '\n' in text:
            score += 0.1
        
        # 检查替换字符（乱码标志）
        replacement = sum(1 for c in text if c == '\ufffd')
        if replacement > 0:
            score -= 0.3 * (replacement / len(text))
        
        return max(0, min(1, score))
    
    def _is_valid_text(self, text):
        """检查文本是否有效"""
        if not text or len(text) < 5:
            return False
        
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        ratio = printable / len(text) if len(text) > 0 else 0
        if ratio < 0.5:
            return False
        
        chinese = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        chinese_ratio = chinese / len(text) if len(text) > 0 else 0
        
        ascii_chars = sum(1 for c in text if ord(c) < 128 and c.isprintable())
        ascii_ratio = ascii_chars / len(text) if len(text) > 0 else 0
        
        return (chinese_ratio > 0.03 or ascii_ratio > 0.15)
    
    def _clean_garbled_text(self, text):
        """只清理控制字符，不改变正常文本"""
        if not text:
            return text
        
        # 只移除真正的控制字符（保留换行和回车）
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
        
        # 移除BOM标记
        if text.startswith('\ufeff'):
            text = text[1:]
        
        return text.strip()
    
    def _fetch_with_auto_headers(self, url, ua=None, source_name=""):
        """获取直播源内容，自动处理编码"""
        domain = self._get_domain_from_url(url)
        self.log(f"获取直播源: {source_name} | {domain}, UA={ua if ua else '默认'}")
        
        # 处理file://协议
        if url.startswith('file://'):
            file_path = url[7:]
            # 尝试多种编码读取文件
            encodings = ['utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'big5']
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='ignore') as f:
                        content = f.read()
                    self.log(f"✅ 文件读取成功，使用编码: {encoding}, 内容长度: {len(content)}")
                    if self._is_valid_text(content):
                        self.log(f"✅ 内容验证通过")
                        return content.encode('utf-8')
                    else:
                        self.log(f"⚠️ 内容可能仍有问题，尝试其他编码")
                        continue
                except Exception as e:
                    continue
            
            # 尝试二进制读取并检测
            try:
                with open(file_path, 'rb') as f:
                    raw = f.read()
                    decoded = self._detect_and_decode(raw, source_name)
                    if decoded:
                        return decoded.encode('utf-8')
            except:
                pass
            
            self.log(f"❌ 读取本地文件失败: {file_path}")
            return None
        
        # 处理HTTP请求
        if ua and ua.strip():
            headers = {
                "User-Agent": ua,
                "Accept": "*/*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Connection": "keep-alive"
            }
            try:
                self.log(f"使用指定UA请求: {ua}")
                resp = self.session.get(url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    content = self._detect_and_decode(resp.content, source_name)
                    if content:
                        return content.encode('utf-8')
                else:
                    self.log(f"指定UA请求失败，状态码: {resp.status_code}")
            except Exception as e:
                self.log(f"指定UA请求异常: {e}")
        
        if domain in self.domain_specific_headers:
            for headers_info in self.domain_specific_headers[domain]:
                try:
                    resp = self.session.get(url, headers=headers_info['headers'], timeout=15)
                    if resp.status_code == 200:
                        content = self._detect_and_decode(resp.content, source_name)
                        if content:
                            return content.encode('utf-8')
                except:
                    continue
        
        for headers_info in self.common_headers_list:
            try:
                resp = self.session.get(url, headers=headers_info['headers'], timeout=10)
                if resp.status_code == 200:
                    content = self._detect_and_decode(resp.content, source_name)
                    if content:
                        return content.encode('utf-8')
            except:
                continue
        
        return None
    
    def _get_domain_from_url(self, url):
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            return domain.split(':')[0] if ':' in domain else domain
        except:
            return ""
    
    def _get_live_programs(self, source):
        source_id = source['id']
        source_name = source.get('name', '未知')
        current_time = time.time()
        
        if source_id in self.live_cache and current_time - self.live_cache_time.get(source_id, 0) < self.live_cache_duration:
            self.log(f"使用缓存的节目列表: {source_name}")
            return self.live_cache[source_id]
        
        ua = source.get('ua', None)
        if ua is None or ua == "":
            ua = None
        
        self.log(f"获取直播源: {source_name}, URL={source['url']}")
        
        content = self._fetch_with_auto_headers(source['url'], ua, source_name)
        if not content:
            self.log(f"获取失败: {source_name}")
            return []
        
        decoded_content = content.decode('utf-8', errors='replace')
        programs = self._parse_live_content(decoded_content, source)
        
        if programs:
            self.live_cache[source_id] = programs
            self.live_cache_time[source_id] = current_time
            self.log(f"获取成功: {source_name}, 共 {len(programs)} 个节目")
        else:
            self.log(f"解析失败: {source_name}")
        
        return programs
    
    def _parse_live_content(self, content, source):
        source_type = source.get('type', 'm3u')
        if source_type == 'txt' or ',#genre#' in content.lower():
            return self._parse_txt_live(content)
        elif content.strip().startswith(('{', '[')):
            return self._parse_json_live(content)
        else:
            return self._parse_m3u_live(content)
    
    def _parse_m3u_live(self, content):
        programs = []
        lines = content.split('\n')
        current_name = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith('#EXTINF:'):
                name_match = re.search(r',(.+)$', line)
                if name_match:
                    current_name = name_match.group(1).strip()
                else:
                    name_match = re.search(r'tvg-name="([^"]+)"', line)
                    if name_match:
                        current_name = name_match.group(1).strip()
                if current_name:
                    current_name = self._clean_garbled_text(current_name)
            elif line and not line.startswith('#') and current_name:
                if self.is_playable_url(line):
                    programs.append({'name': current_name, 'url': line})
                current_name = None
        return programs
    
    def _parse_txt_live(self, content):
        """解析txt格式直播源 - 修复版：不加分类前缀，保留原始顺序"""
        programs = []
        lines = content.split('\n')
        current_cat = "默认分类"
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # 只做基本清理，不改变字符内容
            line = self._clean_garbled_text(line)
            if not line:
                continue
            
            # 处理分类标签 (格式: 分类名,#genre#)
            if ',#genre#' in line.lower():
                cat_name = line.split(',')[0].strip()
                if cat_name:
                    current_cat = cat_name
                continue
            
            # 解析频道条目 (格式: 频道名,URL)
            if ',' in line:
                comma_pos = line.find(',')
                name = line[:comma_pos].strip()
                url = line[comma_pos + 1:].strip()
                
                if not name or not url:
                    continue
                
                # 修复URL格式
                if not self.is_playable_url(url):
                    if url.startswith('http:/') and not url.startswith('http://'):
                        url = url.replace('http:/', 'http://')
                    elif url.startswith('https:/') and not url.startswith('https://'):
                        url = url.replace('https:/', 'https://')
                    elif url.startswith('//'):
                        url = 'https:' + url
                    
                    if not self.is_playable_url(url):
                        continue
                
                # 直接使用原始频道名，不加前缀
                display_name = name
                
                if len(display_name) > 60:
                    display_name = display_name[:57] + "..."
                
                programs.append({
                    'name': display_name,
                    'url': url,
                    'category': current_cat,
                    'original_name': name
                })
        
        # 重要：不再排序，保留原始顺序！只做去重（保留第一次出现的位置）
        seen = set()
        unique_programs = []
        for p in programs:
            key = f"{p['category']}|{p['original_name']}|{p['url']}"
            if key not in seen:
                seen.add(key)
                unique_programs.append(p)
        
        print(f"📊 TXT直播源解析完成: 共 {len(unique_programs)} 个频道（按原始顺序）")
        
        return unique_programs
    
    def _parse_json_live(self, content):
        programs = []
        try:
            data = json.loads(content)
            items = []
            if isinstance(data, dict):
                for key in ['list', 'data', 'items', 'videos']:
                    if key in data and isinstance(data[key], list):
                        items = data[key]
                        break
                if not items:
                    items = [data]
            else:
                items = data
            for item in items:
                if isinstance(item, dict):
                    name = item.get('name') or item.get('title')
                    url = item.get('url') or item.get('play_url')
                    if name and url and self.is_playable_url(url):
                        programs.append({'name': name, 'url': url})
        except:
            pass
        return programs
    
    # ==================== 首页和分类 ====================
    
    def homeContent(self, filter):
        classes = []
        for i, path in enumerate(self.music_paths):
            if os.path.exists(path):
                name = os.path.basename(path.rstrip('/')) or f'音乐{i}'
                classes.append({"type_id": f"music_root_{i}", "type_name": f"🎵 {name}"})
        classes.append({"type_id": "all_music", "type_name": "🎶 全部音乐"})
        classes.append({"type_id": self.live_category_id, "type_name": self.live_category_name})
        return {'class': classes}
    
    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg)
        
        if tid == self.live_category_id:
            return self._live_category_content(pg)
        
        if tid == 'all_music':
            return self._all_music_content(pg)
        
        if tid.startswith('music_root_'):
            try:
                idx = int(tid[11:])
                path = self.music_paths[idx] if idx < len(self.music_paths) else None
                if path and os.path.exists(path):
                    return self._music_directory_content(path, pg)
            except:
                pass
        
        if tid.startswith(self.FOLDER_PREFIX):
            folder_path = self.b64u_decode(tid[len(self.FOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self._music_directory_content(folder_path, pg)
        
        return {'list': [], 'page': pg, 'pagecount': 1}
    
    def _music_directory_content(self, path, pg):
        files = self.scan_music_directory(path)
        total = len(files)
        per_page = 50
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_files = files[start:end]
        
        vlist = []
        
        parent = os.path.dirname(path)
        if parent != path:
            is_root = False
            for root in self.music_paths:
                if os.path.normpath(path) == os.path.normpath(root.rstrip('/')):
                    is_root = True
                    break
            
            if not is_root:
                in_music_path = False
                for root in self.music_paths:
                    if parent.startswith(root):
                        in_music_path = True
                        break
                
                if in_music_path:
                    parent_id = self.FOLDER_PREFIX + self.b64u_encode(parent)
                    vlist.append({'vod_id': parent_id, 'vod_name': f'⬅️ 返回 {os.path.basename(parent)}', 'vod_pic': self.file_icons['folder'], 'vod_remarks': '上级目录', 'vod_tag': 'folder', 'style': {'type': 'list'}})
        
        for f in page_files:
            if f['is_dir']:
                vlist.append({
                    'vod_id': self.FOLDER_PREFIX + self.b64u_encode(f['path']),
                    'vod_name': f"📁 {f['name']}",
                    'vod_pic': self.file_icons['folder'],
                    'vod_remarks': '子目录',
                    'vod_tag': 'folder',
                    'style': {'type': 'list'}
                })
            elif self.is_audio_file(f['ext']):
                vlist.append({
                    'vod_id': f"{self.A_ALL_PREFIX}{self.b64u_encode(path)}#{f['path']}",
                    'vod_name': f"🎵 {f['name']}",
                    'vod_pic': self.file_icons['music_note'],
                    'vod_play_url': f"播放${self.MP3_PREFIX + f['path']}",
                    'vod_remarks': '音频',
                    'vod_tag': 'audio',
                    'style': {'type': 'list'}
                })
            elif self.is_lrc_file(f['ext']):
                vlist.append({
                    'vod_id': f['path'],
                    'vod_name': f"📝 {f['name']}",
                    'vod_pic': self.file_icons['lrc'],
                    'vod_remarks': '歌词',
                    'vod_tag': 'lrc',
                    'style': {'type': 'list'}
                })
        
        return {'list': vlist, 'page': pg, 'pagecount': (total + per_page - 1) // per_page, 'limit': per_page, 'total': total}
    
    def _all_music_content(self, pg):
        all_audios = self._scan_all_music_recursive()
        
        total = len(all_audios)
        per_page = 100
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        
        vlist = []
        for audio in all_audios[start:end]:
            vlist.append({
                'vod_id': f"{self.ALL_MUSIC_PREFIX}{self.b64u_encode(audio['path'])}",
                'vod_name': f"🎵 {audio['name']}",
                'vod_pic': self.file_icons['music_note'],
                'vod_play_url': f"播放${self.MP3_PREFIX + audio['path']}",
                'vod_remarks': f"📁 {os.path.basename(audio['dir'])}",
                'vod_tag': 'audio',
                'style': {'type': 'list'}
            })
        
        return {'list': vlist, 'page': pg, 'pagecount': (total + per_page - 1) // per_page, 'limit': per_page, 'total': total}
    
    def _live_category_content(self, pg):
        vlist = []
        for idx, source in enumerate(self.online_live_sources):
            programs = self.live_cache.get(source['id'], [])
            color = source.get('color', self.default_colors[idx % len(self.default_colors)])
            first_char = source['name'][0] if source['name'] else "直播"
            icon = self._generate_colored_icon(color, first_char)
            remarks = source.get('remarks', '')
            if programs:
                remarks += f" {len(programs)}个节目"
            else:
                remarks += " 点击加载"
            vlist.append({'vod_id': self.LIVE_PREFIX + self.b64u_encode(source['id']), 'vod_name': source['name'], 'vod_pic': icon, 'vod_remarks': remarks, 'vod_tag': 'live_source', 'style': {'type': 'list'}, 'type': 'live'})
        return {'list': vlist, 'page': pg, 'pagecount': 1, 'limit': len(vlist), 'total': len(vlist)}
    
    def _live_source_detail(self, source_id):
        source = next((s for s in self.online_live_sources if s['id'] == source_id), None)
        if not source:
            return {'list': []}
        
        cache_key = f"live_detail_{source_id}"
        current_time = time.time()
        if cache_key in self.live_detail_cache and current_time - self.live_detail_cache_time.get(cache_key, 0) < 300:
            return self.live_detail_cache[cache_key]
        
        idx = self.online_live_sources.index(source)
        color = source.get('color', self.default_colors[idx % len(self.default_colors)])
        first_char = source['name'][0] if source['name'] else "直播"
        icon = self._generate_colored_icon(color, first_char)
        
        programs = self._get_live_programs(source)
        if not programs:
            result = {'list': [{'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id), 'vod_name': source['name'], 'vod_pic': icon, 'vod_play_from': source_id, 'vod_play_url': '提示$无法获取直播源，请稍后重试', 'vod_content': f"直播源: {source['url']}\n状态: 获取失败", 'style': {'type': 'list'}, 'type': 'live', 'vod_type': 4, 'vod_class': 'live', 'vod_style': {'type': 'live'}, 'playerType': source.get('playerType', 2)}]}
            self.live_detail_cache[cache_key] = result
            self.live_detail_cache_time[cache_key] = current_time
            return result
        
        channels = {}
        for p in programs:
            name = p.get('name', '')
            original_name = name
            
            clean_name = re.sub(r'\s*[\[\(（]\s*\d+\s*[\]\)）]\s*$', '', name)
            clean_name = re.sub(r'\s*[线|L|l]ine?\s*\d+$', '', clean_name, flags=re.I)
            clean_name = re.sub(r'[;；,，、]+$', '', clean_name)
            clean_name = clean_name.strip()
            
            if not clean_name:
                clean_name = original_name
            
            if clean_name not in channels:
                channels[clean_name] = []
            
            if p['url'] not in channels[clean_name]:
                channels[clean_name].append(p['url'])
        
        max_lines = max(len(urls) for urls in channels.values())
        original_max_lines = max_lines
        if max_lines > 3:
            max_lines = 3
        
        from_list = []
        url_list = []
        for line_idx in range(max_lines):
            line_name = f"线路{line_idx + 1}"
            channel_urls = []
            for channel_name, urls in channels.items():
                if line_idx < len(urls):
                    channel_urls.append(f"{channel_name}${urls[line_idx]}")
            if channel_urls:
                from_list.append(line_name)
                url_list.append('#'.join(channel_urls))
        
        if not from_list:
            result = {'list': [{'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id), 'vod_name': source['name'], 'vod_pic': icon, 'vod_play_from': source_id, 'vod_play_url': '提示$没有可用的线路', 'vod_content': f"直播源: {source['url']}\n状态: 没有可用的线路", 'style': {'type': 'list'}, 'type': 'live', 'vod_type': 4, 'vod_class': 'live', 'vod_style': {'type': 'live'}, 'playerType': source.get('playerType', 2)}]}
            self.live_detail_cache[cache_key] = result
            self.live_detail_cache_time[cache_key] = current_time
            return result
        
        current_date = time.strftime('%Y.%m.%d', time.localtime())
        total_channels = len(channels)
        total_programs = sum(len(urls) for urls in channels.values())
        remarks = f'更新时间{current_date}'
        if original_max_lines > 3:
            remarks += f' (仅显示前3条线路)'
        
        result = {'list': [{'vod_id': self.LIVE_PREFIX + self.b64u_encode(source_id), 'vod_name': source['name'], 'vod_pic': icon, 'vod_play_from': source_id, 'vod_play_url': '$$$'.join(url_list), 'vod_remarks': remarks, 'vod_content': f"共 {total_channels} 个频道，{total_programs} 条节目线路", 'vod_style': {'type': 'live'}, 'vod_type': 4, 'vod_class': 'live', 'type': 'live', 'style': {'type': 'live'}, 'playerType': source.get('playerType', 2)}]}
        
        self.live_detail_cache[cache_key] = result
        self.live_detail_cache_time[cache_key] = current_time
        return result
    
    # ==================== 详情页 ====================
    
    def detailContent(self, ids):
        id_val = ids[0]
        self.log(f"详情页请求: {id_val}")
        
        if id_val.startswith(self.LIVE_PREFIX):
            source_id = self.b64u_decode(id_val[len(self.LIVE_PREFIX):])
            return self._live_source_detail(source_id)
        
        if id_val.startswith(self.ALL_MUSIC_PREFIX):
            encoded_path = id_val[len(self.ALL_MUSIC_PREFIX):]
            file_path = self.b64u_decode(encoded_path)
            return self._handle_all_music_playlist(file_path)
        
        if id_val.startswith(self.A_ALL_PREFIX):
            parts = id_val[len(self.A_ALL_PREFIX):].split('#', 1)
            if len(parts) == 2:
                encoded_dir = parts[0]
                clicked_path = parts[1]
                dir_path = self.b64u_decode(encoded_dir)
                return self._handle_dir_playlist(dir_path, clicked_path)
            return {'list': []}
        
        if id_val.startswith(self.FOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.FOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self._music_directory_content(folder_path, 1)
            return {'list': []}
        
        if os.path.exists(id_val) and os.path.isfile(id_val):
            ext = self.get_file_ext(id_val)
            if self.is_audio_file(ext):
                dir_path = os.path.dirname(id_val)
                return self._handle_dir_playlist(dir_path, id_val)
        
        if os.path.exists(id_val) and os.path.isdir(id_val):
            return self._music_directory_content(id_val, 1)
        
        return {'list': []}
    
    def _handle_all_music_playlist(self, clicked_path):
        """处理全部音乐播放列表 - 修复随机播放循环问题"""
        all_audios = self._scan_all_music_recursive()
        
        if not all_audios:
            return {'list': []}
        
        clicked_index = -1
        for i, audio in enumerate(all_audios):
            if audio['path'] == clicked_path:
                clicked_index = i
                break
        
        reordered_audios = []
        if clicked_index >= 0:
            reordered_audios.extend(all_audios[clicked_index:])
            reordered_audios.extend(all_audios[:clicked_index])
        else:
            reordered_audios = all_audios
        
        if len(reordered_audios) > 1000:
            reordered_audios = reordered_audios[:1000]
        
        play_urls = []
        total = len(reordered_audios)
        for i, audio in enumerate(reordered_audios):
            audio_name = os.path.splitext(audio['name'])[0]
            if len(audio_name) > 50:
                audio_name = audio_name[:47] + '...'
            
            # 添加循环标记：如果是最后一首，添加特殊标记让播放器知道需要循环
            url_part = self.MP3_PREFIX + audio['path']
            if i == total - 1:
                # 最后一首，添加循环标记
                url_part = f"LOOP_NEXT_FIRST${url_part}"
            
            play_urls.append(f"{audio_name}${url_part}")
        
        # 如果只有一首歌，也要支持循环
        if total == 1:
            play_urls[0] = play_urls[0].replace(f"{self.MP3_PREFIX}", f"LOOP_SINGLE${self.MP3_PREFIX}")
        
        vod = {
            'vod_id': f"allmusic_playlist",
            'vod_name': f"🎶 全部音乐 ({len(all_audios)}首)",
            'vod_pic': self.file_icons.get('audio_playlist', self.file_icons.get('music_note')),
            'vod_play_from': '本地音乐',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{len(all_audios)}首音乐，来自整个音乐库（支持循环播放）',
            'style': {'type': 'list'}
        }
        
        return {'list': [vod]}
    
    def _handle_dir_playlist(self, dir_path, clicked_path):
        """处理目录播放列表 - 修复随机播放循环问题"""
        all_audios = self.collect_audios_in_dir(dir_path, recursive=True)
        
        if not all_audios:
            return {'list': []}
        
        all_audios.sort(key=lambda x: x['name'])
        
        clicked_index = -1
        for i, audio in enumerate(all_audios):
            if audio['path'] == clicked_path:
                clicked_index = i
                break
        
        reordered_audios = []
        if clicked_index >= 0:
            reordered_audios.extend(all_audios[clicked_index:])
            reordered_audios.extend(all_audios[:clicked_index])
        else:
            reordered_audios = all_audios
        
        if len(reordered_audios) > 500:
            reordered_audios = reordered_audios[:500]
        
        play_urls = []
        total = len(reordered_audios)
        for i, audio in enumerate(reordered_audios):
            audio_name = os.path.splitext(audio['name'])[0]
            if len(audio_name) > 50:
                audio_name = audio_name[:47] + '...'
            
            # 添加循环标记：如果是最后一首，添加特殊标记让播放器知道需要循环
            url_part = self.MP3_PREFIX + audio['path']
            if i == total - 1:
                # 最后一首，添加循环标记，播放器会跳转到第一首
                url_part = f"LOOP_NEXT_FIRST${url_part}"
            
            play_urls.append(f"{audio_name}${url_part}")
        
        # 如果只有一首歌，也要支持循环
        if total == 1:
            play_urls[0] = play_urls[0].replace(f"{self.MP3_PREFIX}", f"LOOP_SINGLE${self.MP3_PREFIX}")
        
        vod = {
            'vod_id': f"dir_playlist_{self.b64u_encode(dir_path)}",
            'vod_name': f"🎵 {os.path.basename(dir_path)} ({len(all_audios)}首)",
            'vod_pic': self.file_icons.get('audio_playlist', self.file_icons.get('music_note')),
            'vod_play_from': '本地音乐',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{len(all_audios)}首音乐，来自{os.path.basename(dir_path)}及子目录（支持循环播放）',
            'style': {'type': 'list'}
        }
        
        return {'list': [vod]}
    
    # ==================== 播放页 ====================
    
    def playerContent(self, flag, id, vipFlags):
        self.log(f"播放请求: flag={flag}, id={id[:100] if len(id) > 100 else id}")
        
        # 处理循环播放标记
        loop_next_first = False
        loop_single = False
        
        # 检查循环标记
        if id.startswith('LOOP_NEXT_FIRST$'):
            id = id.replace('LOOP_NEXT_FIRST$', '', 1)
            loop_next_first = True
            self.log(f"检测到循环播放标记（最后一首，下一首跳转到第一首）")
        elif id.startswith('LOOP_SINGLE$'):
            id = id.replace('LOOP_SINGLE$', '', 1)
            loop_single = True
            self.log(f"检测到单曲循环标记")
        
        if id.startswith(self.MP3_PREFIX):
            return self._handle_mp3_play(id, loop_next_first, loop_single)
        
        url = id
        if '$' in url:
            parts = url.split('$', 1)
            if len(parts) == 2:
                url = parts[1]
        
        if url.startswith(('http://', 'https://', 'file://')):
            pass
        else:
            try:
                decoded = base64.b64decode(url).decode('utf-8')
                if decoded.startswith(('http://', 'https://', 'file://')):
                    url = decoded
            except:
                pass
        
        headers = self._build_headers(flag, url)
        result = {"parse": 0, "playUrl": "", "url": url, "header": headers}
        
        if url.startswith('file://'):
            file_path = url[7:]
            while '//' in file_path:
                file_path = file_path.replace('//', '/')
            if os.path.exists(file_path) and self.is_audio_file(self.get_file_ext(file_path)):
                self._add_audio_info_fast(result, file_path)
            play_url = f"music://http://127.0.0.1:9988/file{file_path}"
            result["url"] = play_url
            self.log(f"file:// 转换为 music://+代理地址: {play_url}")
        
        # 添加循环标记到返回结果，让播放器知道需要循环
        if loop_next_first:
            result["next_is_first"] = True
        if loop_single:
            result["loop_single"] = True
        
        return result
    
    def _handle_mp3_play(self, id, loop_next_first=False, loop_single=False):
        """处理MP3播放，支持循环标记"""
        file_path = id.replace(self.MP3_PREFIX, '')
        if not os.path.exists(file_path):
            test_paths = [file_path, '/storage/emulated/0/' + file_path.lstrip('/'), file_path.replace('//', '/')]
            for test_path in test_paths:
                if os.path.exists(test_path):
                    file_path = test_path
                    break
            else:
                return {"parse": 0, "playUrl": "", "url": "", "header": {}, "error": "文件不存在"}
        
        if not os.access(file_path, os.R_OK):
            return {"parse": 0, "playUrl": "", "url": "", "header": {}, "error": "文件无法读取"}
        
        play_url = f"music://http://127.0.0.1:9988/file{file_path}"
        result = {"parse": 0, "playUrl": "", "url": play_url, "header": {}}
        
        if self.is_audio_file(self.get_file_ext(file_path)):
            self._add_audio_info_fast(result, file_path)
        
        # 添加循环标记，让播放器知道如何处理
        if loop_next_first:
            result["next_is_first"] = True
            self.log(f"添加循环标记: 播放完当前歌曲后跳转到列表第一首")
        if loop_single:
            result["loop_single"] = True
            self.log(f"添加单曲循环标记")
        
        return result
    
    def _build_headers(self, flag, url):
        """构建播放请求头 - 修复版：正确传递自定义UA"""
        from urllib.parse import urlparse
        domain = urlparse(url).netloc
        
        # 默认请求头
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
        
        custom_ua_used = False
        
        # 修复：根据flag查找直播源并设置UA
        if flag:
            for source in self.online_live_sources:
                if source['id'] == flag:
                    source_ua = source.get('ua', '')
                    if source_ua:
                        headers["User-Agent"] = source_ua
                        custom_ua_used = True
                        print(f"✅ 播放器使用自定义UA: {source_ua}")
                    if source.get('url'):
                        try:
                            source_domain = urlparse(source['url']).netloc
                            if source_domain:
                                headers["Referer"] = f"https://{source_domain}/"
                        except:
                            pass
                    break
        
        # 域名特定UA覆盖（优先级：自定义UA > 域名特定 > 默认）
        # 只有在没有使用自定义UA的情况下，才使用域名特定配置
        if domain and not custom_ua_used:
            if 't.061899.xyz' in domain:
                headers.update({"User-Agent": "okhttp/3.12.11", "Referer": "http://t.061899.xyz/"})
                print(f"✅ 播放器使用域名特定UA (t.061899.xyz)")
            elif 'rihou.cc' in domain:
                headers.update({"Referer": "https://rihou.cc:555/"})
                print(f"✅ 播放器使用域名特定Referer (rihou.cc)")
            elif 'gongdian.top' in domain:
                headers.update({"Referer": "https://gongdian.top/"})
                print(f"✅ 播放器使用域名特定Referer (gongdian.top)")
            else:
                # 添加默认Referer
                if "Referer" not in headers:
                    headers["Referer"] = f"https://{domain}/"
        
        return headers
    
    # ==================== 搜索 ====================
    
    def searchContent(self, key, quick, pg=1):
        pg = int(pg)
        results = []
        clean_key = re.sub(r'^[📁📂🎵🎬📝⬅️\s]+', '', key.lower())
        
        all_audios = self._scan_all_music_recursive()
        
        for audio in all_audios:
            if clean_key in audio['name'].lower():
                results.append({
                    'vod_id': f"{self.ALL_MUSIC_PREFIX}{self.b64u_encode(audio['path'])}",
                    'vod_name': f"🎵 {audio['name']}",
                    'vod_pic': self.file_icons['music_note'],
                    'vod_play_url': f"播放${self.MP3_PREFIX + audio['path']}",
                    'vod_remarks': f"📁 {os.path.basename(audio['dir'])}",
                    'style': {'type': 'list'}
                })
        
        results.sort(key=lambda x: x['vod_name'])
        per_page = 50
        start = (pg - 1) * per_page
        end = min(start + per_page, len(results))
        return {'list': results[start:end], 'page': pg, 'pagecount': (len(results) + per_page - 1) // per_page, 'limit': per_page, 'total': len(results)}
    
    # ==================== 缓存清理 ====================
    
    def clear_audio_cache(self):
        self.audio_list_cache.clear()
        self.audio_list_cache_time.clear()
        self.all_music_cache = []
        self.all_music_cache_time = 0
        self.log(f"音频缓存已清理")
    
    def clear_network_cache(self):
        self.network_lyrics_cache.clear()
        self.network_cover_cache.clear()
        self.song_info_cache.clear()
        self.log("网络缓存已清理")
    
    def clear_scan_cache(self):
        self.scan_cache.clear()
        self.scan_cache_time.clear()
        self.log("目录扫描缓存已清理")