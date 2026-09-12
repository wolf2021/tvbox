# 资源管理_lite.py - 精简版
# 两分类：视频目录 + 最近播放
# 固定自然排序升序，自动加载同名弹幕，文件夹封面，播放历史记录

import os
import re
import json
import base64
import time
import urllib.parse
from base.spider import Spider

print("✅ 资源管理_精简版 加载成功")

# ==================== 目录配置 ====================
ROOT_PATH = '/storage/emulated/0/'
SCAN_PATHS = [
    '/storage/emulated/0/',
]
VIDEO_SCAN_DEPTH = 4  # 视频目录扫描深度

VIDEO_ICON_URL = 'https://img0.baidu.com/it/u=3801173794,2209343305&fm=253&fmt=auto&app=138&f=PNG?w=500&h=500'
FOLDER_ICON_URL = 'https://img2.baidu.com/it/u=551272933,781657751&fm=253&fmt=auto&app=138&f=PNG?w=607&h=457'
LOCAL_VIDEO_ICON = '/storage/emulated/0/.icons/video.png'
LOCAL_FOLDER_ICON = '/storage/emulated/0/.icons/folder.png'
HISTORY_FILE = '/storage/emulated/0/.resource_lite_history.json'


class Spider(Spider):

    def getName(self):
        return "本地资源管理"

    def init(self, extend=""):
        super().init(extend)
        self.root_path = ROOT_PATH
        self.scan_paths = SCAN_PATHS
        self.media_exts = ['mp4', 'mkv', 'avi', 'rmvb', 'mov', 'wmv', 'flv', 'm4v', 'm3u8']
        self.danmaku_exts = ['xml', 'ass', 'ssa', 'srt', 'vtt']
        self.image_exts = {'jpg', 'jpeg', 'png', 'webp', 'bmp', 'gif'}
        self.cover_names = ['poster', 'cover', 'folder', 'thumb', 'fanart', 'default', 'landscape']
        self.FOLDER_PREFIX = 'folder://'
        self.VFOLDER_PREFIX = 'vfolder://'
        self.dir_cache = {}
        self.dir_cache_time = {}
        self.video_dirs_cache = None
        self.video_dirs_cache_time = 0
        self.play_history = []
        self._load_history()

    def _get_video_icon(self):
        """优先用本地图标，没有就用网络"""
        try:
            if os.path.exists(LOCAL_VIDEO_ICON):
                return f"file://{LOCAL_VIDEO_ICON}"
        except:
            pass
        return VIDEO_ICON_URL

    def _get_folder_icon(self):
        """优先用本地图标，没有就用网络"""
        try:
            if os.path.exists(LOCAL_FOLDER_ICON):
                return f"file://{LOCAL_FOLDER_ICON}"
        except:
            pass
        return FOLDER_ICON_URL

    # ==================== 工具方法 ====================

    def _load_history(self):
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, 'r') as f:
                    self.play_history = json.load(f)
        except:
            self.play_history = []

    def _save_history(self):
        try:
            with open(HISTORY_FILE, 'w') as f:
                json.dump(self.play_history, f, ensure_ascii=False)
        except:
            pass

    def _add_play_history(self, file_path, name):
        # 去重：已存在的先删掉
        self.play_history = [h for h in self.play_history if h.get('path') != file_path]
        # 加到最前面
        self.play_history.insert(0, {
            'path': file_path,
            'name': name,
            'time': time.time()
        })
        # 最多保留 50 条
        if len(self.play_history) > 50:
            self.play_history = self.play_history[:50]
        self._save_history()

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

    def is_media_file(self, ext):
        return ext in self.media_exts

    def get_file_icon(self, ext, is_dir=False):
        if is_dir:
            return '📁'
        if ext in self.media_exts:
            return '🎬'
        return '📄'

    def _find_cover_image(self, dir_path):
        """在目录中查找封面图片，返回 file:// URL 或 None"""
        try:
            if not os.path.isdir(dir_path):
                return None
            files_by_name = {}
            image_files = []
            for name in os.listdir(dir_path):
                if name.startswith('.') or name in ['.', '..']:
                    continue
                ext = self.get_file_ext(name)
                if ext not in self.image_exts:
                    continue
                full_path = os.path.join(dir_path, name)
                if not os.path.isfile(full_path):
                    continue
                name_no_ext = os.path.splitext(name)[0].lower()
                files_by_name[name_no_ext] = full_path
                image_files.append((name_no_ext, full_path))
            for cname in self.cover_names:
                if cname in files_by_name:
                    return f"file://{files_by_name[cname]}"
            if image_files:
                return f"file://{image_files[0][1]}"
            return None
        except:
            return None

    # ==================== 首页 ====================

    def homeContent(self, filter_):
        classes = [
            {"type_id": "video_scan", "type_name": "📺 视频目录大全"},
            {"type_id": "recent_played", "type_name": "🕐 最近播放记录"},
        ]
        return {'class': classes, 'filters': {}}

    # ==================== 分类内容 ====================

    def categoryContent(self, tid, pg, filter_, extend):
        pg = int(pg) if pg else 1

        if tid == "video_scan":
            return self._video_scan_content(pg)
        if tid == "recent_played":
            return self._recent_played_content(pg)
        if tid == "clear_history":
            self.play_history = []
            self._save_history()
            return self._recent_played_content(1)

        # 解析当前路径
        current_path = None
        from_video_scan = False

        if tid.startswith("root_"):
            current_path = self.root_path
        elif tid.startswith(self.VFOLDER_PREFIX):
            current_path = self.b64u_decode(tid[len(self.VFOLDER_PREFIX):])
            from_video_scan = True
        elif tid.startswith(self.FOLDER_PREFIX):
            current_path = self.b64u_decode(tid[len(self.FOLDER_PREFIX):])
        elif os.path.exists(tid):
            current_path = tid

        if not current_path or not os.path.isdir(current_path):
            return {'list': [], 'page': pg, 'pagecount': 1}

        return self._browse_directory(current_path, pg, from_video_scan)

    # ==================== 目录浏览 ====================

    def _browse_directory(self, current_path, pg, from_video_scan=False):
        cache_key = f"dir_{current_path}"
        if cache_key in self.dir_cache and time.time() - self.dir_cache_time.get(cache_key, 0) < 3600:
            files = self.dir_cache[cache_key]
        else:
            files = self.scan_directory(current_path)
            self.dir_cache[cache_key] = files
            self.dir_cache_time[cache_key] = time.time()

        # 只显示视频文件和文件夹
        files = [f for f in files if f['is_dir'] or self.is_media_file(f.get('ext', ''))]

        # 固定自然排序升序
        files.sort(key=lambda f: (not f['is_dir'], self._natural_sort_key(f['name'])))

        total = len(files)
        per_page = 500
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_files = files[start:end]

        vlist = []
        parent_item = self._create_parent_item(current_path, from_video_scan)
        if parent_item:
            vlist.append(parent_item)

        for f in page_files:
            item = self._create_file_item(f, from_video_scan)
            if item:
                vlist.append(item)

        pagecount = (total + per_page - 1) // per_page if total > 0 else 1
        return {
            'list': vlist,
            'page': pg,
            'pagecount': pagecount,
            'limit': per_page,
            'total': total
        }

    # ==================== 视频目录自动扫描 ====================

    def _recent_played_content(self, pg):
        """最近播放：从播放历史中列出视频"""
        per_page = 50
        total = len(self.play_history)
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_items = self.play_history[start:end]

        vlist = []
        # 顶部放清除按钮（只在第一页显示）
        if pg == 1 and total > 0:
            vlist.append({
                'vod_id': 'clear_history',
                'vod_name': '🗑️ 清除播放记录',
                'vod_pic': self._get_folder_icon(),
                'vod_remarks': f'共{total}条记录',
                'style': {'type': 'list'}
            })
        for h in page_items:
            path = h.get('path', '')
            name = h.get('name', '')
            play_time = h.get('time', 0)
            exists = os.path.exists(path)
            if play_time:
                t_str = time.strftime('%m-%d %H:%M', time.localtime(play_time))
            else:
                t_str = ''
            vlist.append({
                'vod_id': path,
                'vod_name': f"🎬 {name}",
                'vod_pic': self._get_video_icon(),
                'vod_remarks': t_str if exists else '已失效',
                'style': {'type': 'list'}
            })

        pagecount = (total + per_page - 1) // per_page if total > 0 else 1
        if not vlist or (pg == 1 and total == 0):
            vlist = [{
                'vod_id': 'recent_played',
                'vod_name': '🕐 暂无播放记录',
                'vod_pic': self._get_folder_icon(),
                'vod_remarks': '播放视频后会自动记录',
                'style': {'type': 'list'}
            }]
        return {'list': vlist, 'page': pg, 'pagecount': pagecount, 'limit': per_page, 'total': total}

    def _video_scan_content(self, pg):
        if self.video_dirs_cache is None or time.time() - self.video_dirs_cache_time > 1800:
            video_dirs = []
            for scan_path in self.scan_paths:
                if os.path.exists(scan_path):
                    self._scan_video_dirs(scan_path, video_dirs, depth=0)
            self.video_dirs_cache = video_dirs
            self.video_dirs_cache_time = time.time()
        else:
            video_dirs = list(self.video_dirs_cache)

        # 固定自然排序升序
        video_dirs.sort(key=lambda x: self._natural_sort_key(x['name']))

        total = len(video_dirs)
        per_page = 200
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_dirs = video_dirs[start:end]

        vlist = []
        for d in page_dirs:
            cover = d.get('cover') or self._get_folder_icon()
            vlist.append({
                'vod_id': self.VFOLDER_PREFIX + self.b64u_encode(d['path']),
                'vod_name': f"📁 {d['name']}",
                'vod_pic': cover,
                'vod_remarks': f"{d['video_count']}个视频",
                'style': {'type': 'grid', 'ratio': 1}
            })

        pagecount = (total + per_page - 1) // per_page if total > 0 else 1
        return {
            'list': vlist,
            'page': pg,
            'pagecount': pagecount,
            'limit': per_page,
            'total': total
        }

    def _scan_video_dirs(self, dir_path, results, depth):
        if depth > VIDEO_SCAN_DEPTH:
            return
        try:
            if not os.path.isdir(dir_path):
                return
            entries = os.listdir(dir_path)
            video_count = 0
            subdirs = []
            for name in entries:
                if name.startswith('.') or name in ['.', '..']:
                    continue
                full_path = os.path.join(dir_path, name)
                if os.path.isdir(full_path):
                    subdirs.append((name, full_path))
                else:
                    ext = self.get_file_ext(name)
                    if self.is_media_file(ext):
                        video_count += 1
            if video_count > 0:
                dir_name = os.path.basename(dir_path.rstrip('/')) or dir_path
                cover = self._find_cover_image(dir_path)
                results.append({
                    'name': dir_name,
                    'path': dir_path,
                    'video_count': video_count,
                    'mtime': os.path.getmtime(dir_path) if os.path.exists(dir_path) else 0,
                    'cover': cover,
                })
            for name, full_path in subdirs:
                self._scan_video_dirs(full_path, results, depth + 1)
        except:
            pass

    # ==================== 目录扫描 ====================

    def scan_directory(self, dir_path):
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                return []
            files = []
            for name in os.listdir(dir_path):
                if name.startswith('.') or name in ['.', '..']:
                    continue
                full_path = os.path.join(dir_path, name)
                is_dir = os.path.isdir(full_path)
                files.append({
                    'name': name,
                    'path': full_path,
                    'is_dir': is_dir,
                    'ext': self.get_file_ext(name) if not is_dir else '',
                    'mtime': os.path.getmtime(full_path) if not is_dir else 0,
                })
            return files
        except:
            return []

    def collect_videos_in_dir(self, dir_path):
        """递归收集目录及子目录中的所有视频文件"""
        videos = []
        try:
            self._collect_videos_recursive(dir_path, videos, depth=0)
            videos.sort(key=lambda v: self._natural_sort_key(v['name']))
        except:
            pass
        return videos

    def _collect_videos_recursive(self, dir_path, videos, depth):
        if depth > 3:
            return
        try:
            for name in os.listdir(dir_path):
                if name.startswith('.') or name in ['.', '..']:
                    continue
                full_path = os.path.join(dir_path, name)
                if os.path.isfile(full_path):
                    ext = self.get_file_ext(name)
                    if self.is_media_file(ext):
                        videos.append({
                            'name': name,
                            'path': full_path,
                            'ext': ext,
                            'mtime': os.path.getmtime(full_path)
                        })
                elif os.path.isdir(full_path):
                    self._collect_videos_recursive(full_path, videos, depth + 1)
        except:
            pass

    # ==================== 创建文件项 ====================

    def _create_parent_item(self, current_path, from_video_scan=False):
        parent = os.path.dirname(current_path)
        if os.path.normpath(current_path) == os.path.normpath(self.root_path.rstrip('/')):
            return None
        if not parent or parent == current_path:
            return None

        if os.path.normpath(parent) == os.path.normpath(self.root_path.rstrip('/')):
            if from_video_scan:
                parent_id = "video_scan"
                parent_name = "视频目录"
            else:
                parent_id = "root_0"
                parent_name = "根目录"
        else:
            if from_video_scan:
                parent_id = self.VFOLDER_PREFIX + self.b64u_encode(parent)
            else:
                parent_id = self.FOLDER_PREFIX + self.b64u_encode(parent)
            parent_name = os.path.basename(parent)

        return {
            'vod_id': parent_id,
            'vod_name': f'⬅️ 返回 {parent_name}',
            'vod_pic': self._get_folder_icon(),
            'vod_remarks': '',
            'style': {'type': 'list'}
        }

    def _create_file_item(self, f, from_video_scan=False):
        icon = self.get_file_icon(f['ext'], f['is_dir'])
        if f['is_dir']:
            prefix = self.VFOLDER_PREFIX if from_video_scan else self.FOLDER_PREFIX
            cover = self._find_cover_image(f['path']) or self._get_folder_icon()
            return {
                'vod_id': prefix + self.b64u_encode(f['path']),
                'vod_name': f"{icon} {f['name']}",
                'vod_pic': cover,
                'vod_remarks': '文件夹',
                'style': {'type': 'grid', 'ratio': 1}
            }
        if self.is_media_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"{icon} {f['name']}",
                'vod_pic': self._get_video_icon(),
                'vod_remarks': '视频',
                'style': {'type': 'grid', 'ratio': 1}
            }
        return {
            'vod_id': f['path'],
            'vod_name': f"{icon} {f['name']}",
            'vod_pic': self._get_folder_icon(),
            'vod_remarks': f['ext'].upper() if f['ext'] else '文件',
            'style': {'type': 'grid', 'ratio': 1}
        }

    # ==================== 详情页 ====================

    def detailContent(self, ids):
        id_val = ids[0]

        # 特殊分类ID → 转到categoryContent处理
        if id_val == 'video_scan' or id_val == 'recent_played' or id_val == 'clear_history' or id_val.startswith('root_'):
            return self.categoryContent(id_val, 1, None, None)

        # 文件夹前缀 → 直接返回播放列表（不进目录浏览）
        if id_val.startswith(self.FOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.FOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self._folder_play_list(folder_path, from_video_scan=False)
            return {'list': []}

        if id_val.startswith(self.VFOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.VFOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self._folder_play_list(folder_path, from_video_scan=True)
            return {'list': []}

        if '#' in id_val:
            id_val = id_val.split('#', 1)[0]

        if not os.path.exists(id_val):
            return {'list': []}

        if os.path.isdir(id_val):
            return self._folder_play_list(id_val)

        return self._handle_file_detail(id_val)

    def _folder_play_list(self, folder_path, from_video_scan=False):
        """点击文件夹 → 返回该目录所有视频的播放列表"""
        all_videos = self.collect_videos_in_dir(folder_path)
        if not all_videos:
            if from_video_scan:
                tid = self.VFOLDER_PREFIX + self.b64u_encode(folder_path)
            else:
                tid = self.FOLDER_PREFIX + self.b64u_encode(folder_path)
            return self.categoryContent(tid, 1, None, None)

        folder_name = os.path.basename(folder_path)
        total = len(all_videos)

        play_urls = [f"{os.path.splitext(v['name'])[0]}$file://{v['path']}" for v in all_videos]

        vod = {
            'vod_id': folder_path,
            'vod_name': f"🎬 {folder_name}",
            'vod_pic': self._get_folder_icon(),
            'vod_play_from': '本地播放',
            'vod_play_url': '#'.join(play_urls),
            'vod_remarks': f'共{total}集',
            'style': {'type': 'list'}
        }

        return {'list': [vod]}

    def _handle_file_detail(self, file_path):
        name = os.path.basename(file_path)
        ext = self.get_file_ext(name)
        play_name = os.path.splitext(name)[0]

        vod = {
            'vod_id': file_path,
            'vod_name': f"🎬 {name}",
            'vod_pic': self._get_video_icon() if self.is_media_file(ext) else self._get_folder_icon(),
            'vod_play_from': '本地播放',
            'vod_play_url': f"{play_name}$file://{file_path}",
            'vod_remarks': ext.upper() if ext else '文件',
            'style': {'type': 'list'}
        }

        return {'list': [vod]}

    # ==================== 播放 ====================

    def playerContent(self, flag, id, vipFlags):
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

        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", "Accept": "*/*"}
        result = {"parse": 0, "playUrl": "", "url": url, "header": headers}

        if url.startswith('file://'):
            file_path = urllib.parse.unquote(url[7:])
            if os.path.exists(file_path) and self.is_media_file(self.get_file_ext(file_path)):
                # 记录播放历史
                self._add_play_history(file_path, os.path.basename(file_path))
                # 查找同名弹幕
                danmaku_path = self._find_local_danmaku_file(file_path)
                if danmaku_path:
                    result["danmaku"] = [{"url": f"file://{danmaku_path}", "name": os.path.basename(danmaku_path)}]

        return result

    # ==================== 排序方法 ====================

    @staticmethod
    def _natural_sort_key(s):
        parts = re.split(r'(\d+)', str(s).lower())
        result = []
        for part in parts:
            if part.isdigit():
                result.append((0, int(part)))
            else:
                result.append((1, part))
        return result

    # ==================== 弹幕查找 ====================

    def _find_local_danmaku_file(self, video_path):
        try:
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0].lower()
            if not os.path.isdir(video_dir):
                return None
            danmaku_exts_set = set(self.danmaku_exts)
            exact_match = None
            fuzzy_match = None
            for name in os.listdir(video_dir):
                if name.startswith('.') or name in ['.', '..']:
                    continue
                name_no_ext = os.path.splitext(name)[0]
                name_ext = os.path.splitext(name)[1].lower().lstrip('.')
                if name_ext not in danmaku_exts_set:
                    continue
                full_path = os.path.join(video_dir, name)
                if not (os.path.isfile(full_path) and os.path.getsize(full_path) > 0):
                    continue
                if name_no_ext.lower() == video_name and not exact_match:
                    exact_match = full_path
                elif video_name in name_no_ext.lower() and not fuzzy_match:
                    fuzzy_match = full_path
            return exact_match or fuzzy_match
        except:
            pass
        return None

    # ==================== 搜索 ====================

    def searchContent(self, key, quick, pg="1"):
        pg = int(pg)
        results = []
        clean_key = key.lower().strip()
        for path in self.scan_paths:
            if os.path.exists(path):
                self._scan_for_search(path, results, clean_key)
        start = (pg - 1) * 20
        end = min(start + 20, len(results))
        return {
            'list': results[start:end],
            'page': pg,
            'pagecount': (len(results) + 19) // 20 if results else 1,
            'limit': 20,
            'total': len(results)
        }

    def _scan_for_search(self, dir_path, results, key, depth=0):
        if depth > 5:
            return
        try:
            for name in os.listdir(dir_path):
                if name.startswith('.'):
                    continue
                full_path = os.path.join(dir_path, name)
                is_dir = os.path.isdir(full_path)
                ext = self.get_file_ext(name) if not is_dir else ''
                if not is_dir and self.is_media_file(ext) and key in name.lower():
                    results.append({
                        'vod_id': full_path,
                        'vod_name': f"🎬 {name}",
                        'vod_pic': self._get_video_icon(),
                        'vod_remarks': '视频'
                    })
                if is_dir:
                    self._scan_for_search(full_path, results, key, depth + 1)
        except:
            pass
