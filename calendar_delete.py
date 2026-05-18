import json
import os
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
            if 'dateTime' in start:
                t = datetime.fromisoformat(start['dateTime']).astimezone(TAIWAN_TZ)
                time_str = t.strftime('%m/%d %H:%M')
            else:
                time_str = start.get('date', '')
            title = e.get('summary', '（無標題）')
            lines.append(f'{i}. {time_str}　{title}')
            refs.append((cal_id, e['id'], title))

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
