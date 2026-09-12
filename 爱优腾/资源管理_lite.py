# 资源管理_lite.py - 精简版
# 三个分类：视频目录 + 根目录 + 排序设置
# 排序/筛选通过第三个分类标签选择，自动保存

import sys
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

VIDEO_ICON = 'https://img0.baidu.com/it/u=3801173794,2209343305&fm=253&fmt=auto&app=138&f=PNG?w=500&h=500'
FOLDER_ICON = 'https://img2.baidu.com/it/u=551272933,781657751&fm=253&fmt=auto&app=138&f=PNG?w=607&h=457'

SORT_OPTIONS = [
    {"n": "🔢 自然排序升序", "v": "natural"},
    {"n": "🔢 自然排序降序", "v": "natural_desc"},
    {"n": "🕐 修改时间新→旧", "v": "time_new"},
    {"n": "🕐 修改时间旧→新", "v": "time_old"},
    {"n": "📦 文件大小大→小", "v": "size_big"},
    {"n": "📦 文件大小小→大", "v": "size_small"},
]

FILTER_OPTIONS = [
    {"n": "🎬 仅视频文件", "v": "video"},
    {"n": "📄 全部文件", "v": "all"},
]

SETTINGS_FILE = '/storage/emulated/0/.resource_lite_settings.json'


