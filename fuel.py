from datetime import datetime, timezone, timedelta
from sheets_helper import read_all, append_row

TAIWAN_TZ = timezone(timedelta(hours=8))
FUEL_SHEET = '加油'

OIL_CHANGE_INTERVAL_KM = 5000
OIL_CHANGE_WARN_KM = 4500


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def save_fuel(mileage, liters, amount, station='', notes='', oil_change=False):
    append_row(FUEL_SHEET, {
        '日期': datetime.now(TAIWAN_TZ).strftime('%Y/%m/%d'),
        '里程': mileage,
        '公升': liters,
        '金額': amount,
        '加油站': station,
        '備註': notes,
        '保養': '機油' if oil_change else '',
    })


def last_oil_change_mileage():
    """找最近一筆「保養」欄位包含『機油』的紀錄，回傳其里程；找不到回傳 None。"""
    rows = read_all(FUEL_SHEET)
    parsed = []
    for r in rows:
        if '機油' not in (r.get('保養') or ''):
            continue
        d = _parse_date(r.get('日期'))
        try:
            m = float(str(r.get('里程', '0')).strip() or 0)
        except (ValueError, TypeError):
            continue
        if d:
            parsed.append((d, m))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])
    return parsed[-1][1]


def oil_change_warning(current_mileage):
    """檢查是否該換機油，回傳警告字串或 None。"""
    try:
        cur_m = float(current_mileage)
    except (ValueError, TypeError):
        return None
    last_m = last_oil_change_mileage()
    if last_m is None:
        return None
    diff = cur_m - last_m
    if diff < OIL_CHANGE_WARN_KM:
        return None
    over = diff - OIL_CHANGE_INTERVAL_KM
    if over >= 0:
        return f'⚠️ 機油該換了！距離上次換機油已 {int(diff):,} km（建議 {OIL_CHANGE_INTERVAL_KM:,} km，超過 {int(over):,} km）'
    remain = OIL_CHANGE_INTERVAL_KM - int(diff)
    return f'🔔 機油提醒：距離上次換機油 {int(diff):,} km，再 {remain:,} km 就到 {OIL_CHANGE_INTERVAL_KM:,} km 週期'


def last_fill_performance(current_mileage, current_liters):
    """這次加油的油耗表現。

    回傳 (trip_km, km_per_l, avg_km_per_l, diff_pct) 或 None（首次加油無前次資料）。
    km_per_l 用「上次→這次跨距 ÷ 這次加的油」（fill-to-full 標準算法）。
    """
    try:
        cur_m = float(current_mileage)
        cur_l = float(current_liters)
    except (ValueError, TypeError):
        return None
    if cur_l <= 0:
        return None

    rows = read_all(FUEL_SHEET)
    parsed = []
    for r in rows:
        d = _parse_date(r.get('日期'))
        if not d:
            continue
        try:
            m = float(str(r.get('里程', '0')).strip() or 0)
            l = float(str(r.get('公升', '0')).strip() or 0)
        except (ValueError, TypeError):
            continue
        parsed.append((d, m, l))
    if not parsed:
        return None
    parsed.sort(key=lambda x: x[0])

    # 這次加油假設是最新一筆（剛剛 append 進去）
    # 找前一筆（里程小於這次的最後一筆）
    prev = None
    for d, m, l in parsed:
        if m < cur_m:
            prev = (d, m, l)
    if not prev:
        return None

    trip_km = cur_m - prev[1]
    if trip_km <= 0 or trip_km > 2000:
        return None
    km_per_l = trip_km / cur_l

    # 個人平均：用所有已記錄的相鄰差（不含這次，因為這次還沒算進 parsed 末尾的「下一筆」）
    total_km = 0.0
    total_l = 0.0
    for i in range(1, len(parsed)):
        diff = parsed[i][1] - parsed[i - 1][1]
        used_l = parsed[i][2]
        if 0 < diff < 2000 and used_l > 0:
            total_km += diff
            total_l += used_l
    avg = (total_km / total_l) if total_l > 0 else 0
    diff_pct = ((km_per_l - avg) / avg * 100) if avg > 0 else 0
    return trip_km, km_per_l, avg, diff_pct


def monthly_total(year=None, month=None):
    """回傳 (本月總金額, 本月總公升, 加油次數)"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month
    rows = read_all(FUEL_SHEET)
    total_amt = 0
    total_l = 0.0
    count = 0
    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            total_amt += int(float(str(row.get('金額', '0')).strip() or 0))
            total_l += float(str(row.get('公升', '0')).strip() or 0)
            count += 1
        except (ValueError, TypeError):
            continue
    return total_amt, total_l, count


def monthly_summary(year=None, month=None):
    """本月加油摘要 + 油耗。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    all_rows = read_all(FUEL_SHEET)
    # 按日期排序所有資料以正確計算里程差
    parsed = []
    for r in all_rows:
        d = _parse_date(r.get('日期'))
        if not d:
            continue
        try:
            m = float(str(r.get('里程', '0')).strip() or 0)
            l = float(str(r.get('公升', '0')).strip() or 0)
            a = int(float(str(r.get('金額', '0')).strip() or 0))
        except (ValueError, TypeError):
            continue
        parsed.append((d, m, l, a, r.get('加油站', '')))
    parsed.sort(key=lambda x: x[0])

    month_records = [(d, m, l, a, s) for d, m, l, a, s in parsed
                     if d.year == year and d.month == month]
    if not month_records:
        return f'⛽ {year}/{month:02d} 還沒有加油記錄'

    lines = [f'⛽ {year}/{month:02d} 加油摘要', '']
    total_amt = 0
    total_l = 0.0
    for i, (d, m, l, a, s) in enumerate(month_records):
        idx_all = parsed.index((d, m, l, a, s))
        consumption = ''
        if idx_all > 0:
            prev = parsed[idx_all - 1]
            diff = m - prev[1]
            if l > 0 and 0 < diff < 2000:
                consumption = f'  ({diff/l:.1f} km/L)'
        station_str = f' @{s}' if s else ''
        lines.append(f'{d.strftime("%m/%d")} {int(m):,}km {l:.1f}L ${a:,}{station_str}{consumption}')
        total_amt += a
        total_l += l
    lines.append('')
    lines.append('━━━━━━━━━━')
    lines.append(f'⛽ 共 {len(month_records)} 次｜{total_l:.1f}L｜${total_amt:,}')
    if len(month_records) >= 2:
        first_m = month_records[0][1]
        last_m = month_records[-1][1]
        avg_consumption = (last_m - first_m) / total_l if total_l > 0 else 0
        if 0 < avg_consumption < 100:
            lines.append(f'📏 平均油耗：{avg_consumption:.1f} km/L')
    return '\n'.join(lines)
