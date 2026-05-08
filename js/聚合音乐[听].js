/*
@header({
  searchable: 1,
  filterable: 1,
  quickSearch: 1,
  title: '聚合音乐[听]',
  lang: 'cat'
})
*/


let siteName = '聚合音乐';
let siteKey = '';
let siteType = 0;

// ==================== 平台配置 ====================
const platformList = [
  { name: '网易云音乐', id: 'wangyi' },
  { name: '听海音乐', id: 'tinghai' },
  { name: '米兔音乐', id: 'mitu' }
];

// ==================== URL配置 ====================
const rule = {
  wangyi: {
    host: 'https://ncm.zhenxin.me',
    playApi: 'http://mc.alger.fun/api/song/url/v1',
    lyricApi: 'http://mc.alger.fun/api/lyric',
    searchApi: 'http://mc.alger.fun/api/cloudsearch',
    detail: '/playlist/detail?id=',
    toplist: '/toplist',
    hotPlaylist: '/top/playlist',
    personalized: '/personalized',
    artist: '/artists?id='
  },
  tinghai: {
    host: 'http://wapi.kuwo.cn',
    tagPlaylist: '/api/pc/classify/playlist/getTagPlayList',
    playlistInfo: '/api/www/playlist/playListInfo',
    songUrl: 'https://nmobi.kuwo.cn/mobi.s',
    lyricApi: 'https://kuwo.cn/openapi/v1/www/lyric/getlyric',
    searchApi: 'https://search.kuwo.cn/r.s',
    picApi: 'http://artistpicserver.kuwo.cn/pic.web'
  },
  mitu: {
    host: 'https://www.qqmp3.vip',
    songsApi: '/api/songs.php',
    kwApi: '/api/kw.php'
  }
};

// ==================== 请求头配置 ====================
const headers = {
  'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
};

// ==================== 分类筛选配置 ====================
const filterOptions = {
  wangyi: [{
    key: "area",
    name: "分类",
    value: [
      { "n": "推荐歌单", "v": "recommend" },
      { "n": "排行榜", "v": "toplist" },
      { "n": "热门歌单", "v": "hot" },
      { "n": "热门歌手", "v": "artist" }
    ]
  }],
  tinghai: [{
    key: "area",
    name: "分类",
    value: [
      { "n": "专区", "v": "12" },
      { "n": "主题", "v": "2189" },
      { "n": "心情", "v": "146" },
      { "n": "场景", "v": "376" },
      { "n": "年代", "v": "637" },
      { "n": "曲风流派", "v": "393" },
      { "n": "语言", "v": "37" }
    ]
  }],
  mitu: [{
    key: "area",
    name: "分类",
    value: [
      { "n": "热门", "v": "hot" },
      { "n": "新歌", "v": "new" },
      { "n": "随机", "v": "rand" }
    ]
  }]
};

const ruleFilterDef = {
  wangyi: { area: 'recommend' },
  tinghai: { area: '12' },
  mitu: { area: 'hot' }
};

// ==================== 图片画质提升 ====================
function hd(img) {
  if (!img) return '';
  return img.replace('/120/', '/4000/')
    .replace('/500/', '/2160/')
    .replace('/150/', '/1000/')
    .replace('/300/', '/1500/');
}

// ==================== 初始化 ====================
async function init(cfg) {
  console.log(`【${siteName}】初始化开始`);
  siteKey = cfg.skey || '';
  siteType = cfg.stype || 0;
  return true;
}

// ==================== 首页分类 ====================
function home(filter) {
  const platForms = getPlatList();
  
  const classes = platForms.map(item => ({
    type_name: item.name,
    type_id: item.id
  }));
  
  const filters = {};
  platForms.forEach(item => {
    if (filterOptions[item.id]) filters[item.id] = filterOptions[item.id];
  });
  
  return JSON.stringify({ class: classes, filters: filters });
}

// ==================== 首页推荐 ====================
async function homeVod() {
  const platForms = getPlatList();
  
  const randomPlat = platForms[Math.floor(Math.random() * platForms.length)];
  const randomArea = ruleFilterDef[randomPlat.id]?.area || '';
  
  const categoryResult = await category(randomPlat.id, 1, { area: randomArea }, {});
  const categoryList = JSON.parse(categoryResult).list || [];
  
  return JSON.stringify({
    list: categoryList
  });
}