class Spider(Spider):

    def getName(self):
        return "本地资源管理"

    def init(self, extend=""):
        super().init(extend)
        self.root_path = ROOT_PATH
        self.scan_paths = SCAN_PATHS
        self.media_exts = ['mp4', 'mkv', 'avi', 'rmvb', 'mov', 'wmv', 'flv', 'm4v', 'm3u8']
        self.danmaku_exts = ['xml', 'ass', 'ssa', 'srt', 'vtt']
        self.FOLDER_PREFIX = 'folder://'
        self.VFOLDER_PREFIX = 'vfolder://'
        self.dir_cache = {}
        self.dir_cache_time = {}
        self.video_dirs_cache = None
        self.video_dirs_cache_time = 0
        # 默认设置
        self.sort_mode = 'natural'
        self.file_filter = 'video'
        # 从文件加载设置
        self._load_settings()

    # ==================== 设置持久化 ====================

    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    self.sort_mode = data.get('sort_mode', 'natural')
                    self.file_filter = data.get('file_filter', 'video')
        except:
            pass

    def _save_settings(self):
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump({'sort_mode': self.sort_mode, 'file_filter': self.file_filter}, f)
        except:
            pass

    # ==================== 工具方法 ====================

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

    def _get_sort_name(self):
        for opt in SORT_OPTIONS:
            if opt['v'] == self.sort_mode:
                return opt['n']
        return SORT_OPTIONS[0]['n']

    def _get_filter_name(self):
        for opt in FILTER_OPTIONS:
            if opt['v'] == self.file_filter:
                return opt['n']
        return FILTER_OPTIONS[0]['n']

    # ==================== 首页 ====================

    def homeContent(self, filter):
        classes = [
            {"type_id": "video_scan", "type_name": "📺 视频目录"},
            {"type_id": "settings_sort", "type_name": "↕️ 排序设置"},
            {"type_id": "settings_filter", "type_name": "📂 文件显示"},
        ]
        return {'class': classes, 'filters': {}}

    # ==================== 分类内容 ====================

    def categoryContent(self, tid, pg, filter, extend):
        pg = int(pg) if pg else 1

        # 排序设置分类
        if tid == "settings_sort":
            return self._sort_settings_content()
        # 文件显示设置分类
        if tid == "settings_filter":
            return self._filter_settings_content()

        # 选择了排序方式
        if tid.startswith("sort_"):
            self.sort_mode = tid[5:]
            self._save_settings()
            return self._sort_settings_content()

        # 选择了文件显示
        if tid.startswith("ffilter_"):
            self.file_filter = tid[8:]
            self._save_settings()
            return self._filter_settings_content()

        if tid == "video_scan":
            return self._video_scan_content(pg)

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

    # ==================== 排序设置页 ====================

    def _sort_settings_content(self):
        vlist = []
        vlist.append({
            'vod_id': 'settings_sort',
            'vod_name': f"↕️ 当前排序：{self._get_sort_name()}",
            'vod_pic': FOLDER_ICON,
            'vod_remarks': '点击下方选项切换',
            'style': {'type': 'list'}
        })
        for opt in SORT_OPTIONS:
            mark = '✅' if opt['v'] == self.sort_mode else '⚪'
            vlist.append({
                'vod_id': f"sort_{opt['v']}",
                'vod_name': f"  {mark} {opt['n']}",
                'vod_pic': FOLDER_ICON,
                'vod_remarks': '已选' if opt['v'] == self.sort_mode else '',
                'style': {'type': 'list'}
            })
        return {'list': vlist, 'page': 1, 'pagecount': 1, 'limit': 20, 'total': len(vlist)}

    # ==================== 文件显示设置页 ====================

    def _filter_settings_content(self):
        vlist = []
        vlist.append({
            'vod_id': 'settings_filter',
            'vod_name': f"📂 当前显示：{self._get_filter_name()}",
            'vod_pic': FOLDER_ICON,
            'vod_remarks': '点击下方选项切换',
            'style': {'type': 'list'}
        })
        for opt in FILTER_OPTIONS:
            mark = '✅' if opt['v'] == self.file_filter else '⚪'
            vlist.append({
                'vod_id': f"ffilter_{opt['v']}",
                'vod_name': f"  {mark} {opt['n']}",
                'vod_pic': FOLDER_ICON,
                'vod_remarks': '已选' if opt['v'] == self.file_filter else '',
                'style': {'type': 'list'}
            })
        return {'list': vlist, 'page': 1, 'pagecount': 1, 'limit': 20, 'total': len(vlist)}

    # ==================== 目录浏览 ====================

    def _browse_directory(self, current_path, pg, from_video_scan=False):
        cache_key = f"dir_{current_path}"
        if cache_key in self.dir_cache and time.time() - self.dir_cache_time.get(cache_key, 0) < 3600:
            files = self.dir_cache[cache_key]
        else:
            files = self.scan_directory(current_path)
            self.dir_cache[cache_key] = files
            self.dir_cache_time[cache_key] = time.time()

        # 默认自然排序
        files.sort(key=lambda x: (not x['is_dir'], self._natural_sort_key(x['name'])))

        # 文件显示过滤（用保存的设置）
        if self.file_filter != 'all':
            files = [f for f in files if f['is_dir'] or self.is_media_file(f.get('ext', ''))]

        # 排序方式（用保存的设置）
        if self.sort_mode:
            files = self._sort_files(files, self.sort_mode)

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

        # 用保存的排序设置
        if self.sort_mode:
            video_dirs = self._sort_dirs(video_dirs, self.sort_mode)
        else:
            video_dirs.sort(key=lambda x: self._natural_sort_key(x['name']))

        total = len(video_dirs)
        per_page = 200
        start = (pg - 1) * per_page
        end = min(start + per_page, total)
        page_dirs = video_dirs[start:end]

        vlist = []
        for d in page_dirs:
            vlist.append({
                'vod_id': self.VFOLDER_PREFIX + self.b64u_encode(d['path']),
                'vod_name': f"📁 {d['name']}",
                'vod_pic': FOLDER_ICON,
                'vod_remarks': f"{d['video_count']}个视频",
                'vod_tag': 'folder',
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
                results.append({
                    'name': dir_name,
                    'path': dir_path,
                    'video_count': video_count,
                    'mtime': os.path.getmtime(dir_path) if os.path.exists(dir_path) else 0,
                })
            for name, full_path in subdirs:
                self._scan_video_dirs(full_path, results, depth + 1)
        except:
            pass

    def _sort_dirs(self, dirs, sort_mode):
        if sort_mode == 'natural':
            dirs.sort(key=lambda x: self._natural_sort_key(x['name']))
        elif sort_mode == 'natural_desc':
            dirs.sort(key=lambda x: self._natural_sort_key(x['name']), reverse=True)
        elif sort_mode == 'time_new':
            dirs.sort(key=lambda x: -x.get('mtime', 0))
        elif sort_mode == 'time_old':
            dirs.sort(key=lambda x: x.get('mtime', 0))
        elif sort_mode == 'size_big':
            dirs.sort(key=lambda x: -x.get('video_count', 0))
        elif sort_mode == 'size_small':
            dirs.sort(key=lambda x: x.get('video_count', 0))
        else:
            dirs.sort(key=lambda x: self._natural_sort_key(x['name']))
        return dirs

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
        videos = []
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
            videos.sort(key=lambda x: self._natural_sort_key(x['name']))
        except:
            pass
        return videos

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
            'vod_pic': FOLDER_ICON,
            'vod_remarks': '',
            'vod_tag': 'folder',
            'style': {'type': 'list'}
        }

    def _create_file_item(self, f, from_video_scan=False):
        icon = self.get_file_icon(f['ext'], f['is_dir'])
        if f['is_dir']:
            prefix = self.VFOLDER_PREFIX if from_video_scan else self.FOLDER_PREFIX
            return {
                'vod_id': prefix + self.b64u_encode(f['path']),
                'vod_name': f"{icon} {f['name']}",
                'vod_pic': FOLDER_ICON,
                'vod_remarks': '文件夹',
                'vod_tag': 'folder',
                'style': {'type': 'grid', 'ratio': 1}
            }
        if self.is_media_file(f['ext']):
            return {
                'vod_id': f['path'],
                'vod_name': f"{icon} {f['name']}",
                'vod_pic': VIDEO_ICON,
                'vod_remarks': '视频',
                'vod_tag': 'video',
                'style': {'type': 'grid', 'ratio': 1}
            }
        return {
            'vod_id': f['path'],
            'vod_name': f"{icon} {f['name']}",
            'vod_pic': FOLDER_ICON,
            'vod_remarks': f['ext'].upper() if f['ext'] else '文件',
            'vod_tag': 'file',
            'style': {'type': 'grid', 'ratio': 1}
        }

    # ==================== 详情页 ====================

    def detailContent(self, ids):
        id_val = ids[0]

        # 排序设置页的选项点击
        if id_val == 'settings_sort':
            return self._sort_settings_content()
        if id_val == 'settings_filter':
            return self._filter_settings_content()
        if id_val.startswith('sort_'):
            self.sort_mode = id_val[5:]
            self._save_settings()
            return self._sort_settings_content()
        if id_val.startswith('ffilter_'):
            self.file_filter = id_val[8:]
            self._save_settings()
            return self._filter_settings_content()

        # 文件夹前缀 → 进入目录
        if id_val.startswith(self.FOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.FOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self.categoryContent(folder_path, 1, None, None)
            return {'list': []}

        if id_val.startswith(self.VFOLDER_PREFIX):
            folder_path = self.b64u_decode(id_val[len(self.VFOLDER_PREFIX):])
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                return self.categoryContent(folder_path, 1, None, None)
            return {'list': []}

        if not os.path.exists(id_val):
            return {'list': []}

        if os.path.isdir(id_val):
            return self.categoryContent(id_val, 1, None, None)

        return self._handle_file_detail(id_val)

    def _handle_file_detail(self, file_path):
        name = os.path.basename(file_path)
        ext = self.get_file_ext(name)
        vod = {
            'vod_id': file_path,
            'vod_name': name,
            'vod_play_from': '本地播放',
            'vod_play_url': '',
            'style': {'type': 'list'}
        }

        if self.is_media_file(ext):
            dir_path = os.path.dirname(file_path)
            all_videos = self.collect_videos_in_dir(dir_path)
            if len(all_videos) > 1:
                clicked_index = -1
                for i, video in enumerate(all_videos):
                    if video['path'] == file_path:
                        clicked_index = i
                        break
                reordered_videos = []
                if clicked_index >= 0:
                    for i in range(clicked_index, len(all_videos)):
                        reordered_videos.append(all_videos[i])
                    for i in range(0, clicked_index):
                        reordered_videos.append(all_videos[i])
                else:
                    reordered_videos = all_videos
                play_urls = [f"{os.path.splitext(v['name'])[0]}$file://{v['path']}" for v in reordered_videos]
                vod.update({
                    'vod_play_url': '#'.join(play_urls),
                    'vod_name': f"🎬 {name} (当前目录 {len(all_videos)}集)",
                    'vod_pic': VIDEO_ICON,
                    'vod_play_from': '本地视频',
                    'vod_remarks': f'共{len(all_videos)}集，循环播放'
                })
            else:
                vod.update({
                    'vod_play_url': f"{os.path.splitext(name)[0]}$file://{file_path}",
                    'vod_name': f"🎬 {name}",
                    'vod_pic': VIDEO_ICON
                })
        else:
            vod.update({
                'vod_play_url': f"{os.path.splitext(name)[0]}$file://{file_path}",
                'vod_pic': FOLDER_ICON,
                'vod_remarks': ext.upper() if ext else '文件'
            })

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

    def _sort_files(self, files, sort_mode):
        if sort_mode == 'natural':
            files.sort(key=lambda f: (not f['is_dir'], self._natural_sort_key(f['name'])))
        elif sort_mode == 'natural_desc':
            dirs = [f for f in files if f['is_dir']]
            non_dirs = [f for f in files if not f['is_dir']]
            dirs.sort(key=lambda f: self._natural_sort_key(f['name']))
            non_dirs.sort(key=lambda f: self._natural_sort_key(f['name']), reverse=True)
            files = dirs + non_dirs
        elif sort_mode == 'time_new':
            files.sort(key=lambda f: (not f['is_dir'], -f.get('mtime', 0)))
        elif sort_mode == 'time_old':
            files.sort(key=lambda f: (not f['is_dir'], f.get('mtime', 0)))
        elif sort_mode == 'size_big':
            def get_size(f):
                try:
                    return -os.path.getsize(f['path']) if not f['is_dir'] else 0
                except:
                    return 0
            files.sort(key=lambda f: (not f['is_dir'], get_size(f)))
        elif sort_mode == 'size_small':
            def get_size(f):
                try:
                    return os.path.getsize(f['path']) if not f['is_dir'] else 0
                except:
                    return 0
            files.sort(key=lambda f: (not f['is_dir'], get_size(f)))
        else:
            files.sort(key=lambda f: (not f['is_dir'], self._natural_sort_key(f['name'])))
        return files

    # ==================== 弹幕查找 ====================

    def _find_local_danmaku_file(self, video_path):
        try:
            video_dir = os.path.dirname(video_path)
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            if not os.path.isdir(video_dir):
                return None
            for ext in self.danmaku_exts:
                for name in os.listdir(video_dir):
                    if name.startswith('.') or name in ['.', '..']:
                        continue
                    name_no_ext = os.path.splitext(name)[0]
                    name_ext = os.path.splitext(name)[1].lower().lstrip('.')
                    if name_ext == ext and name_no_ext == video_name:
                        full_path = os.path.join(video_dir, name)
                        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
                            return full_path
            for ext in self.danmaku_exts:
                for name in os.listdir(video_dir):
                    if name.startswith('.') or name in ['.', '..']:
                        continue
                    name_no_ext = os.path.splitext(name)[0]
                    name_ext = os.path.splitext(name)[1].lower().lstrip('.')
                    if name_ext == ext and video_name.lower() in name_no_ext.lower():
                        full_path = os.path.join(video_dir, name)
                        if os.path.isfile(full_path) and os.path.getsize(full_path) > 0:
                            return full_path
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
                        'vod_pic': VIDEO_ICON,
                        'vod_remarks': '视频'
                    })
                if is_dir:
                    self._scan_for_search(full_path, results, key, depth + 1)
        except:
            pass
