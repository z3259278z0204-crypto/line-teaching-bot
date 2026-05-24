import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta

TAIWAN_TZ = timezone(timedelta(hours=8))
CALENDAR_IDS = [
    'z3259278z0204@gmail.com',
    'classroom108338620680865803594@group.calendar.google.com',
]


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


def list_upcoming(days=7):
    """列出未來 N 天的行程，回傳 (顯示文字, [(cal_id, event_id, summary), ...])"""
    try:
        token = _get_access_token()
        now = datetime.now(TAIWAN_TZ)
        end = now + timedelta(days=days)
        params = urllib.parse.urlencode({
            'timeMin': now.isoformat(),
            'timeMax': end.isoformat(),
            'singleEvents': 'true',
            'orderBy': 'startTime',
            'maxResults': 30
        })
        events_with_cal = []
        for cal_id in CALENDAR_IDS:
            url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}/events?{params}'
            req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
            try:
                with urllib.request.urlopen(req) as resp:
                    items = json.loads(resp.read()).get('items', [])
                    for e in items:
                        events_with_cal.append((cal_id, e))
            except Exception:
                pass

        events_with_cal.sort(key=lambda x: x[1].get('start', {}).get('dateTime', x[1].get('start', {}).get('date', '')))

        if not events_with_cal:
            return '未來7天沒有行程可刪除。', []

        lines = ['📋 未來7天的行程，回覆編號刪除：\n']
        refs = []
        for i, (cal_id, e) in enumerate(events_with_cal, 1):
            start = e.get('start', {})
            event_date = ''
            event_time = ''
            if 'dateTime' in start:
                t = datetime.fromisoformat(start['dateTime']).astimezone(TAIWAN_TZ)
                time_display = t.strftime('%m/%d %H:%M')
                event_date = t.strftime('%Y-%m-%d')
                event_time = t.strftime('%H:%M')
            else:
                time_display = start.get('date', '')
                event_date = start.get('date', '')
            title = e.get('summary', '（無標題）')
            lines.append(f'{i}. {time_display}　{title}')
            refs.append((cal_id, e['id'], title, event_date, event_time))

        lines.append('\n回覆數字刪除，或「取消」中止。')
        return '\n'.join(lines), refs
    except Exception as ex:
        return f'⚠️ 取得行程失敗：{ex}', []


def delete_event(cal_id, event_id):
    try:
        token = _get_access_token()
        url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}/events/{event_id}'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'}, method='DELETE')
        urllib.request.urlopen(req)
        return True
    except Exception:
        return False


def _parse_query(text):
    """解析 '5/27 16:15 輔大自主課' → (date_yyyy_mm_dd, time_hh_mm, title_substring)"""
    now = datetime.now(TAIWAN_TZ)
    date_str = None
    time_str = None

    if text.startswith('今天'):
        date_str = now.strftime('%Y-%m-%d')
        text = text[2:].strip()
    elif text.startswith('明天'):
        date_str = (now + timedelta(days=1)).strftime('%Y-%m-%d')
        text = text[2:].strip()
    elif text.startswith('後天'):
        date_str = (now + timedelta(days=2)).strftime('%Y-%m-%d')
        text = text[2:].strip()
    else:
        m = re.match(r'(\d{1,2})/(\d{1,2})', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            try:
                d = now.date().replace(month=month, day=day)
                if d < now.date():
                    d = d.replace(year=d.year + 1)
                date_str = d.strftime('%Y-%m-%d')
            except ValueError:
                pass
            text = text[m.end():].strip()

    m = re.search(r'(\d{1,2})[點時:](\d{0,2})', text)
    if m:
        hour = int(m.group(1))
        minute = int(m.group(2)) if m.group(2).isdigit() else 0
        time_str = f'{hour:02d}:{minute:02d}'
        text = (text[:m.start()] + text[m.end():]).strip()

    title = text.strip() or None
    return date_str, time_str, title


def _fetch_upcoming(days):
    token = _get_access_token()
    now = datetime.now(TAIWAN_TZ)
    end = now + timedelta(days=days)
    params = urllib.parse.urlencode({
        'timeMin': now.isoformat(),
        'timeMax': end.isoformat(),
        'singleEvents': 'true',
        'orderBy': 'startTime',
        'maxResults': 100
    })
    out = []
    for cal_id in CALENDAR_IDS:
        url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}/events?{params}'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
        try:
            with urllib.request.urlopen(req) as resp:
                for e in json.loads(resp.read()).get('items', []):
                    out.append((cal_id, e))
        except Exception:
            pass
    out.sort(key=lambda x: x[1].get('start', {}).get('dateTime', x[1].get('start', {}).get('date', '')))
    return out


def _normalize_event(cal_id, e):
    start = e.get('start', {})
    if 'dateTime' in start:
        t = datetime.fromisoformat(start['dateTime']).astimezone(TAIWAN_TZ)
        return cal_id, e['id'], e.get('summary', ''), t.strftime('%Y-%m-%d'), t.strftime('%H:%M')
    return cal_id, e['id'], e.get('summary', ''), start.get('date', ''), ''


def find_and_delete(query):
    """根據自然語言條件刪除。回傳 (訊息, refs_for_state_machine_or_None)"""
    date_str, time_str, title = _parse_query(query)
    if not (date_str or title):
        return '⚠️ 至少要給日期或標題，例如：\n刪除行程 5/27 16:15 輔大自主課', None

    try:
        events = _fetch_upcoming(30)
    except Exception as ex:
        return f'⚠️ 取得行程失敗：{ex}', None

    matches = []
    for cal_id, e in events:
        cid, eid, t_title, ed, et = _normalize_event(cal_id, e)
        if date_str and ed != date_str:
            continue
        if time_str and et != time_str:
            continue
        if title and title not in t_title:
            continue
        matches.append((cid, eid, t_title, ed, et))

    if not matches:
        return '⚠️ 找不到符合的行程（30 天內）', None

    if len(matches) > 1:
        lines = [f'🔍 找到 {len(matches)} 筆符合，回覆編號刪除：\n']
        refs = []
        for i, (cid, eid, t, ed, et) in enumerate(matches, 1):
            lines.append(f'{i}. {ed} {et} {t}')
            refs.append((cid, eid, t, ed, et))
        lines.append('\n回覆數字刪除，或「取消」中止。')
        return '\n'.join(lines), refs

    cid, eid, t_title, ed, et = matches[0]
    if not delete_event(cid, eid):
        return f'⚠️ 刪除失敗：{t_title}', None

    salary_msg = ''
    try:
        from sheets_helper import delete_row_by_dict
        ed_slash = ed.replace('-', '/')
        if delete_row_by_dict('薪資', {'日期': ed_slash, '時間': et, '標題': t_title}):
            salary_msg = '\n💸 對應薪資記錄已移除'
    except Exception:
        pass

    return f'🗑️ 已刪除：{ed} {et} {t_title}{salary_msg}', None
