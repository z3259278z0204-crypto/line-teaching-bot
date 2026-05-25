from datetime import datetime, timezone, timedelta
from sheets_helper import read_all, append_row, delete_rows_by_indices

TAIWAN_TZ = timezone(timedelta(hours=8))
PARKING_SHEET = '停車費'


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def save_parking(amount, location='', notes=''):
    append_row(PARKING_SHEET, {
        '日期': datetime.now(TAIWAN_TZ).strftime('%Y/%m/%d'),
        '金額': amount,
        '地點': location,
        '備註': notes,
    })


def monthly_total(year=None, month=None):
    """回傳 (本月總金額, 次數)"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month
    rows = read_all(PARKING_SHEET)
    total = 0
    count = 0
    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            total += int(float(str(row.get('金額', '0')).strip() or 0))
            count += 1
        except (ValueError, TypeError):
            continue
    return total, count


def monthly_summary(year=None, month=None):
    """本月停車費摘要。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    rows = read_all(PARKING_SHEET)
    items = []
    total = 0
    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            a = int(float(str(row.get('金額', '0')).strip() or 0))
        except (ValueError, TypeError):
            continue
        loc = (row.get('地點') or '').strip()
        items.append((d, a, loc))
        total += a

    if not items:
        return f'🅿️ {year}/{month:02d} 還沒有停車費記錄'

    items.sort(key=lambda x: x[0])
    lines = [f'🅿️ {year}/{month:02d} 停車費摘要', '']
    for d, a, loc in items:
        loc_str = f' @{loc}' if loc else ''
        lines.append(f'{d.strftime("%m/%d")} ${a:,}{loc_str}')
    lines.append('')
    lines.append('━━━━━━━━━━')
    lines.append(f'🅿️ 共 {len(items)} 次｜合計 ${total:,}')
    return '\n'.join(lines)


def delete_last_parking():
    """刪除最後一列停車費，回傳被刪內容字串或 None。"""
    rows = read_all(PARKING_SHEET)
    if not rows:
        return None
    last = rows[-1]
    row_index = len(rows) + 1
    delete_rows_by_indices(PARKING_SHEET, [row_index])

    parts = [(last.get('日期') or '').strip()]
    try:
        a = int(float(str(last.get('金額', '0')).strip() or 0))
        parts.append(f'${a:,}')
    except (ValueError, TypeError):
        pass
    loc = (last.get('地點') or '').strip()
    if loc:
        parts.append(f'@{loc}')
    return ' '.join([p for p in parts if p])