// ==================== 分类列表 ====================
async function category(tid, pg, filter, extend) {
  const page = pg || 1;
  extend = extend || {};
  
  const platformItem = platformList.find(p => p.id === tid);
  if (!platformItem) {
    return JSON.stringify({ list: [], page, pagecount: 1, limit: 0, total: 0 });
  }
  
  const searchKeyword = extend?.custom;
  if (searchKeyword) {
    return await cfs(tid, searchKeyword, pg);
  }
  
  const area = filter?.area || extend?.area || ruleFilterDef[tid]?.area || '';
  const videos = [];
  
  switch (tid) {
    case 'wangyi':
      videos.push(...await getWangyiList(area, page));
      break;
    case 'tinghai':
      videos.push(...await getTinghaiList(area, page));
      break;
    case 'mitu':
      videos.push(...await getMituList(area, page));
      break;
  }
  
  return JSON.stringify({
    list: videos,
    page: page,
    pagecount: page + 1,
    limit: videos.length,
    total: videos.length * (page + 1)
  });
}

// ==================== 网易云音乐 ====================
async function getWangyiList(type, page) {
  const limit = 20;
  const offset = (page - 1) * limit;
  let videos = [];
  
  try {
    let url = '';
    let rawData = [];
    
    switch (type) {
      case 'recommend':
        url = `${rule.wangyi.host}${rule.wangyi.personalized}?limit=${page * limit}`;
        break;
      case 'toplist':
        url = `${rule.wangyi.host}${rule.wangyi.toplist}`;
        break;
      case 'hot':
        url = `${rule.wangyi.host}${rule.wangyi.hotPlaylist}?limit=${limit}&offset=${offset}`;
        break;
      case 'artist':
        url = `${rule.wangyi.host}/top/artists?limit=${limit}&offset=${offset}`;
        break;
      default:
        return [];
    }
    
    const html = await request(url);
    const json = JSON.parse(html);
    
    if (type === 'recommend') {
      rawData = json.result || [];
      if (page > 1) rawData = rawData.slice(offset);
    } else if (type === 'toplist') {
      rawData = json.list || [];
    } else if (type === 'artist') {
      rawData = json.artists || [];
    } else {
      rawData = json.playlists || [];
    }
    
    videos = rawData.map(item => ({
      vod_id: `wangyi@${type}@${item.id}`,
      vod_name: item.name || '未知歌单',
      vod_pic: (item.coverImgUrl || item.picUrl || item.img1v1Url || 'https://s1.music.126.net/style/favicon.ico') + '?param=300y300',
      vod_remarks: `网易云音乐 | ${item.playCount ? formatNumber(item.playCount) : (item.updateFrequency || '')}`,
      vod_content: item.description || item.briefDesc || ''
    }));
    
  } catch (e) {
    console.log(`【网易云】获取失败: ${e.message}`);
  }
  
  return videos;
}

// ==================== 听海音乐 ====================
async function getTinghaiList(categoryId, page) {
  let videos = [];
  
  try {
    const url = `${rule.tinghai.host}${rule.tinghai.tagPlaylist}?pn=${page}&rn=30&id=${categoryId}`;
    const html = await request(url);
    const json = JSON.parse(html);
    const data = json.data?.data || [];
    
    videos = data.map(item => ({
      vod_id: `tinghai@${categoryId}@${item.id || item.pid}`,
      vod_name: item.name || item.title || '未命名歌单',
      vod_pic: hd(item.img || item.pic || item.cover || ''),
      vod_remarks: `听海音乐 | ${item.listencnt ? formatNumber(item.listencnt) : ''}`,
      vod_content: item.info || item.userName || ''
    }));
    
  } catch (e) {
    console.log(`【听海音乐】获取失败: ${e.message}`);
  }
  
  return videos;
}

