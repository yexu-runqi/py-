#!/usr/bin/env python3
import os
import re
import json
import asyncio
import aiofiles
import cloudscraper
from urllib.parse import urljoin
from dataclasses import dataclass
from typing import List, Optional

# ==================== 配置 ====================
BASE_URL = "https://missav.live"
TXT_PATH = "/storage/emulated/0/lz/aa.txt"          # IPTV M3U 格式（实时追加）
JSON_PATH = "/storage/emulated/0/lz/missav.json"    # TVBox VOD JSON 格式（实时更新）
OUTPUT_DIR = "/sdcard/missav_links"
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(os.path.dirname(TXT_PATH), exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": BASE_URL,
    "Origin": BASE_URL,
}

# 爬取控制（测试建议先用小数字，全部爬取请改大）
MAX_ACTRESS_LIST_PAGES = 1400          # 女优列表页数（测试用 3\~5，全量约1400+页）
MAX_GENRE_LIST_PAGES = 23           # ←←← Genres 分类列表页数（网站共23页，测试用 3\~5，全量改23）
MAX_VIDEO_PAGES_PER_CATEGORY = 999  # 每个分类（女优或Genres）爬多少页视频（999=爬到没有下一页为止）

# ==================== 数据库（磁力专用，实时保存） ====================
import aiosqlite

@dataclass
class VideoInfo:
    code: str
    title: str
    url: str
    video_stream_url: str
    magnet_links: List[str]
    category: str          # 现在统一用 category（女优或Genres名称）
    cover: str

