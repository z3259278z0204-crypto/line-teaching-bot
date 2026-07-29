from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sheets_helper import read_all
from fuel import monthly_total as fuel_monthly_total
from parking import monthly_total as parking_monthly_total
from ledger import monthly_total as ledger_monthly_total

TAIWAN_TZ = timezone(timedelta(hours=8))


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%m/%d', '%Y/%-m/%-d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _lessons_of(row):
    """讀「堂數」欄，空白或無欄位時當 1 堂處理。"""
    raw = str(row.get('堂數', '') or '').strip()
    if not raw:
        return 1
    try:
        n = int(float(raw))
    except (ValueError, TypeError):
        return 1
    return max(1, n)


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
        lessons = _lessons_of(row)
        amount = price * lessons
        total += amount
        count += lessons
        title = (row.get('標題') or '').strip() or '未分類'
        by_keyword[title]['count'] += lessons
        by_keyword[title]['amount'] += amount

    if count == 0:
        return f'📊 {year}/{month:02d} 還沒有薪資記錄'

    lines = [f'💰 {year}/{month:02d} 薪資摘要', '']
    sorted_items = sorted(by_keyword.items(), key=lambda x: -x[1]['amount'])
    for title, info in sorted_items:
        lines.append(f'• {title} × {info["count"]} = ${info["amount"]:,}')
    lines.append('')
    lines.append(f'📚 共 {count} 堂課')
    lines.append(f'💵 毛薪：${total:,}')

    try:
        fuel_amt, fuel_l, fuel_n = fuel_monthly_total(year, month)
    except Exception:
        fuel_amt, fuel_n = 0, 0
    try:
        park_amt, park_n = parking_monthly_total(year, month)
    except Exception:
        park_amt, park_n = 0, 0
    try:
        ledger_exp, _ = ledger_monthly_total(year, month)
    except Exception:
        ledger_exp = 0
    if fuel_amt > 0 or park_amt > 0 or ledger_exp > 0:
        if fuel_amt > 0:
            lines.append(f'⛽ 油費：−${fuel_amt:,}（{fuel_n} 次）')
        if park_amt > 0:
            lines.append(f'🅿️ 停車：−${park_amt:,}（{park_n} 次）')
        if ledger_exp > 0:
            lines.append(f'📒 記帳支出：−${ledger_exp:,}')
        net = total - fuel_amt - park_amt - ledger_exp
        lines.append(f'💎 淨薪：${net:,}')
    return '\n'.join(lines)