// ==================== 米兔音乐 ====================
async function getMituList(type, page) {
  let apiPath = '';
  if (type === 'hot') apiPath = 'api/songs.php';
  else if (type === 'new') apiPath = 'api/songs.php?type=new';
  else apiPath = 'api/songs.php?type=rand';
  
  const url = `${rule.mitu.host}/${apiPath}`;
  let videos = [];
  
  try {
    const html = await request(url);
    const json = JSON.parse(html);
    
    if (json.code === 200 && Array.isArray(json.data)) {
      videos = json.data.map(item => {
        const vodData = {
          id: item.rid,
          name: item.name,
          pic: item.pic,
          artist: item.artist,
          downurl: item.downurl || []
        };
        const vodId = `mitu@${type}@${encodeURIComponent(JSON.stringify(vodData))}`;
        
        return {
          vod_id: vodId,
          vod_name: `${item.name} - ${item.artist}`,
          vod_pic: item.pic || '',
          vod_remarks: `米兔音乐 | ${type === 'hot' ? '热门' : (type === 'new' ? '新歌' : '随机')}`,
          vod_content: `歌手：${item.artist}`
        };
      });
    }
    
  } catch (e) {
    console.log(`【米兔音乐】获取失败: ${e.message}`);
  }
  
  return videos;
}

// ==================== 详情 ====================
async function detail(id) {
  const parts = id.split('@');
  const platform = parts[0];
  const type = parts[1];
  const did = decodeURIComponent(parts.slice(2).join('@'));
  
  let vod = {};
  
  switch (platform) {
    case 'wangyi':
      vod = await getWangyiDetail(type, did);
      break;
    case 'tinghai':
      vod = await getTinghaiDetail(did);
      break;
    case 'mitu':
      vod = await getMituDetail(did);
      break;
  }
  
  return JSON.stringify({ list: [vod] });
}

// 网易云详情 - 按照原版网易云写法
async function getWangyiDetail(type, id) {
  let vod = {};
  
  try {
    let url = '';
    let data = {};
    let tracks = [];
    
    if (type === 'artist') {
      url = `${rule.wangyi.host}${rule.wangyi.artist}${id}`;
      const html = await request(url);
      const json = JSON.parse(html);
      data = json.artist || {};
      tracks = json.hotSongs || [];
      
      const PicUrl = (data.picUrl || data.img1v1Url || '') + '?param=500y500';
      
      const qualities = [["无损", "lossless"], ["极高", "exhigh"], ["标准", "standard"]];
      const playFrom = qualities.map(q => q[0]).join('$$$');
      
      const playPics = tracks.map(s => {
        const pic = s.al?.picUrl || PicUrl;
        return pic ? pic + '?param=300y300' : PicUrl;
      });
      
      const playUrl = qualities.map(q => 
        tracks.map(s => `${s.name} - ${s.ar?.map(a => a.name).join('/') || ''}$${s.id}|${q[1]}&&${playPics[tracks.indexOf(s)]}`).join('#')
      ).join('$$$');
      
      vod = {
        vod_id: id,
        vod_name: data.name || '未知歌手',
        vod_pic: PicUrl,
        vod_content: data.briefDesc || data.name,
        vod_remarks: `共${tracks.length}首`,
        vod_play_from: playFrom,
        vod_play_url: playUrl,
        vod_play_pic_ratio: 1.0
      };
      
    } else {
      url = `${rule.wangyi.host}${rule.wangyi.detail}${id}`;
      const html = await request(url);
      const json = JSON.parse(html);
      const playlist = json.playlist || {};
      data = playlist;
      tracks = playlist.tracks || [];
      
      const PicUrl = (data.coverImgUrl || data.picUrl || '') + '?param=500y500';
      
      const qualities = [["无损", "lossless"], ["极高", "exhigh"], ["标准", "standard"]];
      const playFrom = qualities.map(q => q[0]).join('$$$');
      
      const playPics = tracks.map(s => {
        const pic = s.al?.picUrl || PicUrl;
        return pic ? pic + '?param=300y300' : PicUrl;
      });
      
      const playUrl = qualities.map(q => 
        tracks.map(s => `${s.name} - ${s.ar?.map(a => a.name).join('/') || ''}$${s.id}|${q[1]}&&${playPics[tracks.indexOf(s)]}`).join('#')
      ).join('$$$');
      
      vod = {
        vod_id: id,
        vod_name: data.name || '未知歌单',
        vod_pic: PicUrl,
        vod_content: data.description || data.name,
        vod_remarks: `${formatNumber(data.playCount || 0)} | 共${tracks.length}首`,
        vod_play_from: playFrom,
        vod_play_url: playUrl,
        vod_play_pic_ratio: 1.0
      };
    }
    
  } catch (e) {
    console.log(`【网易云详情】失败: ${e.message}`);
  }
  
  return vod;
}

