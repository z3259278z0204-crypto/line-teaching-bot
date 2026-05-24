from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sheets_helper import read_all

TAIWAN_TZ = timezone(timedelta(hours=8))


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%m/%d', '%Y/%-m/%-d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def monthly_summary(year=None, month=None):
    """回傳指定月份的薪資摘要訊息。預設本月。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    rows = read_all('薪資')
    total = 0
    count = 0
    by_keyword = defaultdict(lambda: {'count': 0, 'amount': 0})

    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            price = int(str(row.get('單價', '')).strip())
        except (ValueError, TypeError):
            continue
        total += price
        count += 1
        title = (row.get('標題') or '').strip() or '未分類'
        by_keyword[title]['count'] += 1
        by_keyword[title]['amount'] += price

    if count == 0:
        return f'📊 {year}/{month:02d} 還沒有薪資記錄'

    lines = [f'💰 {year}/{month:02d} 薪資摘要', '']
    sorted_items = sorted(by_keyword.items(), key=lambda x: -x[1]['amount'])
    for title, info in sorted_items:
        lines.append(f'• {title} × {info["count"]} = ${info["amount"]:,}')
    lines.append('')
    lines.append(f'📚 共 {count} 堂課')
    lines.append(f'💵 合計：${total:,}')
    return '\n'.join(lines)


def monthly_chart(year=None, month=None):
    """文字長條圖呈現月薪資。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    rows = read_all('薪資')
    total = 0
    count = 0
    by_title = defaultdict(lambda: {'count': 0, 'amount': 0})

    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            price = int(str(row.get('單價', '')).strip())
        except (ValueError, TypeError):
            continue
        total += price
        count += 1
        title = (row.get('標題') or '').strip() or '未分類'
        by_title[title]['count'] += 1
        by_title[title]['amount'] += price

    if count == 0:
        return f'📊 {year}/{month:02d} 還沒有薪資記錄'

    sorted_items = sorted(by_title.items(), key=lambda x: -x[1]['amount'])
    max_amount = sorted_items[0][1]['amount']
    bar_max = 10

    lines = [f'📊 {year}/{month:02d} 薪資視覺化', '']
    for title, info in sorted_items:
        bar_len = max(1, round(info['amount'] / max_amount * bar_max))
        bar = '█' * bar_len
        lines.append(f'{title}')
        lines.append(f'{bar} ${info["amount"]:,} ({info["count"]}堂)')
        lines.append('')
    lines.append('━━━━━━━━━━')
    lines.append(f'💵 合計：${total:,} / {count} 堂')
    return '\n'.join(lines)


def list_prices():
    rows = read_all('價目表')
    if not rows:
        return '📋 價目表尚未建立。直接在 Google Sheet 的「價目表」分頁加：關鍵字、單價'
    lines = ['📋 目前價目表', '']
    for row in rows:
        kw = (row.get('關鍵字') or '').strip()
        price = (row.get('單價') or '').strip()
        if kw:
            lines.append(f'• {kw} ${price}')
    return '\n'.join(lines)