class AsyncDB:
    def __init__(self, path):
        self.path = path

    async def init(self):
        self.conn = await aiosqlite.connect(self.path)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                code TEXT PRIMARY KEY,
                title TEXT,
                url TEXT,
                stream TEXT,
                magnets TEXT,
                category TEXT,
                cover TEXT
            )""")
        await self.conn.commit()

    async def save_video(self, v: VideoInfo):
        await self.conn.execute(
            "INSERT INTO videos VALUES (?,?,?,?,?,?,?) ON CONFLICT(code) DO UPDATE SET stream=excluded.stream",
            (v.code, v.title, v.url, v.video_stream_url, json.dumps(v.magnet_links), v.category, v.cover)
        )
        await self.conn.commit()

# ==================== 解析逻辑（完全保留 + 增强） ====================
def extract_video_stream(html: str) -> str:
    surrit_match = re.search(r'https://surrit\.com/[a-f0-9\-]+/[^"\'\s]*\.m3u8', html)
    if surrit_match:
        return surrit_match.group(0)
    uuid_match = re.search(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', html)
    if uuid_match:
        return f"https://surrit.com/{uuid_match.group(0)}/playlist.m3u8"
    standard_match = re.search(r'source\s*=\s*[\'"]([^\'"]+\.m3u8)[\'"]', html)
    return standard_match.group(1) if standard_match else ""

def parse_video_detail(html: str, url: str, category: str) -> Optional[dict]:
    try:
        code_match = re.search(r'/([A-Za-z0-9]+-\d+)', url)
        code = code_match.group(1).upper() if code_match else "UNKNOWN"

        title_match = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S)
        title = title_match.group(1).strip() if title_match else code

        stream_url = extract_video_stream(html)

        # 磁力链接
        magnets = re.findall(r'magnet:\?xt=urn:btih:[a-zA-Z0-9]{40,}', html)

        # 封面图
        cover_match = re.search(r'<meta property="og:image" content="([^"]+)"', html)
        cover = cover_match.group(1) if cover_match else f"https://fourhoi.com/{code.lower()}/cover-t.jpg"

        # TVBox JSON 单条结构（完全按照你提供的格式）
        vod = {
            "vod_id": code.lower(),
            "vod_name": f"{code} {title} {category}",
            "vod_pic": cover,
            "vod_actor": category,
            "vod_director": "whos.tv",
            "vod_remarks": "HD高清",
            "vod_pubdate": "2026-04-12",
            "vod_area": "日本",
            "vod_year": "2026",
            "vod_tags": [],
            "vod_content": "<p>　　暂无影片详细介绍</p>",
            "vod_play_from": "dytt$$$dyttm3u8",
            "vod_play_url": f"高清${stream_url}" if stream_url else "",
            "type_name": "成人影片",
            "source_page": 1
        }

        # 如果有磁力，追加到播放链接（$$$ 分隔）
        if magnets and stream_url:
            extra = "$$$".join([f"磁力${m}" for m in magnets])
            vod["vod_play_url"] += f"$$${extra}"
            vod["vod_play_from"] += "$$$magnet"

        return {
            "vod": vod,
            "stream_url": stream_url,
            "magnets": magnets,
            "code": code,
            "title": title,
            "cover": cover
        }
    except Exception as e:
        print(f"解析失败 {url}: {e}")
        return None

# ==================== 获取所有女优分类（保持原逻辑） ====================
async def get_all_actresses(scraper, max_list_pages: int):
    print(f"正在获取女优列表（前 {max_list_pages} 页）...")
    actresses = []
    for page in range(1, max_list_pages + 1):
        list_url = f"https://missav.live/cn/actresses?page={page}"
        try:
            resp = await asyncio.to_thread(scraper.get, list_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                break
            html = resp.text
            matches = re.findall(r'<a href="([^"]+/cn/actresses/[^"]+)"[^>]*>([^<]+)</a>', html)
            for link, name in matches:
                full_url = urljoin(BASE_URL, link)
                actresses.append((name.strip(), full_url))
            print(f"  第 {page} 页 → 找到 {len(matches)} 个女优")
        except Exception as e:
            print(f"获取女优列表第 {page} 页失败: {e}")
            break
    return list(dict.fromkeys(actresses))  # 去重

# ==================== 新增：获取所有 Genres 分类 ====================
async def get_all_genres(scraper, max_list_pages: int):
    print(f"正在获取 Genres 分类列表（前 {max_list_pages} 页，共 23 页）...")
    genres = []
    for page in range(1, max_list_pages + 1):
        list_url = f"https://missav.live/cn/genres?page={page}"
        try:
            resp = await asyncio.to_thread(scraper.get, list_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                break
            html = resp.text
            # 专门匹配 Genres 链接（包含 /cn/ 的子分类）
            matches = re.findall(r'<a href="([^"]+/cn/[^"]+)"[^>]*>([^<]+)</a>', html)
            for link, name in matches:
                full_url = link if link.startswith('http') else urljoin(BASE_URL, link)
                name = name.strip()
                # 过滤掉无效链接和导航
                if name and name != '#' and not name.isdigit() and name not in ['观看日本 AV', '素人', '无码影片', '亚洲 AV', '我的收藏']:
                    genres.append((name, full_url))
            print(f"  Genres 第 {page} 页 → 找到 {len(matches)} 个分类")
        except Exception as e:
            print(f"获取 Genres 列表第 {page} 页失败: {e}")
            break
    return list(dict.fromkeys(genres))  # 去重

# ==================== 爬取单个分类（女优或 Genres 通用，实时保存所有格式） ====================
async def crawl_one_category(scraper, category_name: str, category_url: str, txt_file, db, all_vods):
    print(f"\n▶ 开始爬取分类: {category_name}")
    page = 1
    while page <= MAX_VIDEO_PAGES_PER_CATEGORY:
        page_url = f"{category_url}?page={page}"
        try:
            resp = await asyncio.to_thread(scraper.get, page_url, headers=HEADERS, timeout=20)
            if resp.status_code != 200:
                break
            html = resp.text

            links = re.findall(r'href="([^"]*/(?:cn|en)/[A-Za-z0-9]+-\d+)"', html)
            unique_links = list(set(links))
            if not unique_links:
                break

            for link in unique_links:
                full_url = urljoin(BASE_URL, link)
                try:
                    detail_resp = await asyncio.to_thread(scraper.get, full_url, headers=HEADERS, timeout=20)
                    if detail_resp.status_code != 200:
                        continue

                    result = parse_video_detail(detail_resp.text, full_url, category_name)
                    if not result:
                        continue

                    vod = result["vod"]
                    stream_url = result["stream_url"]
                    magnets = result["magnets"]
                    code = result["code"]
                    title = result["title"]
                    cover = result["cover"]

                    # 1. 实时保存到 M3U（IPTV 标准格式，带封面和分组）
                    if stream_url:
                        extinf = f'#EXTINF:-1 tvg-logo="{cover}" group-title="{category_name}",{code} {title}\n'
                        await txt_file.write(extinf + stream_url + "\n")

                    # 2. 实时保存到 SQLite（磁力专用）
                    video_info = VideoInfo(
                        code=code, title=title, url=full_url,
                        video_stream_url=stream_url, magnet_links=magnets,
                        category=category_name, cover=cover
                    )
                    await db.save_video(video_info)

                    # 3. 收集到 JSON 列表
                    all_vods.append(vod)
                    print(f"  [成功] {code}  {category_name}")

                except Exception as e:
                    print(f"  详情失败 {full_url}: {e}")

                await asyncio.sleep(3)  # 防封

            page += 1
        except Exception as e:
            print(f"页面 {page} 请求失败: {e}")
            break

    # 每爬完一个分类，立即更新 JSON
    await save_json(all_vods)

# ==================== 保存 JSON（TVBox 格式） ====================
async def save_json(all_vods: list):
    try:
        data = {"list": all_vods}
        async with aiofiles.open(JSON_PATH, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"  JSON 已实时更新 → 当前共 {len(all_vods)} 条视频")
    except Exception as e:
        print(f"JSON 保存失败: {e}")

# ==================== 主函数 ====================
async def main():
    # 初始化
    db = AsyncDB(os.path.join(OUTPUT_DIR, "missav_data.db"))
    await db.init()

    scraper = cloudscraper.create_scraper()
    # 预热
    try:
        await asyncio.to_thread(scraper.get, BASE_URL, headers=HEADERS, timeout=15)
    except:
        pass

    # 清空或创建 M3U 文件
    async with aiofiles.open(TXT_PATH, "w", encoding="utf-8") as txt_file:
        await txt_file.write("#EXTM3U\n")

    all_vods = []  # 用于 JSON

    async with aiofiles.open(TXT_PATH, "a", encoding="utf-8") as txt_file:
        # 1. 爬取所有女优
        all_actresses = await get_all_actresses(scraper, MAX_ACTRESS_LIST_PAGES)
        print(f"\n✅ 共获取到 {len(all_actresses)} 个女优分类，开始爬取视频...")

        for name, url in all_actresses:
            await crawl_one_category(scraper, name, url, txt_file, db, all_vods)

        # 2. 新增：爬取所有 Genres 分类
        all_genres = await get_all_genres(scraper, MAX_GENRE_LIST_PAGES)
        print(f"\n✅ 共获取到 {len(all_genres)} 个 Genres 分类，开始爬取视频...")

        for name, url in all_genres:
            await crawl_one_category(scraper, name, url, txt_file, db, all_vods)

    print(f"\n🎉 全部完成！（已同时爬取 女优 + Genres）")
    print(f"   • M3U IPTV 文件（TVBox / IPTV 播放器直接使用）: {TXT_PATH}")
    print(f"   • JSON VOD 文件（TVBox 影片库格式）: {JSON_PATH}")
    print(f"   • 磁力数据库: {os.path.join(OUTPUT_DIR, 'missav_data.db')}")
    print(f"   • 共爬取 {len(all_vods)} 条视频（含 m3u8 + 磁力，已实时保存）")

if __name__ == "__main__":
    asyncio.run(main())