// 听海详情
async function getTinghaiDetail(id) {
  let vod = {};
  
  try {
    const limit = 100;
    let baseUrl = `${rule.tinghai.host}${rule.tinghai.playlistInfo}?pid=${id}&rn=${limit}&httpsStatus=1&pn=`;
    
    let html = await request(baseUrl + '1');
    let json = JSON.parse(html);
    let data = json.data || {};
    let songs = data.musicList || data.musiclist || [];
    let total = parseInt(data.total || 0);
    
    if (total > limit) {
      let tasks = [];
      for (let p = 2; p <= Math.min(Math.ceil(total / limit), 5); p++) {
        tasks.push(request(baseUrl + p));
      }
      let results = await Promise.all(tasks);
      results.forEach(r => {
        let d = JSON.parse(r).data || {};
        songs = songs.concat(d.musicList || d.musiclist || []);
      });
    }
    
    let playArr = [];
    let songPicArr = [];
    
    songs.forEach(it => {
      let rid = (it.rid || it.musicrid || '').toString().replace('MUSIC_', '');
      let song = (it.name || '').replace(/&nbsp;/g, ' ');
      let artist = (it.artist || '').replace(/&nbsp;/g, ' ');
      let albumpic = hd(it.albumpic || it.pic);
      let displayName = artist ? `${song} [${artist}]` : song;
      
      if (rid) {
        playArr.push(`${displayName}$${rid}&&${albumpic}&&${albumpic}`);
        songPicArr.push(albumpic);
      }
    });
    
    vod = {
      vod_id: id,
      vod_name: data.name || '听海歌单',
      vod_pic: hd(data.img || data.img500),
      vod_content: data.info || '',
      vod_remarks: `共${songs.length}首`,
      vod_play_from: "听海音乐",
      vod_play_url: playArr.join('#'),
      vod_play_pic: songPicArr.join('#'),
      vod_play_pic_ratio: 1.0
    };
    
  } catch (e) {
    console.log(`【听海详情】失败: ${e.message}`);
  }
  
  return vod;
}

// 米兔详情
async function getMituDetail(encodedData) {
  let vod = {};
  
  try {
    const songData = JSON.parse(encodedData);
    const { id: rid, name, pic, artist, downurl } = songData;
    
    let playUrl = '';
    let rawLrc = '暂无歌词';
    
    const res = await request(`${rule.mitu.host}${rule.mitu.kwApi}?rid=${rid}&type=json&level=exhigh&lrc=true`);
    const data = JSON.parse(res);
    
    if (data.code === 200 && data.data) {
      playUrl = data.data.url || '';
      rawLrc = data.data.lrc || '暂无歌词';
    }
    
    const displayLrc = rawLrc === '暂无歌词' ? rawLrc : rawLrc.replace(/\[\d{2}:\d{2}\.\d{2}\]/g, '\n');
    
    let playFrom = [];
    let playUrls = [];
    
    if (playUrl) {
      playFrom.push('在线播放');
      playUrls.push(`第1集$${JSON.stringify({ url: playUrl, lrc: rawLrc, cover: pic })}`);
    }
    
    if (downurl && downurl.length) {
      playFrom.push('网盘下载');
      const downUrls = downurl.map(item => {
        const [name, url] = item.split('$$');
        return `${name}$push://${url}`;
      }).join('#');
      playUrls.push(downUrls);
    }
    
    vod = {
      vod_id: rid,
      vod_name: name,
      vod_pic: pic,
      vod_content: displayLrc,
      vod_actor: artist,
      vod_play_from: playFrom.join('$$$'),
      vod_play_url: playUrls.join('$$$')
    };
    
  } catch (e) {
    console.log(`【米兔详情】失败: ${e.message}`);
  }
  
  return vod;
}

