"""明日器材：每天手動設定隔天上課要帶的器材，存進 Google Sheet。
午夜通知（Cloudflare Worker）會透過 /equipment/today 抓當天器材附在行程後。"""

from datetime import datetime, timezone, timedelta
from sheets_helper import ensure_sheet, read_all, append_row, delete_row_by_match

TAIWAN_TZ = timezone(timedelta(hours=8))
SHEET = '明日器材'
HEADERS = ['日期', '器材']
_WD = ['一', '二', '三', '四', '五', '六', '日']  # Monday=0


def _key(date_obj):
    return date_obj.strftime('%Y-%m-%d')


def label(date_obj):
    return f'{date_obj.month}/{date_obj.day}（週{_WD[date_obj.weekday()]}）'


def today_date():
    return datetime.now(TAIWAN_TZ).date()


def tomorrow_date():
    return (datetime.now(TAIWAN_TZ) + timedelta(days=1)).date()


def set_equipment(date_obj, items):
    """設定某天器材，覆蓋同日舊資料。"""
    ensure_sheet(SHEET, HEADERS)
    key = _key(date_obj)
    delete_row_by_match(SHEET, '日期', key)  # 先清掉同日舊設定
    append_row(SHEET, {'日期': key, '器材': items}, value_input='RAW')


def get_equipment(date_obj):
    """取某天器材字串，沒有回 ''。"""
    try:
        ensure_sheet(SHEET, HEADERS)
        key = _key(date_obj)
        for r in read_all(SHEET):
            if (r.get('日期') or '').strip() == key:
                return (r.get('器材') or '').strip()
    except Exception:
        pass
    return ''
