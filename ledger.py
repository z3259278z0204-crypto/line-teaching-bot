from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sheets_helper import read_all, append_row, delete_rows_by_indices, ensure_sheet

TAIWAN_TZ = timezone(timedelta(hours=8))
LEDGER_SHEET = '記帳'
HEADERS = ['日期', '類型', '類別', '金額', '備註']

EXPENSE_CATEGORIES = ['餐費', '教材教具', '交通', '生活用品', '娛樂', '醫療', '其他']
INCOME_CATEGORIES = ['副業', '獎金', '補助', '其他']


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d', '%Y/%m/%d %H:%M'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _read_rows():
    try:
        return read_all(LEDGER_SHEET)
    except Exception:
        return []


def save_entry(entry_type, category, amount, notes=''):
    ensure_sheet(LEDGER_SHEET, HEADERS)
    append_row(LEDGER_SHEET, {
        '日期': datetime.now(TAIWAN_TZ).strftime('%Y/%m/%d'),
        '類型': entry_type,
        '類別': category,
        '金額': amount,
        '備註': notes,
    })


def monthly_total(year=None, month=None):
    """回傳 (本月支出總額, 本月收入總額)。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month
    expense = 0
    income = 0
    for row in _read_rows():
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            amt = int(float(str(row.get('金額', '0')).strip() or 0))
        except (ValueError, TypeError):
            continue
        if (row.get('類型') or '').strip() == '收入':
            income += amt
        else:
            expense += amt
    return expense, income


def monthly_summary(year=None, month=None):
    """本月收支摘要，依類別分組。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    inc_by_cat = defaultdict(lambda: {'count': 0, 'amount': 0})
    exp_by_cat = defaultdict(lambda: {'count': 0, 'amount': 0})
    income_total = 0
    expense_total = 0

    for row in _read_rows():
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            amt = int(float(str(row.get('金額', '0')).strip() or 0))
        except (ValueError, TypeError):
            continue
        cat = (row.get('類別') or '').strip() or '未分類'
        if (row.get('類型') or '').strip() == '收入':
            inc_by_cat[cat]['count'] += 1
            inc_by_cat[cat]['amount'] += amt
            income_total += amt
        else:
            exp_by_cat[cat]['count'] += 1
            exp_by_cat[cat]['amount'] += amt
            expense_total += amt

    if not inc_by_cat and not exp_by_cat:
        return f'📒 {year}/{month:02d} 還沒有記帳記錄'

    lines = [f'📒 {year}/{month:02d} 收支摘要', '']

    if inc_by_cat:
        lines.append('📥 收入')
        for cat, info in sorted(inc_by_cat.items(), key=lambda x: -x[1]['amount']):
            lines.append(f'• {cat} ×{info["count"]} = ${info["amount"]:,}')
        lines.append('')

    if exp_by_cat:
        lines.append('📤 支出')
        for cat, info in sorted(exp_by_cat.items(), key=lambda x: -x[1]['amount']):
            lines.append(f'• {cat} ×{info["count"]} = ${info["amount"]:,}')
        lines.append('')

    lines.append('━━━━━━━━━━')
    lines.append(f'📥 收入 ${income_total:,}｜📤 支出 ${expense_total:,}')
    lines.append(f'💰 結餘：${income_total - expense_total:,}')
    return '\n'.join(lines)


def delete_last_entry():
    """刪除最後一列記帳，回傳被刪內容字串或 None。"""
    rows = _read_rows()
    if not rows:
        return None
    last = rows[-1]
    row_index = len(rows) + 1
    delete_rows_by_indices(LEDGER_SHEET, [row_index])

    parts = [(last.get('日期') or '').strip()]
    t = (last.get('類型') or '').strip()
    cat = (last.get('類別') or '').strip()
    if t:
        parts.append(t)
    if cat:
        parts.append(cat)
    try:
        amt = int(float(str(last.get('金額', '0')).strip() or 0))
        parts.append(f'${amt:,}')
    except (ValueError, TypeError):
        pass
    return ' '.join([p for p in parts if p])
