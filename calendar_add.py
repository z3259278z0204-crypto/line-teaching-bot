import json
import os
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone, timedelta
from sheets_helper import find_price, append_row

TAIWAN_TZ = timezone(timedelta(hours=8))
CALENDAR_ID = 'z3259278z0204@gmail.com'


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


def _parse(text):
    """解析 '明天10點 體能課' 或 '5/20 下午3點 家長會 地點：學校' """
    now = datetime.now(TAIWAN_TZ)
    original = text

    # 日期
    date = None
    if text.startswith('今天'):
        date = now.date(); text = text[2:].strip()
    elif text.startswith('明天'):
        date = (now + timedelta(days=1)).date(); text = text[2:].strip()
    elif text.startswith('後天'):
        date = (now + timedelta(days=2)).date(); text = text[2:].strip()
    else:
        m = re.match(r'(\d{1,2})/(\d{1,2})', text)
        if m:
            month, day = int(m.group(1)), int(m.group(2))
            try:
                date = now.date().replace(month=month, day=day)
                if date < now.date():
                    date = date.replace(year=date.year + 1)
            except ValueError:
                return None, '日期格式有誤，請用 MM/DD（例如 5/20）'
            text = text[m.end():].strip()
        else:
            return None, '請加上日期，例如：今天、明天、5/20'

    # 上下午
    afternoon = bool(re.search(r'下午|午後|PM|pm', text))
    text = re.sub(r'下午|午後|PM|pm|上午|早上|AM|am', '', text).strip()

    # 時間
    hour, minute = 9, 0
    m = re.search(r'(\d{1,2})[點時:](\d{0,2})(半)?', text)
    if m:
        hour = int(m.group(1))
        minute = 30 if m.group(3) else (int(m.group(2)) if m.group(2).isdigit() else 0)
        if afternoon and hour < 12:
            hour += 12
        text = (text[:m.start()] + text[m.end():]).strip()

    # 地點
    location = None
    loc_m = re.search(r'地點[：:]\s*(.+)', text)
    if loc_m:
        location = loc_m.group(1).strip()
        text = text[:loc_m.start()].strip()

    title = text.strip() or '新行程'

    start = datetime(date.year, date.month, date.day, hour, minute, tzinfo=TAIWAN_TZ)
    end = start + timedelta(hours=1)
    return (title, start, end, location), None


def add_event(raw_text):
    result, err = _parse(raw_text.strip())
    if err:
        return f'⚠️ {err}\n\n格式：新增行程 明天10點 體能課\n或：新增行程 5/20 下午3點 家長會 地點：學校'

    title, start, end, location = result
    try:
        token = _get_access_token()
        body = {
            'summary': title,
            'start': {'dateTime': start.isoformat(), 'timeZone': 'Asia/Taipei'},
            'end': {'dateTime': end.isoformat(), 'timeZone': 'Asia/Taipei'},
            'colorId': '3',
            'reminders': {'useDefault': False, 'overrides': []},
        }
        if location:
            body['location'] = location

        data = json.dumps(body).encode()
        url = f'https://www.googleapis.com/calendar/v3/calendars/{urllib.parse.quote(CALENDAR_ID)}/events'
        req = urllib.request.Request(url, data=data, headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        })
        with urllib.request.urlopen(req) as resp:
            e = json.loads(resp.read())

        time_str = start.strftime('%H:%M')
        date_str = start.strftime('%m/%d')
        loc_str = f'\n📍 {location}' if location else ''

        # 自動依價目表寫入薪資
        salary_str = ''
        try:
            price, keyword = find_price(title)
            if price is not None:
                append_row('薪資', {
                    '日期': start.strftime('%Y/%m/%d'),
                    '時間': time_str,
                    '標題': title,
                    '單價': price,
                    '備註': f'匹配關鍵字：{keyword}',
                })
                salary_str = f'\n💰 已記薪資 ${price}（{keyword}）'
            elif keyword:
                salary_str = f'\n⚠️ 價目表「{keyword}」單價格式錯誤，未記薪資'
            else:
                salary_str = '\n⚠️ 價目表查無此課程，未記薪資'
        except Exception as sex:
            salary_str = f'\n⚠️ 薪資寫入失敗：{str(sex)[:50]}'

        return f'✅ 行程已新增！\n\n📅 {date_str} {time_str}\n📌 {title}{loc_str}{salary_str}'
    except Exception as ex:
        return f'⚠️ 新增失敗：{str(ex)}'
