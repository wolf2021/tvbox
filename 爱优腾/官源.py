# coding=utf-8
# !/usr/bin/python
"""
聚合影视（豆瓣 / 腾讯视频 / 优酷视频 / 爱奇艺视频 / 芒果视频 / 哔哩视频）
- 一级分类 = 各站 + 设置；
- 豆瓣支持分类多选（movie,tv 等）与其它筛选多选叠加；
- 播放线路交由外部来源处理：内置 type 1 采集源 + 宿主 asSource 外置采集源；
- 设置里通过 multiInput 对话框调整内置/自定义采集源顺序与启用隐藏。
"""
import json
import sys
import re
import copy
import time
import uuid
import urllib.parse
from datetime import datetime
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor

sys.path.append('..')
from base.spider import Spider
from pyquery import PyQuery as pq


class Spider(Spider):

    PLAY_SOURCES = [
        {'key': '天堂', 'name': '天堂', 'type': 1, 'api': 'https://dyttzyw.com/api.php/provide/vod/'},
        {'key': '西瓜', 'name': '西瓜', 'type': 1, 'api': 'https://caiji.xgzyapi.com/api.php/provide/vod/'},
        {'key': '非凡', 'name': '非凡', 'type': 1, 'api': 'http://api.ffzyapi.com/api.php/provide/vod/'},
        {'key': '暴风', 'name': '暴风', 'type': 1, 'api': 'https://bfzyapi.com/api.php/provide/vod/'},
        {'key': '量子', 'name': '量子', 'type': 1, 'api': 'https://cj.lziapi.com/api.php/provide/vod/'},
        {'key': '卧龙', 'name': '卧龙', 'type': 1, 'api': 'https://collect.wolongzyw.com/api.php/provide/vod/'},
        {'key': '最大', 'name': '最大', 'type': 1, 'api': 'https://api.zuidapi.com/api.php/provide/vod/'},
        {'key': '无尽', 'name': '无尽', 'type': 1, 'api': 'https://api.wujinapi.me/api.php/provide/vod/'},
    ]
    SOURCES_MODE = 'merge'

    IQIYI_HOST = 'https://www.iqiyi.com'
    IQIYI_SEARCH = ('https://search.video.iqiyi.com/o?if=html5&key=**'
                    '&pageNum=fypage&pos=1&pageSize=24&site=iqiyi')

    MGTV_HOST = 'https://pianku.api.mgtv.com'
    MGTV_SEARCH = 'https://mobileso.bz.mgtv.com/msite/search/v2?q=**&pn=fypage&pc=10'
    MGTV_LIST = ('/rider/list/pcweb/v3?platform=pcweb&channelId=fyclass&pn=fypage'
                 '&pc=80&hudong=1&_support=10000000&kind=a1&area=a1')

    YOUKU_HOST = 'https://www.youku.com'
    YOUKU_SEARCH = 'https://search.youku.com/api/search?pg=fypage&keyword=**'

    TENCENT_HOST = 'https://v.qq.com'
    TENCENT_API = 'https://pbaccess.video.qq.com'

    BILI_HOST = 'https://www.bilibili.com'
    BILI_SEARCH = ('https://api.bilibili.com/x/web-interface/search/type'
                   '?search_type=media_bangumi&keyword=**&page=fypage')
    BILI_INDEX = 'https://api.bilibili.com/pgc/season/index/result'
    BILI_DETAIL = 'http://api.bilibili.com/pgc/view/web/season'

    DOUBAN_HOST = 'https://movie.douban.com'
    DOUBAN_API = 'https://m.douban.com/rexxar/api/v2'
    DOUBAN_PAGE_SIZE = 20

    YOUKU_KEYS = {'chargeInfo', 'order', 'year', 'area'}
    IQIYI_KEYS = {'is_purchase', 'mode', 'year', 'region'}
    MGTV_KEYS = {'chargeInfo', 'sort', 'year'}
    TENCENT_KEYS = {'sort'}

    CONFIG_PATH = '/sdcard/juhe_config.json'

    SITE_NAMES = {
        'douban': '豆瓣',
        'tencent': '腾讯视频',
        'youku': '优酷视频',
        'iqiyi': '爱奇艺视频',
        'mgtv': '芒果视频',
        'bili': '哔哩视频',
        'settings': '设置',
    }
    SITE_DEFAULT_CATE = {
        'douban': 'top200',
        'tencent': '100113',
        'youku': '电视剧',
        'iqiyi': '2',
        'mgtv': '2',
        'bili': '1',
    }

    def init(self, extend=""):
        try:
            self.extendDict = json.loads(extend) if isinstance(extend, str) else (extend or {})
        except Exception:
            self.extendDict = {}

        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36',
            'Referer': 'https://www.youku.com',
        }
        self.mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/109.0.5410.0 Mobile Safari/537.36',
            'Referer': 'https://www.youku.com',
        }
        self.tencent_headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36',
            'origin': self.TENCENT_HOST,
            'referer': self.TENCENT_HOST + '/',
        }
        self.bili_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36',
            'Referer': 'https://www.bilibili.com',
        }
        self.douban_headers = {
            'Referer': self.DOUBAN_HOST + '/',
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/120.0 Mobile Safari/537.36',
        }
        self.page_contexts = {}

        self._load_config()

    def getName(self):
        return "聚合影视"

    def getLogo(self):
        return "https://bkimg.cdn.bcebos.com/pic/6c224f4a20a4462309f7e398376a650e0cf3d6ca79ba"

    def isVideoFormat(self, url):
        pass

    def manualVideoCheck(self):
        pass

    def destroy(self):
        pass

    def _log(self, msg):
        try:
            with open('/sdcard/juhe_debug.log', 'a', encoding='utf-8') as f:
                f.write(str(msg) + '\n')
        except Exception:
            pass

    # ==================== 配置持久化 ====================
    def _save_config(self):
        try:
            with open(self.CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.extendDict, f, ensure_ascii=False)
        except Exception as e:
            self._log('保存配置异常 ' + str(e))

    def _load_config(self):
        try:
            with open(self.CONFIG_PATH, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for k, v in saved.items():
                    self.extendDict[k] = v
        except Exception:
            pass

    # ==================== 首页 ====================
    def homeContent(self, filter):
        classes = [
            {'type_name': self.SITE_NAMES[k], 'type_id': k}
            for k in ('douban', 'tencent', 'youku', 'iqiyi', 'mgtv', 'bili', 'settings')
        ]
        filters = {}
        if filter:
            filters['douban'] = self._douban_filter()
            filters['tencent'] = self._tencent_filter()
            filters['youku'] = self._youku_filter()
            filters['iqiyi'] = self._iqiyi_filter()
            filters['mgtv'] = self._mgtv_filter()
            filters['bili'] = self._bili_filter_default()
        return {'class': classes, 'filters': filters}

    def homeVideoContent(self):
        vlist = []
        try:
            doc = self._fetch_html(self.TENCENT_HOST, self.tencent_headers)
            for script in doc('script').items():
                if 'window.__INITIAL_STATE__' not in script.text():
                    continue
                idx = script.text().find('=')
                if idx == -1:
                    continue
                data = json.loads(script.text()[idx + 1:])
                cards = (data.get('storeModulesData', {})
                             .get('channelsModulesMap', {})
                             .get('choice', {})
                             .get('cardListData', []))
                for group in cards:
                    for card in group.get('children_list', {}).get('list', {}).get('cards', []):
                        params = card.get('params', {})
                        if not params:
                            continue
                        vid = card.get('id') or params.get('cid')
                        name = params.get('mz_title') or params.get('title')
                        if not vid or not name or 'http' in vid:
                            continue
                        tag = self._parse_tag(params.get('uni_imgtag') or params.get('imgtag'))
                        vlist.append({
                            'vod_id': 'tencent_%s' % vid,
                            'vod_name': name,
                            'vod_pic': params.get('image_url', ''),
                            'vod_year': tag.get('tag_2', {}).get('text', ''),
                            'vod_remarks': tag.get('tag_4', {}).get('text', ''),
                        })
                break
        except Exception as e:
            self._log('homeVideoContent 异常 ' + str(e))
        return {'list': vlist}

    # ==================== 分类列表 ====================
    def categoryContent(self, tid, pg, filter, extend):
        extend = self._normalize_extend(extend)

        if tid == 'settings':
            return self._settings_category(pg)

        if tid in self.SITE_NAMES:
            site = tid
            if site == 'douban':
                mode = extend.get('mode') or 'top200'
                return self._douban_category(mode, pg, extend)
            cid = extend.get('cate') or self.SITE_DEFAULT_CATE.get(site, '')
            if site == 'tencent':
                return self._tencent_category(cid, pg, extend)
            if site == 'youku':
                return self._youku_category(cid, pg, extend)
            if site == 'iqiyi':
                return self._iqiyi_category(cid, pg, extend)
            if site == 'mgtv':
                return self._mgtv_category(cid, pg, extend)
            if site == 'bili':
                return self._bili_category(cid, pg, extend)
            return self._page([], pg)

        site, _, cid = str(tid).partition('_')
        if site in self.SITE_NAMES and cid:
            if site == 'douban':
                return self._douban_category(cid, pg, extend)
            if site == 'tencent':
                return self._tencent_category(cid, pg, extend)
            if site == 'youku':
                return self._youku_category(cid, pg, extend)
            if site == 'iqiyi':
                return self._iqiyi_category(cid, pg, extend)
            if site == 'mgtv':
                return self._mgtv_category(cid, pg, extend)
            if site == 'bili':
                return self._bili_category(cid, pg, extend)
        return self._page([], pg)

    # ==================== 设置 ====================
    def _settings_category(self, pg):
        all_keys = self._all_keys()
        hidden_keys = set(self.extendDict.get('hidden_sources', []))

        def _name_of(k):
            if k.startswith('custom_'):
                for c in self.extendDict.get('custom_sources', []):
                    if c.get('key') == k:
                        return c.get('name', k)
                return k
            for s in self.PLAY_SOURCES:
                if s['key'] == k:
                    return s['name']
            return k

        visible_names = [_name_of(k) for k in all_keys if k not in hidden_keys]
        hidden_names = [_name_of(k) for k in all_keys if k in hidden_keys]

        order_text = ' > '.join(visible_names) if visible_names else '（无）'
        if hidden_names:
            order_text += ' ｜ 隐藏：' + '、'.join(hidden_names)

        custom = self.extendDict.get('custom_sources', [])
        custom_text = '、'.join([c.get('name', '') for c in custom]) if custom else '无'

        vlist = [
            {
                'vod_id': json.dumps({
                    'actionId': 'juhe_settings_action',
                    'type': 'multiInput',
                    'title': '⚙️ 采集源排序与开关',
                    'msg': '设置每个源的位置与启用/隐藏状态（含自定义源）',
                    'input': self._settings_inputs()
                }, ensure_ascii=False),
                'vod_name': '⚙️ 采集源排序与开关',
                'vod_remarks': '源顺序：{}'.format(order_text),
                'vod_tag': 'action',
            },
            {
                'vod_id': json.dumps({
                    'actionId': 'juhe_add_source_action',
                    'type': 'multiInput',
                    'title': '➕ 添加采集源',
                    'msg': '输入源名称和 API 地址，点确定添加',
                    'input': [
                        {'id': 'add_name', 'name': '源名称', 'tip': '例如：某某资源', 'value': ''},
                        {'id': 'add_api', 'name': 'API地址', 'tip': '例如：https://xxx.com/api.php/provide/vod/', 'value': ''},
                    ]
                }, ensure_ascii=False),
                'vod_name': '➕ 添加采集源',
                'vod_remarks': '自定义：{}'.format(custom_text),
                'vod_tag': 'action',
            },
            {
                'vod_id': json.dumps({
                    'actionId': 'juhe_del_source_action',
                    'type': 'multiInput',
                    'title': '🗑️ 删除自定义采集源',
                    'msg': '选择要删除的自定义源',
                    'input': self._delete_inputs()
                }, ensure_ascii=False),
                'vod_name': '🗑️ 删除自定义采集源',
                'vod_remarks': '当前自定义：{}'.format(custom_text),
                'vod_tag': 'action',
            },
        ]

        return {
            'list': vlist,
            'page': int(pg),
            'pagecount': int(pg),
            'limit': 50,
            'total': len(vlist),
        }

    def _all_keys(self):
        builtin_order = list(self.extendDict.get(
            'builtin_order', [s['key'] for s in self.PLAY_SOURCES]))
        custom = list(self.extendDict.get('custom_sources', []))
        all_keys = list(builtin_order)
        for c in custom:
            if isinstance(c, dict) and c.get('key') and c['key'] not in all_keys:
                all_keys.append(c['key'])
        for s in self.PLAY_SOURCES:
            if s['key'] not in all_keys:
                all_keys.append(s['key'])
        return all_keys

    def _settings_inputs(self):
        all_keys = self._all_keys()
        hidden_keys = self.extendDict.get('hidden_sources', [])
        custom = list(self.extendDict.get('custom_sources', []))

        option_list = []
        for i in range(1, len(all_keys) + 1):
            option_list.append('第{}位·启用:{}_on'.format(i, i))
            option_list.append('第{}位·隐藏:{}_off'.format(i, i))
        options_str = ','.join(option_list)

        def _name_of(k):
            if k.startswith('custom_'):
                for c in custom:
                    if c.get('key') == k:
                        return c.get('name', k)
                return k
            for s in self.PLAY_SOURCES:
                if s['key'] == k:
                    return s['name']
            return k

        inputs = []
        for idx, key in enumerate(all_keys):
            name = _name_of(key)
            is_hidden = key in hidden_keys
            cur = '{}位·{}'.format(idx + 1, '隐藏' if is_hidden else '启用')
            inputs.append({
                'id': 'cfg_' + key,
                'name': name,
                'tip': '选择位置与状态',
                'value': cur,
                'selectData': options_str,
            })

        return inputs

    def _delete_inputs(self):
        custom = self.extendDict.get('custom_sources', [])
        if not custom:
            return [{'id': 'del_none', 'name': '无自定义源', 'tip': '当前没有可删除的源', 'value': '无', 'readonly': True}]

        # 只让显示名做选项，值也用显示名，保证回传的就是 name
        options = ','.join(['{}:{}'.format(c.get('name', ''), c.get('name', '')) for c in custom])
        return [{
            'id': 'del_key',
            'name': '选择要删除的源',
            'tip': '选中后点确定删除',
            'value': custom[0].get('name', ''),
            'selectData': options,
        }]

    # ==================== 动作回调 ====================
    def action(self, action_str):
        self._log('===== action 被调用, 原始内容: ' + repr(action_str))

        payload = None
        if isinstance(action_str, dict):
            payload = action_str
        elif isinstance(action_str, str):
            try:
                payload = json.loads(action_str)
            except Exception as e:
                self._log('action 解析失败: ' + str(e))
                return self._error_result('参数异常')

        if not isinstance(payload, dict):
            return self._error_result('参数异常')

        action_id = payload.get('actionId') or payload.get('action') or ''

        inputs = payload.get('input')
        if inputs is None and 'value' in payload:
            value_dict = payload.get('value') or {}
            if isinstance(value_dict, dict):
                inputs = []
                for k, v in value_dict.items():
                    inputs.append({'id': k, 'value': v})
            elif isinstance(value_dict, list):
                inputs = value_dict

        if inputs is None:
            inputs = []

        self._log('===== 解析出 action_id={} inputs={}'.format(action_id, inputs))

        if action_id in ('juhe_settings_action', 'juhe_settings_result', ''):
            return self._do_save_settings(inputs)
        if action_id == 'juhe_add_source_action':
            return self._do_add_source(inputs)
        if action_id == 'juhe_del_source_action':
            return self._do_del_source(inputs)

        return self._error_result('未知动作: ' + str(action_id))

    def _do_save_settings(self, inputs):
        self._log('===== _do_save_settings 收到 inputs: ' + repr(inputs))

        target_pos = {}
        hidden_keys = set()
        parsed_any = False

        for item in inputs:
            if not isinstance(item, dict):
                continue
            iid = item.get('id', '') or item.get('key', '') or item.get('name', '')
            val = ''
            for field in ('value', 'text', 'content', 'selected', 'selectValue', 'val'):
                if field in item and item[field] not in (None, ''):
                    val = item[field]
                    break

            self._log('===== 解析项 id={} val={}'.format(iid, val))

            if val == '':
                continue
            parsed_any = True

            if iid.startswith('cfg_'):
                key = iid[4:]
                s = str(val)
                m = re.search(r'(\d+)', s)
                if m:
                    target_pos[key] = int(m.group(1))
                if '隐藏' in s or s.endswith('_off'):
                    hidden_keys.add(key)

        if not parsed_any:
            return {
                'action': {
                    'actionId': 'juhe_settings_result',
                    'type': 'msgbox',
                    'title': '⚠️ 未获取到修改',
                    'htmlMsg': '没有解析到任何修改值，请关闭对话框重新打开设置再试。',
                },
                'toast': '未获取到修改值',
            }

        all_keys_old = self._all_keys()
        key_list = [k for k in all_keys_old if k in target_pos]
        new_sorted = sorted(key_list, key=lambda k: target_pos.get(k, 999))
        for k in all_keys_old:
            if k not in new_sorted:
                new_sorted.append(k)

        new_builtin = [k for k in new_sorted if not k.startswith('custom_')]
        new_custom_keys = [k for k in new_sorted if k.startswith('custom_')]

        custom = list(self.extendDict.get('custom_sources', []))
        custom_map = {c.get('key'): c for c in custom if isinstance(c, dict)}
        new_custom = [custom_map[k] for k in new_custom_keys if k in custom_map]

        self.extendDict['builtin_order'] = new_builtin
        self.extendDict['hidden_sources'] = list(hidden_keys)
        self.extendDict['custom_sources'] = new_custom
        self._save_config()

        def _name_of(k):
            if k.startswith('custom_'):
                for c in new_custom:
                    if c.get('key') == k:
                        return c.get('name', k)
                return k
            for s in self.PLAY_SOURCES:
                if s['key'] == k:
                    return s['name']
            return k

        visible = [k for k in new_sorted if k not in hidden_keys]
        names = ' > '.join(_name_of(k) for k in visible)
        hidden_names = '、'.join(_name_of(k) for k in new_sorted if k in hidden_keys)

        msg = '源顺序：{}'.format(names if names else '（无）')
        if hidden_names:
            msg += '<br>已隐藏：{}'.format(hidden_names)

        return {
            'action': {
                'actionId': 'juhe_settings_result',
                'type': 'msgbox',
                'title': '✅ 已保存',
                'htmlMsg': msg,
            },
            'toast': '设置已保存',
        }

    def _do_add_source(self, inputs):
        name = ''
        api = ''
        for item in inputs:
            if not isinstance(item, dict):
                continue
            iid = item.get('id', '')
            val = ''
            for field in ('value', 'text', 'content', 'selected', 'selectValue', 'val'):
                if field in item and item[field] not in (None, ''):
                    val = item[field]
                    break
            if iid == 'add_name':
                name = str(val).strip()
            elif iid == 'add_api':
                api = str(val).strip()

        if not name or not api:
            return {
                'action': {
                    'actionId': 'juhe_settings_result',
                    'type': 'msgbox',
                    'title': '⚠️ 信息不完整',
                    'htmlMsg': '请填写源名称和 API 地址。',
                },
                'toast': '请填写完整',
            }

        custom = list(self.extendDict.get('custom_sources', []))
        key = 'custom_' + name
        custom = [c for c in custom if c.get('key') != key]
        custom.append({
            'key': key,
            'name': name,
            'type': 1,
            'api': api,
        })
        self.extendDict['custom_sources'] = custom

        order = list(self.extendDict.get('builtin_order', []))
        if not order:
            order = [s['key'] for s in self.PLAY_SOURCES]
        if key not in order:
            order.append(key)
        self.extendDict['builtin_order'] = order

        self._save_config()

        return {
            'action': {
                'actionId': 'juhe_settings_result',
                'type': 'msgbox',
                'title': '✅ 已添加',
                'htmlMsg': '已添加：{}<br>API：{}<br><br>可返回设置页继续调整顺序。'.format(name, api),
            },
            'toast': '已添加采集源',
        }

    def _do_del_source(self, inputs):
        del_val = ''
        for item in inputs:
            if not isinstance(item, dict):
                continue
            iid = item.get('id', '')
            val = ''
            for field in ('value', 'text', 'content', 'selected', 'selectValue', 'val'):
                if field in item and item[field] not in (None, ''):
                    val = item[field]
                    break
            if iid == 'del_key':
                del_val = str(val).strip()

        if not del_val:
            return {
                'action': {
                    'actionId': 'juhe_settings_result',
                    'type': 'msgbox',
                    'title': '⚠️ 未选择',
                    'htmlMsg': '没有选择要删除的源。',
                },
                'toast': '未选择',
            }

        # 兼容壳子回传 "显示名:值" 的格式，取冒号前后两段都作为候选
        candidates = set()
        candidates.add(del_val)
        if ':' in del_val:
            for p in del_val.split(':'):
                p = p.strip()
                if p:
                    candidates.add(p)

        custom = list(self.extendDict.get('custom_sources', []))
        new_custom = []
        removed_key = ''
        removed_name = ''
        for c in custom:
            if not isinstance(c, dict):
                continue
            ckey = c.get('key', '')
            cname = c.get('name', '')
            if cname in candidates or ckey in candidates:
                removed_key = ckey
                removed_name = cname or ckey
                continue
            new_custom.append(c)

        if not removed_key:
            return {
                'action': {
                    'actionId': 'juhe_settings_result',
                    'type': 'msgbox',
                    'title': '⚠️ 未找到',
                    'htmlMsg': '没有找到要删除的源：{}'.format(del_val),
                },
                'toast': '未找到',
            }

        self.extendDict['custom_sources'] = new_custom

        order = [k for k in self.extendDict.get('builtin_order', []) if k != removed_key]
        self.extendDict['builtin_order'] = order

        hidden = [k for k in self.extendDict.get('hidden_sources', []) if k != removed_key]
        self.extendDict['hidden_sources'] = hidden

        self._save_config()

        return {
            'action': {
                'actionId': 'juhe_settings_result',
                'type': 'msgbox',
                'title': '✅ 已删除',
                'htmlMsg': '已删除：{}'.format(removed_name),
            },
            'toast': '已删除',
        }

    # ---------- 豆瓣（分类多选 + 其它筛选多选叠加） ----------
    def _douban_category(self, mode, pg, extend):
        p = int(pg) if pg else 1
        ext = dict(extend) if isinstance(extend, dict) else {}

        def _split_multi(v):
            if v is None:
                return []
            if isinstance(v, list):
                out = []
                for x in v:
                    out.extend(_split_multi(x))
                return out
            s = str(v).strip()
            if not s:
                return []
            for sep in (',', '&'):
                if sep in s:
                    parts = [x.strip() for x in s.split(sep) if x.strip()]
                    if parts:
                        return parts
            return [s]

        modes = _split_multi(mode)
        if not modes:
            modes = ['top200']

        genres = [g for g in _split_multi(ext.get('genre'))
                  if g not in ('全部', '不限类型', '不限')]
        areas = [a for a in _split_multi(ext.get('area')) if a != '全部']
        plats = [x for x in _split_multi(ext.get('platform')) if x != '全部']
        years = [y for y in _split_multi(ext.get('year')) if y and y != '全部']
        sorts = _split_multi(ext.get('sort'))
        scores = _split_multi(ext.get('score'))
        playable_list = _split_multi(ext.get('playable'))

        sort_val = sorts[0] if sorts else 'T'
        score_val = scores[0] if scores else '0,10'
        playable_flag = any(x for x in playable_list)

        all_items = []
        seen_ids = set()

        for one_mode in modes:
            one_mode = one_mode.strip()
            if not one_mode:
                continue
            try:
                items = self._douban_fetch_mode(
                    one_mode, p, genres, areas, plats, years,
                    sort_val, score_val, playable_flag)
            except Exception as e:
                self._log('douban mode={} 异常 {}'.format(one_mode, e))
                items = []

            for it in items:
                vid = str(it.get('vod_id') or '')
                if not vid or vid in seen_ids:
                    continue
                seen_ids.add(vid)
                all_items.append(it)

        pagecount = p + 1 if len(all_items) > 0 else p

        return {
            'list': all_items,
            'page': p,
            'pagecount': pagecount,
            'limit': self.DOUBAN_PAGE_SIZE,
            'total': len(all_items),
        }

    def _douban_fetch_mode(self, mode, p, genres, areas, plats, years,
                           sort_val, score_val, playable_flag):
        start = (p - 1) * self.DOUBAN_PAGE_SIZE

        if mode == 'top200':
            if start >= 200:
                return []
            top_count = min(self.DOUBAN_PAGE_SIZE, 200 - start)
            url = (self.DOUBAN_API + '/subject_collection/movie_top250/items'
                   '?start=' + str(start) + '&count=' + str(top_count))
            data = self._get_json(url, self.douban_headers)
            items = (data or {}).get('subject_collection_items') \
                or (data or {}).get('items') or []
            return self._douban_subject_list(items)

        if mode == 'movie_hot':
            mode = 'hot'

        if mode == 'tv_animation':
            selected = {'类型': '动画'}
            tags = list(years)
            if '动画' not in tags:
                tags.insert(0, '动画')
            query = [
                'refresh=0',
                'start=' + str(start),
                'count=' + str(self.DOUBAN_PAGE_SIZE),
                'selected_categories=' + urllib.parse.quote(
                    json.dumps(selected, ensure_ascii=False)),
                'uncollect=false',
                'score_range=' + urllib.parse.quote(score_val),
                'tags=' + urllib.parse.quote(','.join(tags)),
                'sort=' + urllib.parse.quote(sort_val),
            ]
            if playable_flag:
                query.append('playable=true')
            url = self.DOUBAN_API + '/movie/recommend?' + '&'.join(query)
            self._log('douban 动画 url={}'.format(url))
            data = self._get_json(url, self.douban_headers)
            items = (data or {}).get('items', []) or []

            if not items:
                try:
                    fb_url = (self.DOUBAN_API + '/search/subjects?q=' +
                              urllib.parse.quote('动画') +
                              '&type=tv&start=' + str(start) +
                              '&count=' + str(self.DOUBAN_PAGE_SIZE))
                    fb = self._get_json(fb_url, self.douban_headers)
                    items = ((fb or {}).get('subjects', {}) or {}).get('items', []) or []
                except Exception as e:
                    self._log('douban 动画兜底异常 ' + str(e))

            return self._douban_subject_list(items)

        tv_modes = ('tv', 'tv_hot', 'tv_domestic', 'tv_american', 'tv_japanese',
                    'tv_korean', 'tv_documentary',
                    'show', 'show_domestic', 'show_foreign')
        is_tv = mode in tv_modes
        real_tid = 'tv' if is_tv else 'movie'

        selected = {}
        if is_tv:
            if mode == 'tv_hot':
                selected['类型'] = '全部剧集'
            elif mode == 'tv_domestic':
                selected['地区'] = '中国大陆'
                selected['类型'] = '全部剧集'
            elif mode == 'tv_american':
                selected['地区'] = '美国'
                selected['类型'] = '全部剧集'
            elif mode == 'tv_japanese':
                selected['地区'] = '日本'
                selected['类型'] = '全部剧集'
            elif mode == 'tv_korean':
                selected['地区'] = '韩国'
                selected['类型'] = '全部剧集'
            elif mode == 'tv_documentary':
                selected['类型'] = '纪录片'
            elif mode == 'show':
                selected['类型'] = '全部综艺'
            elif mode == 'show_domestic':
                selected['地区'] = '中国大陆'
                selected['类型'] = '全部综艺'
            elif mode == 'show_foreign':
                selected['地区'] = '国外'
                selected['类型'] = '全部综艺'
            else:
                selected['类型'] = '全部剧集'

        if genres:
            selected['类型'] = genres[0]
        if areas:
            selected['地区'] = areas[0]
        if is_tv and plats:
            selected['平台'] = plats[0]

        tags = list(years)

        query = [
            'refresh=0',
            'start=' + str(start),
            'count=' + str(self.DOUBAN_PAGE_SIZE),
            'selected_categories=' + urllib.parse.quote(
                json.dumps(selected, ensure_ascii=False)),
            'uncollect=false',
            'score_range=' + urllib.parse.quote(score_val),
            'tags=' + urllib.parse.quote(','.join(tags)),
            'sort=' + urllib.parse.quote(sort_val),
        ]
        if playable_flag:
            query.append('playable=true')
        url = self.DOUBAN_API + '/' + real_tid + '/recommend?' + '&'.join(query)

        self._log('douban mode={} url={}'.format(mode, url))
        data = self._get_json(url, self.douban_headers)
        items = (data or {}).get('items', []) or []

        return self._douban_subject_list(items)

    def _douban_subject_list(self, items):
        out = []
        for it in items or []:
            it = it or {}
            if it.get('card') and it.get('card') != 'subject':
                continue
            if it.get('layout') and it.get('layout') != 'subject':
                continue
            if it.get('target'):
                it = it.get('target')
            if not it.get('id') or not it.get('title'):
                continue
            pic = ''
            if it.get('pic'):
                pic = it['pic'].get('large', '') or it['pic'].get('normal', '')
            elif it.get('cover_url'):
                pic = it['cover_url']
            out.append({
                'vod_id': 'douban_{}'.format(it.get('id')),
                'vod_name': it.get('title', ''),
                'vod_pic': self._douban_image_url(pic),
                'vod_remarks': self._douban_rating_text(it),
                'vod_year': str(it.get('year', '') or ''),
            })
        return out

    def _douban_image_url(self, url):
        if not url:
            return ''
        return url + '@Referer=' + urllib.parse.quote(self.DOUBAN_HOST + '/')

    def _douban_rating_text(self, item):
        item = item or {}
        rating = item.get('rating') or {}
        value = float(rating.get('value', 0) or 0)
        episode = item.get('episodes_info', '') or ''
        if episode and value:
            return '{} · {}分'.format(episode, value)
        if episode:
            return episode
        return '{}分'.format(value) if value else '暂无评分'

    def _douban_filter(self):
        movie_genres = ['全部', '喜剧', '爱情', '动作', '科幻', '动画', '悬疑', '犯罪', '惊悚', '冒险',
                        '音乐', '历史', '奇幻', '恐怖', '战争', '传记', '歌舞', '武侠', '情色', '灾难',
                        '西部', '纪录片', '短片']
        movie_areas = ['全部', '华语', '欧美', '韩国', '日本', '中国大陆', '美国', '中国香港', '中国台湾',
                       '英国', '法国', '德国', '意大利', '西班牙', '印度', '泰国', '俄罗斯', '加拿大',
                       '澳大利亚', '爱尔兰', '瑞典', '巴西', '丹麦']
        years = ['全部', '2020年代', '2026', '2025', '2024', '2023', '2022', '2021', '2020',
                 '2019', '2010年代', '2000年代', '90年代', '80年代', '70年代', '60年代', '更早']

        def _vals(lst):
            return [{'n': x, 'v': '' if i == 0 else x} for i, x in enumerate(lst)]

        return [
            {'key': 'mode', 'name': '分类', 'value': [
                {'n': 'TOP200', 'v': 'top200'},
                {'n': '电影', 'v': 'movie'},
                {'n': '剧集', 'v': 'tv'},
                {'n': '动画', 'v': 'tv_animation'},
            ]},
            {'key': 'genre', 'name': '类型', 'value': _vals(movie_genres)},
            {'key': 'area', 'name': '地区', 'value': _vals(movie_areas)},
            {'key': 'year', 'name': '年代', 'value': _vals(years)},
            {'key': 'sort', 'name': '排序', 'value': [
                {'n': '综合排序', 'v': 'T'}, {'n': '近期热度', 'v': 'U'},
                {'n': '首映时间', 'v': 'R'}, {'n': '高分优先', 'v': 'S'}]},
            {'key': 'score', 'name': '评分区间', 'value': [
                {'n': '全部评分', 'v': '0,10'}, {'n': '9-10分', 'v': '9,10'},
                {'n': '8-10分', 'v': '8,10'}, {'n': '7-10分', 'v': '7,10'},
                {'n': '6-10分', 'v': '6,10'}, {'n': '0-6分', 'v': '0,6'}]},
            {'key': 'playable', 'name': '可播放', 'value': [
                {'n': '不限', 'v': ''}, {'n': '可播放', 'v': 'true'}]},
        ]

    # ---------- 腾讯 ----------
    def _tencent_category(self, tid, pg, extend):
        filter_params = self._build_filter_params(extend)
        body = {
            "page_params": {
                "channel_id": str(tid),
                "filter_params": filter_params,
                "page_type": "channel_operation",
                "page_id": "channel_list_second_page"
            }
        }
        cache_key = "{}_{}".format(tid, filter_params)
        if str(pg) != '1' and cache_key in self.page_contexts:
            body['page_context'] = self.page_contexts[cache_key]

        try:
            url = ('{}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
                   '?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1'
                   ).format(self.TENCENT_API)
            data = self.post(url, json=body, headers=self.tencent_headers).json().get('data', {})
        except Exception as e:
            self._log('tencent 分类异常 ' + str(e))
            data = {}

        has_next = data.get('has_next_page', False)
        if has_next:
            self.page_contexts[cache_key] = data.get('next_page_context', {})
        else:
            self.page_contexts.pop(cache_key, None)

        vlist = []
        for mld in data.get('module_list_datas', []):
            for md in mld.get('module_datas', []):
                for item in md.get('item_data_lists', {}).get('item_datas', []):
                    params = item.get('item_params', {})
                    cid = params.get('cid')
                    if not cid:
                        continue
                    tag = self._parse_tag(params.get('uni_imgtag') or params.get('imgtag'))
                    vlist.append({
                        'vod_id': 'tencent_{}'.format(cid),
                        'vod_name': params.get('mz_title') or params.get('title'),
                        'vod_pic': (params.get('new_pic_hz') or params.get('new_pic_vt')
                                    or params.get('image_url')),
                        'vod_year': tag.get('tag_2', {}).get('text', ''),
                        'vod_remarks': tag.get('tag_4', {}).get('text', ''),
                    })
        pagecount = int(pg) + 1 if has_next else int(pg)
        return {'list': vlist, 'page': int(pg), 'pagecount': pagecount,
                'limit': 90, 'total': 999999}

    # ---------- 优酷 ----------
    def _youku_category(self, tid, pg, extend):
        fl = {'type': tid} if tid else {}
        for k, v in extend.items():
            if k in self.YOUKU_KEYS and v not in (None, ''):
                fl[k] = v

        params = urllib.parse.quote(json.dumps(fl, ensure_ascii=False, separators=(',', ':')))

        if int(pg) > 1:
            old_session = self.page_contexts.get('yk_session_' + str(tid), '{}')
            url = '{}/category/data?session={}&pageNo={}&params={}'.format(
                self.YOUKU_HOST, urllib.parse.quote(old_session), pg, params)
        else:
            url = '{}/category/data?optionRefresh=1&pageNo={}&params={}'.format(
                self.YOUKU_HOST, pg, params)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/109.0.5410.0 Safari/537.36',
            'Referer': 'https://www.youku.com/category/',
            'Accept': 'application/json, text/plain, */*',
        }

        vlist = []
        try:
            rsp = self.fetch(url, headers=headers)
            raw = rsp.text if hasattr(rsp, 'text') else rsp
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8', 'ignore')
            data = json.loads(raw) if raw and raw.strip().startswith('{') else {}
        except Exception as e:
            self._log('youku 分类 fetch 异常 ' + str(e))
            data = {}

        try:
            inner = (data or {}).get('data', {}) or {}
            filter_data = inner.get('filterData', {}) or {}
            lists = filter_data.get('listData', []) or []
            if not lists:
                lists = inner.get('listData', []) or []

            session = filter_data.get('session') or inner.get('session')
            if session:
                self.page_contexts['yk_session_' + str(tid)] = json.dumps(
                    session, ensure_ascii=False, separators=(',', ':'))

            items = []
            for it in lists:
                link = it.get('videoLink', '') or ''
                vid = ''
                if 'id_' in link:
                    vid = link.split('id_')[1].split('.html')[0]
                elif link:
                    vid = link
                if not vid:
                    continue
                items.append((vid, it.get('img', ''), it.get('summary', ''), it.get('title', '')))

            def _fetch_name(show_id):
                try:
                    durl = 'https://v.youku.com/v_getvideo_info/?showId={}'.format(show_id)
                    d = self._get_json(durl, self.mobile_headers)
                    if d and d.get('data'):
                        return d['data'].get('showTitle', '') or ''
                except Exception:
                    pass
                return ''

            names = []
            if items:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    names = list(executor.map(lambda x: _fetch_name(x[0]), items))

            for (vid, img, summary, title), name in zip(items, names):
                final_name = name or title
                if not final_name:
                    continue
                vlist.append({
                    'vod_id': 'youku_{}${}'.format(vid, final_name),
                    'vod_name': final_name,
                    'vod_pic': img,
                    'vod_remarks': summary,
                    'vod_year': '',
                })
        except Exception as e:
            self._log('youku 分类解析异常 ' + str(e))

        if not vlist:
            try:
                vlist = self._youku_search_category(tid, pg)
            except Exception as e:
                self._log('youku 搜索兜底异常 ' + str(e))

        limit = 20
        pagecount = int(pg) if len(vlist) < limit else int(pg) + 1
        return {'list': vlist, 'page': int(pg), 'pagecount': pagecount,
                'limit': limit, 'total': 999999}

    def _youku_search_category(self, tid, pg):
        key = tid or ''
        if not key:
            return []
        url = self.YOUKU_SEARCH.replace('**', urllib.parse.quote(key)).replace('fypage', str(pg))
        data = self._get_json(url, self.mobile_headers)
        vlist = []
        for it in (data or {}).get('pageComponentList', []) or []:
            cd = it.get('commonData')
            if not cd:
                continue
            show_id = cd.get('showId')
            if not show_id:
                continue
            name = (cd.get('titleDTO', {}) or {}).get('displayName', '')
            vlist.append({
                'vod_id': 'youku_{}${}'.format(show_id, name),
                'vod_name': name,
                'vod_pic': (cd.get('posterDTO', {}) or {}).get('vThumbUrl', ''),
                'vod_remarks': cd.get('stripeBottom', ''),
                'vod_year': '',
            })
        return vlist

    # ---------- 爱奇艺 ----------
    def _iqiyi_category(self, tid, pg, extend):
        if tid in ('1', '4'):
            url = ('https://pcw-api.iqiyi.com/search/video/videolists'
                   '?channel_id={}&data_type=1&pageNum={}&pageSize=24'.format(tid, pg))
        else:
            url = ('https://pcw-api.iqiyi.com/search/recommend/list'
                   '?channel_id={}&data_type=1&page_id={}&ret_num=24'.format(tid, pg))

        params = []
        if extend.get('is_purchase'):
            params.append('is_purchase=' + urllib.parse.quote(str(extend['is_purchase'])))
        if extend.get('mode'):
            params.append('mode=' + urllib.parse.quote(str(extend['mode'])))
        if extend.get('year'):
            params.append('market_release_date_level=' + urllib.parse.quote(str(extend['year'])))
        if extend.get('region'):
            params.append('region=' + urllib.parse.quote(str(extend['region'])))
        if params:
            url += '&' + '&'.join(params)

        data = self._get_json(url, self.headers)
        vlist = []
        try:
            if isinstance(data, dict) and data.get('code') == 'A00003':
                data = self._get_json(url, self.headers)
            inner = (data or {}).get('data', {}) or {}
            for it in inner.get('list', []) or []:
                name = it.get('name', '') or ''
                if not name:
                    continue
                desc = self._iqiyi_remark(it)
                pic = it.get('imageUrl', '') or ''
                if pic.endswith('.jpg'):
                    pic = pic.replace('.jpg', '_390_520.jpg?caplist=jpg,webp')
                vlist.append({
                    'vod_id': 'iqiyi_{}${}'.format(it.get('channelId'), name),
                    'vod_name': name,
                    'vod_pic': pic,
                    'vod_remarks': desc,
                    'vod_year': '',
                })
        except Exception as e:
            self._log('iqiyi 分类解析异常 ' + str(e))
        return self._page(vlist, pg, limit=24)

    def _iqiyi_remark(self, it):
        channel_id = it.get('channelId')
        if channel_id == 1:
            desc = (str(it.get('score', '')) + '分\t') if it.get('score') else ''
            if it.get('duration'):
                desc += str(it['duration'])
            return desc
        if channel_id in (2, 4, 35, 15, 37):
            latest = it.get('latestOrder')
            total = it.get('videoCount')
            score = (str(it.get('score', '')) + '分\t') if it.get('score') else ''
            if latest and total and latest == total:
                return score + str(latest) + '集全'
            if total:
                return score + str(latest or '') + '/' + str(total) + '集'
            if latest:
                return '更新至 ' + str(latest) + '集'
            return it.get('focus', '') or ''
        if channel_id == 6:
            return str(it.get('period', '')) + '期' if it.get('period') else ''
        if it.get('latestOrder'):
            return '更新至 第' + str(it['latestOrder']) + '期'
        return it.get('period') or it.get('focus', '') or ''

    # ---------- 芒果 ----------
    def _mgtv_category(self, tid, pg, extend):
        year = extend.get('year') or 'all'
        sort = extend.get('sort') or 'all'
        charge = extend.get('chargeInfo') or 'all'
        url = self.MGTV_HOST + self.MGTV_LIST \
            .replace('fyclass', str(tid)).replace('fypage', str(pg))
        url += '&year={}&sort={}&chargeInfo={}'.format(year, sort, charge)
        data = self._get_json(url, self.headers)

        vlist = []
        items = ((data or {}).get('data', {}) or {}).get('hitDocs', []) or []
        for item in items:
            vid = item.get('playPartId') or item.get('id')
            if not vid:
                continue
            vlist.append({
                'vod_id': 'mgtv_{}'.format(vid),
                'vod_name': item.get('title', ''),
                'vod_pic': item.get('img', ''),
                'vod_remarks': self._right_corner(item),
                'vod_year': '',
            })
        return self._page(vlist, pg, limit=80)

    # ---------- B站 ----------
    def _bili_category(self, tid, pg, extend):
        cookie = self._bili_cookie()
        params = {
            'order': '2', 'sort': '0', 'pagesize': '20', 'type': '1',
            'st': tid, 'season_type': tid, 'page': str(pg),
        }
        for key in extend:
            if extend[key] not in (None, ''):
                params[key] = extend[key]
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = '{}?{}'.format(self.BILI_INDEX, query)
        data = self._get_json(url, self.bili_headers, cookies=cookie)

        vlist = []
        try:
            for vod in (data or {}).get('data', {}).get('list', []) or []:
                aid = str(vod.get('season_id', '')).strip()
                if not aid:
                    continue
                title = self._remove_html_tags(self._clean_text(vod.get('title', '')))
                vlist.append({
                    'vod_id': 'bili_{}'.format(aid),
                    'vod_name': title,
                    'vod_pic': (vod.get('cover', '') or '').strip(),
                    'vod_remarks': (vod.get('index_show', '') or '').strip(),
                })
        except Exception as e:
            self._log('bili 分类解析异常 ' + str(e))
        has_next = (data or {}).get('data', {}).get('has_next', 0)
        pagecount = int(pg) + 1 if has_next == 1 else int(pg)
        return {'list': vlist, 'page': int(pg), 'pagecount': pagecount,
                'limit': len(vlist), 'total': 999999}

    # ==================== 搜索 ====================
    def searchContent(self, key, quick, pg="1"):
        results = []
        with ThreadPoolExecutor(max_workers=6) as executor:
            futures = [
                executor.submit(self._douban_search, key, pg),
                executor.submit(self._tencent_search, key, pg),
                executor.submit(self._youku_search, key, pg),
                executor.submit(self._iqiyi_search, key, pg),
                executor.submit(self._mgtv_search, key, pg),
                executor.submit(self._bili_search, key, pg),
            ]
            for f in futures:
                try:
                    results.extend(f.result() or [])
                except Exception as e:
                    self._log('搜索子任务异常 ' + str(e))
        return {'list': results, 'page': int(pg)}

    def _douban_search(self, key, pg):
        p = int(pg) if pg else 1
        start = (p - 1) * self.DOUBAN_PAGE_SIZE
        try:
            url = (self.DOUBAN_API + '/search/subjects?q=' + urllib.parse.quote(key)
                   + '&type=movie&start=' + str(start) + '&count=' + str(self.DOUBAN_PAGE_SIZE))
            data = self._get_json(url, self.douban_headers)
            items = ((data or {}).get('subjects', {}) or {}).get('items', [])
            return self._douban_subject_list(items)
        except Exception as e:
            self._log('douban 搜索异常 ' + str(e))
            return []

    def _iqiyi_search(self, key, pg):
        url = self.IQIYI_SEARCH.replace('**', urllib.parse.quote(key)).replace('fypage', str(pg))
        data = self._get_json(url, self.mobile_headers)
        vlist = []
        for it in ((data or {}).get('data', {}) or {}).get('docinfos', []) or []:
            info = it.get('albumDocInfo', {}) or {}
            title = info.get('albumTitle', '') or ''
            if not title:
                continue
            vlist.append({
                'vod_id': 'iqiyi_{}${}'.format(info.get('channel', ''), title),
                'vod_name': title,
                'vod_pic': info.get('albumVImage', '') or '',
                'vod_remarks': info.get('tvFocus', ''),
                'vod_year': '',
            })
        return vlist

    def _mgtv_search(self, key, pg):
        url = self.MGTV_SEARCH.replace('**', key).replace('fypage', str(pg))
        data = self._get_json(url, self.mobile_headers)
        vlist = []
        for block in ((data or {}).get('data', {}) or {}).get('contents', []) or []:
            if block.get('type') != 'media':
                continue
            items = block.get('data', []) or []
            if not items:
                continue
            item = items[0]
            if item.get('source') != 'imgo':
                continue
            m = re.search(r'.*/(.*?)\.html', item.get('url', ''))
            vid = m.group(1) if m else item.get('url', '')
            title = re.sub(r'<B>|</B>', '', item.get('title', ''))
            vlist.append({
                'vod_id': 'mgtv_{}'.format(vid),
                'vod_name': title,
                'vod_pic': item.get('img', ''),
                'vod_remarks': ','.join(item.get('desc', []) or []),
                'vod_year': '',
            })
        return vlist

    def _youku_search(self, key, pg):
        url = self.YOUKU_SEARCH.replace('**', key).replace('fypage', str(pg))
        data = self._get_json(url, self.mobile_headers)
        vlist = []
        for it in (data or {}).get('pageComponentList', []) or []:
            cd = it.get('commonData')
            if not cd:
                continue
            show_id = cd.get('showId')
            if not show_id:
                continue
            name = (cd.get('titleDTO', {}) or {}).get('displayName', '')
            vlist.append({
                'vod_id': 'youku_{}${}'.format(show_id, name),
                'vod_name': name,
                'vod_pic': (cd.get('posterDTO', {}) or {}).get('vThumbUrl', ''),
                'vod_remarks': cd.get('stripeBottom', ''),
                'vod_year': '',
            })
        return vlist

    def _tencent_search(self, key, pg):
        body = {
            "version": "24072901", "clientType": 1, "filterValue": "",
            "uuid": str(uuid.uuid4()), "retry": 0, "query": key,
            "pagenum": int(pg) - 1, "pagesize": 30, "queryFrom": 0,
            "searchDatakey": "", "transInfo": "", "isneedQc": True, "preQid": "",
            "adClientInfo": "",
            "extraInfo": {"isNewMarkLabel": "1", "multi_terminal_pc": "1"}
        }
        try:
            data = self.post(
                '{}/trpc.videosearch.mobile_search.MultiTerminalSearch/MbSearch?vplatform=2'.format(
                    self.TENCENT_API),
                json=body, headers=self.tencent_headers).json()
        except Exception:
            return []
        vlist = []
        for item in (data.get('data', {}).get('areaBoxList', [{}])[-1]
                         .get('itemList', [])):
            if not item.get('doc', {}).get('id'):
                continue
            info = item.get('videoInfo', {})
            tag = self._parse_tag(info.get('imgTag'))
            vlist.append({
                'vod_id': 'tencent_{}'.format(item['doc']['id']),
                'vod_name': info.get('title', ''),
                'vod_pic': info.get('imgUrl', ''),
                'vod_year': tag.get('tag_2', {}).get('text', ''),
                'vod_remarks': tag.get('tag_4', {}).get('text', ''),
            })
        return vlist

    def _bili_search(self, key, pg):
        url = self.BILI_SEARCH.replace('**', urllib.parse.quote(key)).replace('fypage', str(pg))
        cookie = self._bili_cookie()
        data = self._get_json(url, self.bili_headers, cookies=cookie)
        vlist = []
        try:
            inner = (data or {}).get('data', {}) or {}
            if 'result' not in inner:
                return vlist
            for vod in inner.get('result', []) or []:
                sid = str(vod.get('season_id', '')).strip()
                if not sid:
                    continue
                title = self._remove_html_tags(self._clean_text(vod.get('title', '')))
                if SequenceMatcher(None, title, key).ratio() < 0.6 and key not in title:
                    continue
                eps = vod.get('eps', []) or []
                img = (eps[0].get('cover', '') if eps else '').strip()
                remark = self._remove_html_tags(vod.get('index_show', '') or '').strip()
                vlist.append({
                    'vod_id': 'bili_{}'.format(sid),
                    'vod_name': title,
                    'vod_pic': img,
                    'vod_remarks': remark,
                    'vod_year': '',
                })
        except Exception as e:
            self._log('bili 搜索异常 ' + str(e))
        return vlist

    # ==================== 详情 ====================
    def detailContent(self, ids):
        if not ids or not ids[0]:
            return self._error_result("缺少影片标识")
        raw = str(ids[0])

        if raw.startswith('{') and 'actionId' in raw:
            return {'list': []}

        site, _, ident = raw.partition('_')
        if site == 'douban':
            vod = self._douban_detail(ident)
        elif site == 'tencent':
            vod = self._tencent_detail(ident)
        elif site == 'youku':
            vod = self._youku_detail(ident)
        elif site == 'iqiyi':
            vod = self._iqiyi_detail(ident)
        elif site == 'mgtv':
            vod = self._mgtv_detail(ident)
        elif site == 'bili':
            vod = self._bili_detail(ident)
        else:
            return self._error_result("未知来源: " + raw)

        if not vod:
            return self._error_result("无法获取影片信息")

        vod['vod_sources_mode'] = self.SOURCES_MODE
        vod['vod_sources'] = self._ordered_sources()
        return {'list': [vod]}

    def _new_vod(self, vid, name):
        return {
            'vod_id': vid, 'vod_name': name, 'type_name': '', 'vod_year': '',
            'vod_area': '', 'vod_actor': '', 'vod_director': '', 'vod_content': '',
            'vod_remarks': '', 'vod_pic': '',
        }

    # ---------- 播放源顺序 ----------
    def _ordered_sources(self):
        builtin_order = list(self.extendDict.get(
            'builtin_order', [s['key'] for s in self.PLAY_SOURCES]))
        custom = list(self.extendDict.get('custom_sources', []))
        hidden_keys = set(self.extendDict.get('hidden_sources', []))

        builtin_map = {s['key']: s for s in self.PLAY_SOURCES}
        custom_map = {c.get('key'): c for c in custom if isinstance(c, dict)}

        ordered_keys = list(builtin_order)
        for k in custom_map:
            if k not in ordered_keys:
                ordered_keys.append(k)
        for s in self.PLAY_SOURCES:
            if s['key'] not in ordered_keys:
                ordered_keys.append(s['key'])

        result = []
        for k in ordered_keys:
            if k in hidden_keys:
                continue
            if k.startswith('custom_'):
                c = custom_map.get(k)
                if c:
                    result.append({
                        'key': c['key'],
                        'name': c.get('name', ''),
                        'type': 1,
                        'api': c.get('api', ''),
                    })
            else:
                s = builtin_map.get(k)
                if s:
                    result.append(copy.deepcopy(s))

        return result

    # ---------- 豆瓣详情 ----------
    def _douban_detail(self, show_id):
        m = re.search(r'\d+', str(show_id))
        if not m:
            return None
        show_id = m.group(0)
        try:
            item = self._get_json(self.DOUBAN_API + '/subject/' + show_id, self.douban_headers)
        except Exception as e:
            self._log('douban 详情异常 ' + str(e))
            return None
        if not item:
            return None
        return {
            'vod_id': 'douban_{}'.format(show_id),
            'vod_name': item.get('title', '') or show_id,
            'type_name': '',
            'vod_year': str(item.get('year', '') or ''),
            'vod_area': '/'.join(item.get('countries', []) or []),
            'vod_actor': '/'.join([a.get('name', '') for a in (item.get('actors', []) or [])]),
            'vod_director': '/'.join([d.get('name', '') for d in (item.get('directors', []) or [])]),
            'vod_content': item.get('intro', '') or '',
            'vod_remarks': self._douban_rating_text(item),
            'vod_pic': self._douban_image_url(
                item.get('cover_url', '') or
                (item.get('pic', {}) or {}).get('large', '') or
                (item.get('pic', {}) or {}).get('normal', '')
            ),
        }

    # ---------- 优酷详情 ----------
    def _youku_detail(self, ident):
        show_id, _, name_in_id = ident.partition('$')
        if not show_id:
            show_id = ident

        vod = self._new_vod(show_id, '')
        if name_in_id:
            vod['vod_name'] = name_in_id

        try:
            detail_url = 'https://v.youku.com/v_getvideo_info/?showId={}'.format(show_id)
            detail_info = self._get_json(detail_url, self.mobile_headers)
            if detail_info and detail_info.get('data'):
                v = detail_info['data']
                if not vod['vod_name']:
                    vod['vod_name'] = v.get('showTitle', '') or ''
                vod['type_name'] = v.get('showVideotype', '')
                vod['vod_year'] = v.get('lastUpdate', '')
                vod['vod_remarks'] = v.get('rc_title', '')
                vod['vod_actor'] = v.get('_personNameStr', '')
                vod['vod_content'] = v.get('showdesc', '')
                vod['vod_pic'] = v.get('showLogo', '') or vod['vod_pic']
        except Exception as e:
            self._log('youku v_getvideo_info 异常 ' + str(e))

        if not vod['vod_pic']:
            try:
                info_url = ('https://search.youku.com/api/search'
                            '?appScene=show_episode&showIds={}').format(show_id)
                info_data = self._get_json(info_url, self.mobile_headers)
                serises = info_data.get('serisesList') or []
                if serises:
                    vod['vod_pic'] = serises[0].get('thumbUrl', '') or vod['vod_pic']
            except Exception:
                pass

        return vod if vod['vod_name'] else None

    # ---------- 爱奇艺详情 ----------
    def _iqiyi_detail(self, ident):
        channel_id, _, search_key = ident.partition('$')
        if not search_key:
            search_key = ident
        vod = self._new_vod(search_key, search_key)

        album_id = ''
        try:
            surl = ('https://search.video.iqiyi.com/o?if=html5&key={}'
                    '&pageNum=1&pos=1&pageSize=24&site=iqiyi'
                    ).format(urllib.parse.quote(search_key))
            sdata = self._get_json(surl, self.mobile_headers)
            docs = ((sdata or {}).get('data', {}) or {}).get('docinfos', []) or []
            matched = None
            for it in docs:
                info = it.get('albumDocInfo', {}) or {}
                if (info.get('albumTitle', '') or '') == search_key:
                    matched = info
                    break
            if not matched:
                for it in docs:
                    info = it.get('albumDocInfo', {}) or {}
                    t = info.get('albumTitle', '') or ''
                    if search_key in t or t in search_key:
                        matched = info
                        break
            if not matched and docs:
                matched = docs[0].get('albumDocInfo', {}) or {}
            if matched:
                album_id = str(matched.get('albumId', '') or '')
                vod['vod_name'] = matched.get('albumTitle') or search_key
                vod['vod_pic'] = matched.get('albumVImage', '') or ''
                vod['vod_remarks'] = matched.get('tvFocus', '') or ''
                vod['vod_content'] = matched.get('description', '') or ''
                vod['vod_year'] = str(matched.get('releaseDate', '') or '')[:4]
        except Exception as e:
            self._log('iqiyi 详情搜索异常 ' + str(e))

        if album_id:
            try:
                aurl = ('https://pcw-api.iqiyi.com/albums/album/avlistinfo'
                        '?aid={}&size=200&page=1').format(album_id)
                a = (self._get_json(aurl, self.mobile_headers) or {}).get('data', {}) or {}
                if a.get('name'):
                    vod['vod_name'] = a['name']
                if a.get('description') and not vod['vod_content']:
                    vod['vod_content'] = a['description']
                cats = a.get('categories', []) or []
                if cats:
                    vod['type_name'] = ','.join([c.get('name', '') for c in cats if c.get('name')])
                vod['vod_area'] = a.get('areas', '') or vod['vod_area']
                vod['vod_year'] = str(a.get('year', '') or vod['vod_year'])
                people = a.get('people', {}) or {}
                actors = people.get('main_charactor', []) or []
                if actors:
                    vod['vod_actor'] = ','.join([x.get('name', '') for x in actors if x.get('name')])
                if not vod['vod_pic']:
                    pic = a.get('imageUrl', '') or ''
                    if pic.endswith('.jpg'):
                        pic = pic.replace('.jpg', '_579_772.jpg?caplist=jpg,webp')
                    vod['vod_pic'] = pic
            except Exception as e:
                self._log('iqiyi avlistinfo 异常 ' + str(e))

        vod['vod_id'] = album_id or search_key
        return vod if vod['vod_name'] else None

    # ---------- 芒果详情 ----------
    def _mgtv_detail(self, video_id):
        info_url = ('https://pcweb.api.mgtv.com/video/info'
                    '?allowedRC=1&vid={}&type=b&_support=10000000').format(video_id)
        data = self._get_json(info_url, self.mobile_headers)
        vod = self._new_vod(video_id, '')
        try:
            info = (data.get('data') or {}).get('info') or {}
            detail = info.get('detail') or {}
            vod['vod_name'] = info.get('title', '')
            vod['type_name'] = detail.get('kind', '')
            vod['vod_year'] = detail.get('releaseTime', '')
            vod['vod_area'] = detail.get('area', '')
            vod['vod_actor'] = detail.get('leader', '')
            vod['vod_director'] = detail.get('director', '')
            vod['vod_content'] = detail.get('story', '')
            vod['vod_remarks'] = detail.get('updateInfo', '')
            if detail.get('img'):
                vod['vod_pic'] = detail['img']
        except Exception as e:
            self._log('mgtv 详情异常 ' + str(e))
        return vod if vod['vod_name'] else None

    # ---------- 腾讯详情 ----------
    def _tencent_detail(self, cid):
        body = {
            "page_params": {
                "req_from": "web", "cid": cid, "vid": "", "lid": "",
                "page_type": "detail_operation",
                "page_id": "detail_page_introduction"
            },
            "has_cache": 1
        }
        try:
            url = ('{}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
                   '?video_appid=3000010&vplatform=2&vversion_name=8.2.96'
                   ).format(self.TENCENT_API)
            data = self.post(url, json=body, headers=self.tencent_headers).json()
            detail = (data['data']['module_list_datas'][0]['module_datas'][0]
                          ['item_data_lists']['item_datas'][0])
            params = detail['item_params']
            actors = [s['item_params']['name'] for s in
                      detail.get('sub_items', {}).get('star_list', {}).get('item_datas', [])
                      if s.get('item_params', {}).get('name')]
            vod = self._new_vod(cid, params.get('title', ''))
            if not vod['vod_name']:
                return None
            vod['type_name'] = params.get('sub_genre', '')
            vod['vod_pic'] = (params.get('new_pic_vt') or params.get('image_url')
                              or params.get('new_pic_hz') or '')
            vod['vod_year'] = params.get('year', '')
            vod['vod_area'] = params.get('area_name', '')
            vod['vod_remarks'] = (params.get('holly_online_time')
                                  or params.get('hotval', ''))
            vod['vod_actor'] = ','.join(actors)
            vod['vod_content'] = params.get('cover_description', '')
            return vod
        except Exception as e:
            self._log('tencent 详情异常 ' + str(e))
            return None

    # ---------- B站详情 ----------
    def _bili_detail(self, show_id):
        url = '{}?season_id={}'.format(self.BILI_DETAIL, show_id)
        data = self._get_json(url, self.bili_headers)
        vod = self._new_vod(show_id, '')
        try:
            result = (data or {}).get('result', {}) or {}
            vod['vod_name'] = self._remove_html_tags(result.get('title', ''))
            vod['vod_pic'] = result.get('cover', '')
            vod['type_name'] = result.get('share_sub_title', '')
            vod['vod_actor'] = (result.get('actors', '') or '').replace('\n', '，')
            vod['vod_content'] = self._remove_html_tags(result.get('evaluate', ''))
        except Exception as e:
            self._log('bili 详情异常 ' + str(e))
        return vod if vod['vod_name'] else None

    def playerContent(self, flag, id, vipFlags):
        return {'parse': 0, 'url': '', 'msg': '请在详情页选择播放来源'}

    def localProxy(self, param):
        pass

    # ==================== 私有辅助 ====================
    def _page(self, vlist, pg, limit=24):
        return {'list': vlist, 'page': int(pg), 'pagecount': int(pg) + 1,
                'limit': limit, 'total': 999999}

    def _fetch_html(self, url, headers=None):
        rsp = self.fetch(url, headers=headers or self.headers)
        return pq(self.cleanText(rsp.text))

    def _get_json(self, url, headers=None, cookies=None):
        headers = headers or self.headers
        try:
            if cookies is not None:
                rsp = self.fetch(url, headers=headers, cookies=cookies)
            else:
                rsp = self.fetch(url, headers=headers)
        except Exception as e:
            self._log('fetch 异常 ' + str(e))
            return {}
        if hasattr(rsp, 'json'):
            try:
                return rsp.json()
            except Exception:
                pass
        text = rsp.text if hasattr(rsp, 'text') else rsp
        if isinstance(text, bytes):
            text = text.decode('utf-8', 'ignore')
        if not isinstance(text, str):
            return text if isinstance(text, dict) else {}
        text = text.strip()
        if not text:
            return {}
        try:
            return json.loads(self._clean_text(text))
        except Exception:
            return {}

    def _normalize_extend(self, extend):
        if isinstance(extend, str):
            try:
                extend = json.loads(extend)
            except Exception:
                extend = {}
        return extend if isinstance(extend, dict) else {}

    def _parse_tag(self, tag_str):
        if not tag_str:
            return {}
        try:
            return json.loads(tag_str) if isinstance(tag_str, str) else tag_str
        except Exception:
            return {}

    def _right_corner(self, item):
        rc = item.get('rightCorner') or {}
        return rc.get('text', '') if isinstance(rc, dict) else ''

    def _build_filter_params(self, extend):
        params = {'sort': extend.get('sort', '75')}
        for k, v in extend.items():
            if k != 'sort' and k in self.TENCENT_KEYS and v is not None and str(v) != '':
                params[k] = str(v)
        return '&'.join(['{}={}'.format(k, v) for k, v in params.items()])

    def _error_result(self, message):
        return {'list': [], 'msg': message}

    def _remove_html_tags(self, src):
        if src is None:
            return ''
        clean = re.compile('<.*?>')
        return re.sub(clean, '', str(src))

    def _clean_text(self, text):
        if text is None:
            return ''
        text = str(text)
        return text.replace('\u200b', '').replace('\ufeff', '')

    def _bili_cookie(self):
        cookie = self.extendDict.get('cookie', '')
        if 'json' in self.extendDict:
            try:
                r = self.fetch(self.extendDict['json'], timeout=10)
                j = r.json()
                if 'cookie' in j:
                    cookie = j['cookie']
            except Exception:
                pass
        if cookie == '':
            cookie = '{}'
        elif isinstance(cookie, str) and cookie.startswith('http'):
            cookie = self.fetch(cookie, timeout=10).text.strip()
        try:
            if isinstance(cookie, dict):
                cookie = json.dumps(cookie, ensure_ascii=False)
        except Exception:
            pass
        cookies, _, _ = self._bili_parse_cookie(cookie)
        return cookies

    def _bili_parse_cookie(self, cookie):
        if '{' in cookie and '}' in cookie:
            try:
                cookies = json.loads(cookie)
            except Exception:
                cookies = {}
        else:
            cookies = dict([co.strip().split('=', 1)
                            for co in cookie.strip(';').split(';') if '=' in co])
        return cookies, '', ''

    # ---------- 各站筛选 ----------
    def _iqiyi_filter(self):
        return [
            {'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': '2'}, {'n': '电视剧', 'v': '2'},
                {'n': '电影', 'v': '1'}, {'n': '综艺', 'v': '6'},
                {'n': '动漫', 'v': '4'}, {'n': '少儿', 'v': '15'},
                {'n': '纪录片', 'v': '3'}, {'n': '短剧', 'v': '35'},
                {'n': '知识', 'v': '31'}]},
            {'key': 'is_purchase', 'name': '付费类型', 'value': [
                {'n': '全部', 'v': ''}, {'n': '免费', 'v': '0'}, {'n': 'VIP', 'v': '1'}]},
            {'key': 'mode', 'name': '排序', 'value': [
                {'n': '最新', 'v': '24'}, {'n': '最热', 'v': '11'}, {'n': '评分', 'v': '4'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}] + [{'n': str(y), 'v': str(y)} for y in range(2026, 2014, -1)]},
            {'key': 'region', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '内地', 'v': '内地'}, {'n': '港台', 'v': '港台'},
                {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
                {'n': '泰国', 'v': '泰国'}, {'n': '英国', 'v': '英国'}]},
        ]

    def _mgtv_filter(self):
        return [
            {'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': '2'}, {'n': '电视剧', 'v': '2'},
                {'n': '电影', 'v': '3'}, {'n': '综艺', 'v': '1'},
                {'n': '动漫', 'v': '50'}, {'n': '纪录片', 'v': '51'},
                {'n': '教育', 'v': '115'}, {'n': '少儿', 'v': '10'}]},
            {'key': 'chargeInfo', 'name': '付费类型', 'value': [
                {'n': '全部', 'v': 'all'}, {'n': '免费', 'v': 'b1'}, {'n': 'vip', 'v': 'b2'},
                {'n': 'VIP用券', 'v': 'b3'}, {'n': '付费点播', 'v': 'b4'}]},
            {'key': 'sort', 'name': '排序', 'value': [
                {'n': '最新', 'v': 'c1'}, {'n': '最热', 'v': 'c2'}, {'n': '知乎高分', 'v': 'c4'}]},
            {'key': 'year', 'name': '年代', 'value': [
                {'n': '全部', 'v': 'all'}] + [{'n': str(y), 'v': str(y)} for y in range(2026, 2003, -1)]},
        ]

    def _youku_filter(self):
        return [
            {'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': '电视剧'}, {'n': '电视剧', 'v': '电视剧'},
                {'n': '电影', 'v': '电影'}, {'n': '综艺', 'v': '综艺'},
                {'n': '动漫', 'v': '动漫'}, {'n': '少儿', 'v': '少儿'},
                {'n': '纪录片', 'v': '纪录片'}]},
            {'key': 'chargeInfo', 'name': '付费类型', 'value': [
                {'n': '全部', 'v': ''}, {'n': '免费', 'v': '免费'}, {'n': 'VIP', 'v': 'VIP'}]},
            {'key': 'order', 'name': '排序', 'value': [
                {'n': '最新', 'v': '最新'}, {'n': '最热', 'v': '最热'}, {'n': '评分', 'v': '评分'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': ''}] + [{'n': str(y), 'v': str(y)} for y in range(2026, 2014, -1)]},
            {'key': 'area', 'name': '地区', 'value': [
                {'n': '全部', 'v': ''}, {'n': '内地', 'v': '内地'}, {'n': '港台', 'v': '港台'},
                {'n': '美国', 'v': '美国'}, {'n': '韩国', 'v': '韩国'}, {'n': '日本', 'v': '日本'},
                {'n': '泰国', 'v': '泰国'}, {'n': '英国', 'v': '英国'}]},
        ]

    def _tencent_filter(self):
        fallback = [
            {'key': 'cate', 'name': '分类', 'value': [
                {'n': '全部', 'v': '100113'}, {'n': '电视剧', 'v': '100113'},
                {'n': '电影', 'v': '100173'}, {'n': '综艺', 'v': '100109'},
                {'n': '动漫', 'v': '100119'}, {'n': '少儿', 'v': '100150'},
                {'n': '纪录片', 'v': '100105'}, {'n': '短剧', 'v': '120188'}]},
            {'key': 'sort', 'name': '排序', 'value': [
                {'n': '最热', 'v': '75'}, {'n': '最新', 'v': '83'}, {'n': '好评', 'v': '81'}]},
        ]
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._get_tencent_filter_data, '100113')
                _, data = future.result()
            if not data or not data.get('data', {}).get('module_list_datas'):
                return fallback
            filter_dict = {}
            for mld in data['data']['module_list_datas']:
                for md in mld.get('module_datas', []):
                    for item in md.get('item_data_lists', {}).get('item_datas', []):
                        params = item.get('item_params', {})
                        key = params.get('index_item_key')
                        if not key:
                            continue
                        if key not in filter_dict:
                            filter_dict[key] = {'key': key,
                                                'name': params.get('index_name', key),
                                                'value': []}
                        filter_dict[key]['value'].append({
                            'n': params.get('option_name', ''),
                            'v': params.get('option_value', ''),
                        })
            result = [fallback[0]]
            result += list(filter_dict.values())
            return result
        except Exception:
            return fallback

    def _get_tencent_filter_data(self, cid):
        body = {
            "page_params": {
                "channel_id": cid, "filter_params": "sort=75",
                "page_type": "channel_operation",
                "page_id": "channel_list_second_page"
            }
        }
        try:
            url = ('{}/trpc.universal_backend_service.page_server_rpc.PageServer/GetPageData'
                   '?video_appid=1000005&vplatform=2&vversion_name=8.9.10&new_mark_label_enabled=1'
                   ).format(self.TENCENT_API)
            data = self.post(url, json=body, headers=self.tencent_headers).json()
        except Exception:
            data = {}
        return cid, data

    def _bili_filter_default(self):
        return [
            {'key': 'cate', 'name': '分类', 'value': [
                {'n': '番剧', 'v': '1'}, {'n': '国创', 'v': '4'},
                {'n': '电影', 'v': '2'}, {'n': '综艺', 'v': '7'},
                {'n': '电视剧', 'v': '5'}]},
            {'key': 'season_status', 'name': '付费', 'value': [
                {'n': '全部', 'v': '-1'}, {'n': '免费', 'v': '1'},
                {'n': '付费', 'v': '2,6'}, {'n': '大会员', 'v': '4,6'}]},
            {'key': 'year', 'name': '年份', 'value': [
                {'n': '全部', 'v': '-1'}] + [{'n': str(y), 'v': '[{}, {})'.format(y, y + 1)} for y in range(2026, 2000, -1)]},
        ]