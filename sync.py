"""Calendar ↔ 薪資 Sheet 同步：
- 比對 Google Calendar 與「薪資」分頁，補上 Calendar 上有但 Sheet 漏掉的、移除 Sheet 上有但 Calendar 已刪除的
- 比對基準是 (日期, 時間, 標題) 三欄
"""
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from sheets_helper import read_all, append_row, delete_row_by_dict

TAIWAN_TZ = timezone(timedelta(hours=8))
CALENDAR_IDS = [
    'z3259278z0204@gmail.com',
    'classroom108338620680865803594@group.calendar.google.com',
]
SALARY_SHEET = '薪資'

# 同步範圍：過去 90 天到未來 90 天
PAST_DAYS = 90
FUTURE_DAYS = 90


def _get_access_token():
    data = urllib.parse.urlencode({
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'refresh_token': os.environ['GOOGLE_REFRESH_TOKEN'],
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['access_token']


def _fetch_events():
    token = _get_access_token()
    now = datetime.now(TAIWAN_TZ)
    time_min = (now - timedelta(days=PAST_DAYS)).isoformat()
    time_max = (now + timedelta(days=FUTURE_DAYS)).isoformat()
    params = urllib.parse.urlencode({
        'timeMin': time_min,
        'timeMax': time_max,
        'singleEvents': 'true',
        'orderBy': 'startTime',
        'maxResults': 2500,
    })
    events = []
    for cal_id in CALENDAR_IDS:
        url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}/events?{params}'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req) as resp:
                events.extend(json.loads(resp.read()).get('items', []))
        except Exception:
            pass
    return events


def _event_key(e):
    """從 calendar event 取出 (日期 yyyy/mm/dd, 時間 HH:MM, 標題)。回傳 None 表示忽略此事件。"""
    start = e.get('start', {})
    if 'dateTime' not in start:
        return None  # 跳過整天事件
    t = datetime.fromisoformat(start['dateTime']).astimezone(TAIWAN_TZ)
    title = (e.get('summary') or '').strip()
    if not title:
        return None
    return t.strftime('%Y/%m/%d'), t.strftime('%H:%M'), title


def _load_price_table():
    """讀一次價目表，回傳 [(關鍵字, 單價), ...]"""
    rows = read_all('價目表')
    out = []
    for r in rows:
        kw = (r.get('關鍵字') or '').strip()
        if not kw:
            continue
        try:
            price = int(str(r.get('單價', '')).strip())
        except (ValueError, TypeError):
            continue
        out.append((kw, price))
    return out


def _match_price(title, price_table):
    for kw, price in price_table:
        if kw in title:
            return price, kw
    return None, None


def sync_salary():
    """執行雙向同步，回傳人類可讀的訊息。"""
    try:
        events = _fetch_events()
    except Exception as ex:
        return f'⚠️ 取得行事曆失敗：{ex}'

    try:
        price_table = _load_price_table()
    except Exception as ex:
        return f'⚠️ 讀取價目表失敗：{ex}'

    # 篩出有匹配價目表的 events
    matched_events = []  # [(date_str, time_str, title, price, keyword)]
    skipped_no_price = 0
    for e in events:
        key = _event_key(e)
        if not key:
            continue
        d, t, title = key
        price, keyword = _match_price(title, price_table)
        if price is None:
            skipped_no_price += 1
            continue
        matched_events.append((d, t, title, price, keyword))

    # 讀取現有薪資
    salary_rows = read_all(SALARY_SHEET)
    existing_keys = set()
    for r in salary_rows:
        d = (r.get('日期') or '').strip()
        t = (r.get('時間') or '').strip()
        title = (r.get('標題') or '').strip()
        if d and t and title:
            existing_keys.add((d, t, title))

    event_keys = {(d, t, title) for d, t, title, _, _ in matched_events}

    # 補：Calendar 有，Sheet 沒有
    added = 0
    for d, t, title, price, keyword in matched_events:
        if (d, t, title) not in existing_keys:
            try:
                append_row(SALARY_SHEET, {
                    '日期': d, '時間': t, '標題': title, '單價': price,
                    '備註': f'匹配關鍵字：{keyword}（自動同步）',
                })
                added += 1
            except Exception:
                pass

    # 移：Sheet 有，Calendar 沒有（限同步範圍內的日期才刪，避免誤刪歷史資料）
    now = datetime.now(TAIWAN_TZ)
    cutoff_past = now - timedelta(days=PAST_DAYS)
    removed = 0
    for r in salary_rows:
        d_str = (r.get('日期') or '').strip()
        t_str = (r.get('時間') or '').strip()
        title = (r.get('標題') or '').strip()
        if not (d_str and t_str and title):
            continue
        try:
            d_obj = datetime.strptime(d_str, '%Y/%m/%d').replace(tzinfo=TAIWAN_TZ)
        except ValueError:
            continue
        if d_obj < cutoff_past:
            continue  # 超出同步範圍，不動
        if (d_str, t_str, title) not in event_keys:
            try:
                if delete_row_by_dict(SALARY_SHEET, {
                    '日期': d_str, '時間': t_str, '標題': title,
                }):
                    removed += 1
            except Exception:
                pass

    return (
        f'🔄 同步完成\n\n'
        f'➕ 新增：{added} 筆（Calendar 有但 Sheet 漏的）\n'
        f'➖ 移除：{removed} 筆（Sheet 有但 Calendar 已刪的）\n'
        f'🔍 略過：{skipped_no_price} 筆 Calendar 事件（價目表查無）\n'
        f'📅 範圍：過去 {PAST_DAYS} 天 ~ 未來 {FUTURE_DAYS} 天'
    )