// ==================== 播放 ====================
async function play(flag, id, flags) {
  if (flag.includes('网易云') || flag.includes('无损') || flag.includes('极高') || flag.includes('标准')) {
    return await playWangyi(id);
  }
  
  if (flag.includes('听海')) {
    return await playTinghai(id);
  }
  
  if (flag.includes('网盘下载')) {
    return JSON.stringify({ parse: 0, url: id });
  }
  
  if (flag.includes('在线播放')) {
    return await playMitu(id);
  }
  
  return JSON.stringify({ parse: 0, url: id });
}

// 网易云播放
async function playWangyi(id) {
  try {
    const [musicId, quality] = id.split('|');
    const url = `${rule.wangyi.playApi}?id=${musicId}&level=${quality}`;
    const res = await request(url);
    const json = JSON.parse(res);
    const songData = json.data?.[0] || (Array.isArray(json) && json[0]) || json || {};
    
    const lyricRes = await request(`${rule.wangyi.lyricApi}?id=${musicId}`);
    const lyricJson = JSON.parse(lyricRes);
    const lyric = lyricJson.lrc?.lyric || '';
    
    const infoRes = await request(`${rule.wangyi.host}/song/detail?ids=${musicId}`);
    const infoJson = JSON.parse(infoRes);
    const cover = infoJson.songs?.[0]?.al?.picUrl + '?param=500y500' || songData.pic || '';
    
    return JSON.stringify({
      parse: 0,
      url: songData.url || '',
      header: headers,
      lrc: lyric,
      cover: cover,
      pic: cover,
      height: 720
    });
    
  } catch (e) {
    console.log(`【网易云播放】失败: ${e.message}`);
    return JSON.stringify({ parse: 0, url: id });
  }
}

// 听海播放
async function playTinghai(id) {
  try {
    const parts = id.split('&&');
    const firstPart = parts[0] || '';
    const firstParts = firstPart.split('$');
    const songId = firstParts.length > 1 ? firstParts[1] : firstParts[0];
    const albumPic = hd(parts[1]);
    
    let url = await getTinghaiSongUrl(songId, '320kmp3');
    if (!url) url = await getTinghaiSongUrl(songId, '128kmp3');
    
    let lrc = await getTinghaiLyric(songId);
    
    let picUrl = albumPic;
    if (!picUrl) {
      try {
        let picRes = await request(`${rule.tinghai.picApi}?type=rid_pic&pictype=url&size=500&rid=${songId}`);
        picUrl = picRes.trim().replace('/500/', '/2160/');
      } catch (e) {}
    }
    
    const result = {
      parse: 0,
      url: url || '',
      header: headers,
      height: 720
    };
    
    if (picUrl) {
      result.pic = picUrl;
      result.cover = picUrl;
    }
    
    if (lrc && lrc !== '暂无歌词') {
      result.lrc = lrc;
    }
    
    return JSON.stringify(result);
    
  } catch (e) {
    console.log(`【听海播放】失败: ${e.message}`);
    return JSON.stringify({ parse: 0, url: id });
  }
}

async function getTinghaiSongUrl(rid, br) {
  const url = `${rule.tinghai.songUrl}?f=web&user=0&source=kwplayer_ar_4.4.2.7_B_nuoweida_vh.apk&type=convert_url_with_sign&rid=${rid}&format=flac&br=${br}`;
  const html = await request(url);
  const json = JSON.parse(html);
  return json?.data?.url?.trim() || '';
}

