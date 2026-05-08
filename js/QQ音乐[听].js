var rule = {
  title: 'QQ音乐',
  host: 'https://cyapi.top',
  url: '',
  searchable: 1,
  quickSearch: 1,
  filterable: 0,
  headers: {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 11)',
    'Referer': 'https://y.qq.com/'
  },

  class_parse: $js.toString(() => {
    input = [
      { type_id: '巅峰榜', type_name: '巅峰榜' },
      { type_id: '地区榜', type_name: '地区榜' },
      { type_id: '特色榜', type_name: '特色榜' },
      { type_id: '网络歌曲榜', type_name: '网络歌曲榜' },
      { type_id: '全球榜', type_name: '全球榜' }
    ];
  }),

  play_parse: true,

  lazy: $js.toString(() => {
    let mid = input;
    let realUrl = '';
    let lyricText = '';
    let coverPic = '';
    let songName = '';
    let artistName = '';
    try {
      let res = JSON.parse(request('https://cyapi.top/API/qq_music.php?apikey=2baf39266d8ef0580aba937245d5bb569fe376f230ff508f1faa0922dc320fe4&mid=' + mid + '&type=json'));
      realUrl = res.url;
      if (res.lyric) {
        lyricText = res.lyric.text;
      }
      if (res.cover) {
        coverPic = res.cover.medium || res.cover.small || '';
      }
      if (res.name) {
        songName = res.name;
      }
      if (res.artists && res.artists.length > 0) {
        artistName = res.artists.map(a => a.name).join('/');
      }
    } catch (e) {}
    input = realUrl ? {
      parse: 0,
      url: realUrl,
      header: rule.headers,
      subtitile: lyricText,
      cover: coverPic,
      title: songName,
      artist: artistName
    } : '';
  }),

  推荐: $js.toString(() => {
    try {
      let list = JSON.parse(request('https://cyapi.top/API/music_hot.php?apikey=2baf39266d8ef0580aba937245d5bb569fe376f230ff508f1faa0922dc320fe4'));
      VODS = list.map(i => ({
        vod_id: i.list_id,
        vod_name: i.list_name,
        vod_pic: i.list_cover,
        vod_remarks: '热度:' + i.hot
      }));
    } catch (e) {
      VODS = [];
    }
  }),

  一级: $js.toString(() => {
    try {
      let list = JSON.parse(request('https://cyapi.top/API/music_hot.php?apikey=2baf39266d8ef0580aba937245d5bb569fe376f230ff508f1faa0922dc320fe4'));
      if (MY_CATE === '巅峰榜') list = list.filter(i => /飙升|热歌|新歌|流行/.test(i.list_name));
      else if (MY_CATE === '地区榜') list = list.filter(i => /内地|香港|台湾/.test(i.list_name));
      else if (MY_CATE === '全球榜') list = list.filter(i => /欧美|韩国|日本|JOOX/.test(i.list_name));
      else if (MY_CATE === '特色榜') list = list.filter(i => /听歌识曲|MV|说唱/.test(i.list_name));
      VODS = list.map(i => ({
        vod_id: i.list_id,
        vod_name: i.list_name,
        vod_pic: i.list_cover,
        vod_remarks: '热度:' + i.hot
      }));
    } catch (e) {
      VODS = [];
    }
  }),

  二级: $js.toString(() => {
    try {
      let list = JSON.parse(request('https://cyapi.top/API/music_hot.php?apikey=2baf39266d8ef0580aba937245d5bb569fe376f230ff508f1faa0922dc320fe4&id=' + orId));
      let playUrls = [];
      for (let i = 0; i < list.length; i++) {
        let s = list[i];
        playUrls.push(s.song_name + '\n' + s.songer_name + '$' + s.song_mid);
      }
      VOD = {
        vod_id: input,
        vod_name: '榜单歌曲',
        vod_pic: list[0].cover,
        vod_remarks: list.length + ' 首歌曲',
        vod_play_from: 'QQ音乐',
        vod_play_url: playUrls.join('#')
      };
    } catch (e) {
      VOD = {
        vod_name: '解析失败',
        vod_play_from: 'QQ音乐',
        vod_play_url: ''
      };
    }
  }),

  搜索: $js.toString(() => {
    try {
      let res = JSON.parse(request('https://c.y.qq.com/soso/fcgi-bin/client_search_cp?p=' + MY_PAGE + '&n=20&w=' + encodeURIComponent(KEY)));
      let list = res.data.song.list;
      VODS = list.map(s => ({
        vod_id: s.songmid,
        vod_name: s.songname,
        vod_pic: 'https://y.gtimg.cn/music/photo_new/T002R300x300M000' + s.albummid + '.jpg',
        vod_remarks: s.singer.map(v => v.name).join('/')
      }));
    } catch (e) {
      VODS = [];
    }
  })
};