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
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['access_token']


def _fetch_events(access_token, day: datetime):
    day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day.replace(hour=23, minute=59, second=59, microsecond=0)
    params = urllib.parse.urlencode({
        'timeMin': day_start.isoformat(),
        'timeMax': day_end.isoformat(),
        'singleEvents': 'true',
        'orderBy': 'startTime',
        'maxResults': '20',
    })
    all_events = []
    for cal_id in CALENDAR_IDS:
        url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(cal_id)}/events?{params}'
        req = urllib.request.Request(url, headers={'Authorization': f'Bearer {access_token}'})
        try:
            with urllib.request.urlopen(req) as resp:
                all_events.extend(json.loads(resp.read()).get('items', []))
        except Exception:
            pass
    all_events.sort(key=lambda e: e.get('start', {}).get('dateTime', e.get('start', {}).get('date', '')))
    return all_events


def _format(events, label):
    if not events:
        return f'📅 {label}\n\n沒有行程，好好休息！'
    lines = [f'📅 {label}\n']
    for e in events:
        start = e.get('start', {})
        if 'dateTime' in start:
            t = datetime.fromisoformat(start['dateTime']).astimezone(TAIWAN_TZ)
            time_str = t.strftime('%H:%M')
        else:
            time_str = '全天'
        title = e.get('summary', '（無標題）')
        lines.append(f'• {time_str}　{title}')
        if e.get('location'):
            lines.append(f'  📍 {e["location"]}')
    lines.append(f'\n共 {len(events)} 件行程')
    return '\n'.join(lines)


def query_schedule(offset_days=0):
    try:
        access_token = _get_access_token()
        now = datetime.now(TAIWAN_TZ)
        target = now + timedelta(days=offset_days)
        weekday_map = {
            'Monday': '週一', 'Tuesday': '週二', 'Wednesday': '週三',
            'Thursday': '週四', 'Friday': '週五', 'Saturday': '週六', 'Sunday': '週日'
        }
        label = target.strftime('%m/%d（') + weekday_map.get(target.strftime('%A'), '') + '）'
        events = _fetch_events(access_token, target)
        return _format(events, label)
    except Exception as e:
        return f'⚠️ 無法取得行程：{str(e)}'