async function getTinghaiLyric(rid) {
  const maxRetries = 20;
  
  for (let i = 0; i < maxRetries; i++) {
    try {
      const url = `${rule.tinghai.lyricApi}?musicId=${rid}`;
      const html = await request(url);
      
      if (html) {
        const json = JSON.parse(html);
        
        if (json.code === 200 && json.data && json.data.lrclist && json.data.lrclist.length > 0) {
          const lrclist = json.data.lrclist;
          
          const lyric = lrclist.map(item => {
            const time = parseFloat(item.time) || 0;
            const min = Math.floor(time / 60).toString().padStart(2, '0');
            const sec = Math.floor(time % 60).toString().padStart(2, '0');
            const ms = Math.floor((time % 1) * 100).toString().padStart(2, '0');
            return `[${min}:${sec}.${ms}]${item.lineLyric || ''}`;
          }).join('\n');
          
          return lyric;
        }
      }
    } catch (e) {}
    
    if (i < maxRetries - 1) await sleep(0.01);
  }
  
  return '暂无歌词';
}

// 米兔播放
async function playMitu(id) {
  try {
    const playData = JSON.parse(id);
    let subt;
    
    if (playData.lrc && playData.lrc !== '暂无歌词') {
      subt = 'data:text/plain;charset=utf-8,' + encodeURIComponent(playData.lrc);
    }
    
    return JSON.stringify({
      parse: 0,
      url: playData.url,
      header: headers,
      lrc: playData.lrc,
      subt,
      cover: playData.cover,
      pic: playData.cover,
      height: 720
    });
    
  } catch (e) {
    console.log(`【米兔播放】失败: ${e.message}`);
    return JSON.stringify({ parse: 0, url: id });
  }
}

// ==================== 搜索 ====================
async function cfs(siteId, wd, pg) {
  const page = pg || 1;
  let results = [];
  
  if (siteId === 'wangyi') {
    results = await searchWangyi(wd);
  } else if (siteId === 'tinghai') {
    results = await searchTinghai(wd, page);
  } else if (siteId === 'mitu') {
    results = await searchMitu(wd);
  }
  
  return JSON.stringify({
    list: results,
    page: page,
    pagecount: page + 1,
    limit: results.length,
    total: results.length * (page + 1)
  });
}

async function search(wd, quick, pg) {
  const videos = [];
  const page = pg || 1;
  
  const searchPromises = [
    cfs('wangyi', wd, page),
    cfs('tinghai', wd, page),
    cfs('mitu', wd, page)
  ];
  
  const searchResults = await Promise.all(searchPromises);
  searchResults.forEach(result => {
    videos.push(...JSON.parse(result).list || []);
  });
  
  const filteredResults = videos.filter(item => 
    (item.vod_name || '').toLowerCase().includes(wd.toLowerCase())
  );
  
  return JSON.stringify({
    list: filteredResults,
    page: page,
    pagecount: page + 1,
    limit: filteredResults.length,
    total: filteredResults.length * (page + 1)
  });
}

// 网易云搜索
async function searchWangyi(wd) {
  const results = [];
  const searchTypes = [
    { type: 1, prefix: 'wangyi@song@', remark: '歌曲', key: 'songs' },
    { type: 1000, prefix: 'wangyi@playlist@', remark: '歌单', key: 'playlists' },
    { type: 100, prefix: 'wangyi@artist@', remark: '歌手', key: 'artists' }
  ];
  
  try {
    for (const st of searchTypes) {
      const url = `${rule.wangyi.searchApi}?keywords=${encodeURIComponent(wd)}&type=${st.type}`;
      const res = await request(url);
      const json = JSON.parse(res);
      
      if (json.result?.[st.key]) {
        for (const item of json.result[st.key]) {
          const result = {
            vod_id: `${st.prefix}${item.id}`,
            vod_name: item.name,
            vod_remarks: st.remark,
            vod_pic: ''
          };
          
          if (st.type === 1) {
            if (item.ar) result.vod_name += ' - ' + item.ar.map(a => a.name).join('/');
            if (item.al?.picUrl) result.vod_pic = item.al.picUrl + '?param=300y300';
          } else if (st.type === 1000) {
            if (item.coverImgUrl) result.vod_pic = item.coverImgUrl + '?param=300y300';
            result.vod_remarks += ` | ${formatNumber(item.playCount || 0)}`;
          } else if (st.type === 100) {
            const picUrl = item.picUrl || item.img1v1Url;
            if (picUrl) result.vod_pic = picUrl + '?param=300y300';
          }
          
          results.push(result);
        }
      }
    }
  } catch (e) {
    console.log(`【网易云搜索】失败: ${e.message}`);
  }
  
  return results;
}