def monthly_net(year=None, month=None):
    """回傳本月工作收支數字明細（給練食記跨 bot 接的結構化資料）。
    net＝毛薪＋記帳收入 − 油費 − 停車 − 記帳支出（含記帳收入，比薪資摘要顯示更完整）。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    gross = 0
    lessons = 0
    for row in read_all('薪資'):
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            price = int(str(row.get('單價', '')).strip())
        except (ValueError, TypeError):
            continue
        n = _lessons_of(row)
        gross += price * n
        lessons += n

    try:
        fuel_amt, _, _ = fuel_monthly_total(year, month)
    except Exception:
        fuel_amt = 0
    try:
        park_amt, _ = parking_monthly_total(year, month)
    except Exception:
        park_amt = 0
    try:
        ledger_exp, ledger_inc = ledger_monthly_total(year, month)
    except Exception:
        ledger_exp, ledger_inc = 0, 0

    net = gross + ledger_inc - fuel_amt - park_amt - ledger_exp
    return {
        'year': year,
        'month': month,
        'lessons': lessons,
        'salary_gross': gross,
        'ledger_income': ledger_inc,
        'fuel': fuel_amt,
        'parking': park_amt,
        'ledger_expense': ledger_exp,
        'net': net,
    }


def _flex_row(icon, label, value, color):
    """薪資卡的一列：左 icon＋標籤、右金額（帶色）。"""
    return {
        'type': 'box', 'layout': 'horizontal',
        'contents': [
            {'type': 'text', 'text': f'{icon}  {label}', 'size': 'sm', 'color': '#555555', 'flex': 5},
            {'type': 'text', 'text': value, 'size': 'sm', 'color': color, 'align': 'end', 'flex': 4, 'weight': 'bold'},
        ],
    }


def monthly_summary_flex(year=None, month=None):
    """把薪資摘要做成 Flex 卡（與練食記同風格）。沒資料回 None，讓呼叫端退回文字。
    淨薪＝毛薪−油費−停車−記帳支出（比照文字摘要，不含記帳收入，決策B）。"""
    d = monthly_net(year, month)
    y, m = d['year'], d['month']
    gross, fuel, park, ledger_exp, lessons = (
        d['salary_gross'], d['fuel'], d['parking'], d['ledger_expense'], d['lessons']
    )
    if lessons == 0 and gross == 0:
        return None
    net = gross - fuel - park - ledger_exp

    rows = [
        {'type': 'separator', 'margin': 'lg'},
        _flex_row('📚', f'教課 {lessons} 堂', f'+${gross:,}', '#1F7A5A'),
    ]
    if fuel > 0:
        rows.append(_flex_row('⛽', '油費', f'−${fuel:,}', '#C0392B'))
    if park > 0:
        rows.append(_flex_row('🅿️', '停車', f'−${park:,}', '#C0392B'))
    if ledger_exp > 0:
        rows.append(_flex_row('📒', '記帳支出', f'−${ledger_exp:,}', '#C0392B'))

    bubble = {
        'type': 'bubble',
        'header': {
            'type': 'box', 'layout': 'vertical',
            'contents': [
                {'type': 'text', 'text': f'{y}/{m:02d} 薪資', 'weight': 'bold', 'size': 'lg', 'color': '#FFFFFF'},
                {'type': 'text', 'text': '教課 × 工作支出', 'size': 'xs', 'color': '#FFFFFFCC'},
            ],
            'backgroundColor': '#1F7A5A', 'paddingAll': '16px',
        },
        'body': {
            'type': 'box', 'layout': 'vertical', 'spacing': 'sm', 'paddingAll': '16px',
            'contents': [
                {
                    'type': 'box', 'layout': 'vertical', 'spacing': 'xs',
                    'contents': [
                        {'type': 'text', 'text': '本月淨薪', 'size': 'sm', 'color': '#8C8C8C'},
                        {'type': 'text', 'text': f'${net:,}', 'size': '3xl', 'weight': 'bold', 'color': '#1F7A5A', 'wrap': True},
                    ],
                },
                *rows,
            ],
        },
    }
    return {'alt_text': f'{y}/{m:02d} 淨薪 ${net:,}', 'bubble': bubble}


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
        lessons = _lessons_of(row)
        amount = price * lessons
        total += amount
        count += lessons
        title = (row.get('標題') or '').strip() or '未分類'
        by_title[title]['count'] += lessons
        by_title[title]['amount'] += amount

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
    try:
        fuel_amt, _, fuel_n = fuel_monthly_total(year, month)
    except Exception:
        fuel_amt, fuel_n = 0, 0
    try:
        park_amt, park_n = parking_monthly_total(year, month)
    except Exception:
        park_amt, park_n = 0, 0
    try:
        ledger_exp, _ = ledger_monthly_total(year, month)
    except Exception:
        ledger_exp = 0
    if fuel_amt > 0:
        bar_len_fuel = max(1, round(fuel_amt / max_amount * bar_max))
        lines.append('⛽ 油費')
        lines.append(f'{"▒" * bar_len_fuel} −${fuel_amt:,} ({fuel_n}次)')
        lines.append('')
    if park_amt > 0:
        bar_len_park = max(1, round(park_amt / max_amount * bar_max))
        lines.append('🅿️ 停車')
        lines.append(f'{"▒" * bar_len_park} −${park_amt:,} ({park_n}次)')
        lines.append('')
    if ledger_exp > 0:
        bar_len_led = max(1, round(ledger_exp / max_amount * bar_max))
        lines.append('📒 記帳支出')
        lines.append(f'{"▒" * bar_len_led} −${ledger_exp:,}')
        lines.append('')

    lines.append('━━━━━━━━━━')
    lines.append(f'💵 毛薪：${total:,} / {count} 堂')
    if fuel_amt > 0:
        lines.append(f'⛽ 油費：−${fuel_amt:,}')
    if park_amt > 0:
        lines.append(f'🅿️ 停車：−${park_amt:,}')
    if ledger_exp > 0:
        lines.append(f'📒 記帳支出：−${ledger_exp:,}')
    if fuel_amt > 0 or park_amt > 0 or ledger_exp > 0:
        lines.append(f'💎 淨薪：${total - fuel_amt - park_amt - ledger_exp:,}')
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