// 听海搜索
async function searchTinghai(wd, page) {
  const results = [];
  const offset = (page - 1) * 30;
  const url = `${rule.tinghai.searchApi}?client=kt&all=${encodeURIComponent(wd)}&pn=${offset}&rn=30&vipver=1&ft=music&encoding=utf8&rformat=json&mobi=1`;
  
  try {
    let html = '';
    let retry = 0;
    while (!html && retry < 3) {
      html = await request(url);
      if (!html) await sleep(0.1);
      retry++;
    }
    
    if (html) {
      const json = JSON.parse(html.replace(/'/g, '"'));
      
      if (json.abslist) {
        json.abslist.forEach(it => {
          const rid = it.DC_TARGETID || it.MUSICRID?.replace('MUSIC_', '') || '';
          const pic = it.web_albumpic_short ? `http://img1.kuwo.cn/star/albumcover/${it.web_albumpic_short}` : (it.hts_MVPIC || '');
          
          results.push({
            vod_id: `tinghai@song@${rid}`,
            vod_name: `${it.SONGNAME || it.NAME || '未知歌曲'} - ${it.ARTIST || '未知歌手'}`,
            vod_pic: hd(pic),
            vod_remarks: it.ALBUM || '听海音乐'
          });
        });
      }
    }
  } catch (e) {
    console.log(`【听海搜索】失败: ${e.message}`);
  }
  
  return results;
}

// 米兔搜索
async function searchMitu(wd) {
  const results = [];
  const url = `${rule.mitu.host}/api/songs.php?type=search&keyword=${encodeURIComponent(wd)}`;
  
  try {
    const html = await request(url);
    const json = JSON.parse(html);
    
    if (json.code === 200 && Array.isArray(json.data)) {
      json.data.forEach(item => {
        const vodData = {
          id: item.rid,
          name: item.name,
          pic: item.pic,
          artist: item.artist,
          downurl: item.downurl || []
        };
        
        results.push({
          vod_id: `mitu@song@${encodeURIComponent(JSON.stringify(vodData))}`,
          vod_name: `${item.name} - ${item.artist}`,
          vod_pic: item.pic || '',
          vod_remarks: '米兔音乐'
        });
      });
    }
  } catch (e) {
    console.log(`【米兔搜索】失败: ${e.message}`);
  }
  
  return results;
}

// ==================== 工具函数 ====================
function getPlatList() {
  return platformList;
}

async function request(url, options = {}) {
  try {
    console.log(`【${siteName}】${options.method || 'GET'} ${url.split('?')[0]}`);
    
    const requestConfig = {
      method: options.method || 'GET',
      headers: { ...headers, ...options.headers },
      timeout: options.timeout || 10000
    };
    
    if (options.data) {
      if (typeof options.data === 'string') {
        requestConfig.body = options.data;
      } else {
        const contentType = requestConfig.headers['Content-Type'] || '';
        if (contentType.includes('json')) {
          requestConfig.body = JSON.stringify(options.data);
        } else {
          const parts = [];
          for (const key in options.data) {
            parts.push(encodeURIComponent(key) + '=' + encodeURIComponent(options.data[key]));
          }
          requestConfig.body = parts.join('&');
        }
      }
    }
    
    const res = await req(url, requestConfig);
    return res.content || '';
  } catch (e) {
    console.log(`【${siteName}】请求失败: ${e.message}`);
    return '';
  }
}

function formatNumber(num) {
  if (!num) return '0';
  if (num >= 10000) {
    return (num / 10000).toFixed(1) + '万';
  }
  return num.toString();
}

function sleep(seconds) {
  return new Promise(resolve => setTimeout(resolve, seconds * 1000));
}

// ==================== 导出 ====================
export function __jsEvalReturn() {
  return {
    init: init,
    home: home,
    homeVod: homeVod,
    category: category,
    detail: detail,
    play: play,
    search: search,
    cfs: cfs
  };
}