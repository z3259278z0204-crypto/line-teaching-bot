"""診斷某個關鍵字為何沒同步進薪資。
LINE 指令『查 X』『查關鍵字 X』『debug X』會呼叫 debug_keyword(X)。
"""
from sync import _fetch_events, _event_key, _load_price_table, _match_price, SALARY_SHEET
from sheets_helper import read_all


def debug_keyword(needle):
    needle = (needle or '').strip()
    if not needle:
        return '⚠️ 沒給關鍵字。試試「查 00老師」。'

    lines = [f'🔎 診斷關鍵字：「{needle}」', '']

    # ===== Step 1：價目表這邊有沒有、單價能不能 parse =====
    try:
        rows = read_all('價目表')
    except Exception as ex:
        return f'⚠️ 讀價目表失敗：{ex}'

    matched_price_rows = []
    for i, r in enumerate(rows, start=2):
        kw = (r.get('關鍵字') or '')
        if needle in kw or kw.strip() == needle:
            matched_price_rows.append((i, kw, r.get('單價', '')))

    lines.append('📋 價目表：')
    if not matched_price_rows:
        lines.append(f'  ❌ 沒有任何列的「關鍵字」包含「{needle}」')
        # 找近似的（去空白後比對）
        near = [(i, r.get('關鍵字','')) for i, r in enumerate(rows, start=2)
                if needle.strip() in (r.get('關鍵字','') or '').strip()
                or (r.get('關鍵字','') or '').strip() in needle.strip()]
        if near:
            lines.append('  🔍 近似（去空白比對）：')
            for i, kw in near[:5]:
                lines.append(f'    列{i}: {repr(kw)}')
    else:
        for i, kw, price in matched_price_rows:
            ok = '✅' if str(price).strip().isdigit() else '❌單價不是整數'
            lines.append(f'  列{i}: 關鍵字={repr(kw)} 單價={repr(str(price))} {ok}')

    # 也驗證 sync 用的 _load_price_table 會不會吃進這個 keyword
    try:
        price_table = _load_price_table()
        in_table = [(k, p) for k, p in price_table if needle in k or k == needle]
        if in_table:
            lines.append(f'  ✅ sync 載入的價目表內：{in_table}')
        else:
            lines.append(f'  ❌ sync 載入的價目表查無此關鍵字（可能單價非整數被略過）')
    except Exception as ex:
        lines.append(f'  ⚠️ 載入價目表失敗：{ex}')

    # ===== Step 2：Calendar 過去 90 天裡標題含此字串的事件 =====
    lines.append('')
    lines.append('📅 Calendar 事件（過去90天～未來90天，標題含此字）：')
    try:
        events = _fetch_events()
    except Exception as ex:
        lines.append(f'  ⚠️ 取得行事曆失敗：{ex}')
        events = []

    hit_events = []
    for e in events:
        title = (e.get('summary') or '')
        if needle in title:
            hit_events.append(e)

    if not hit_events:
        lines.append(f'  ❌ 90 天區間內沒有任何事件標題含「{needle}」')
    else:
        try:
            price_table = _load_price_table()
        except Exception:
            price_table = []
        for e in hit_events[:10]:
            title = e.get('summary') or ''
            key = _event_key(e)
            if key is None:
                reason = '⏭ 整天事件（無 dateTime）→ 同步會跳過'
            else:
                d, t, _ = key
                price, kw = _match_price(title, price_table)
                if price is None:
                    reason = '❌ 價目表查無對應關鍵字'
                else:
                    reason = f'✅ 已對應「{kw}」單價 {price}'
                reason = f'{d} {t}  {reason}'
            lines.append(f'  {repr(title)}（len={len(title)}）')
            lines.append(f'    {reason}')
        if len(hit_events) > 10:
            lines.append(f'  …另有 {len(hit_events)-10} 筆')

    # ===== Step 3：薪資 Sheet 裡有沒有對應列 =====
    lines.append('')
    lines.append('💰 薪資分頁（90 天區間內、標題含此字）：')
    try:
        salary_rows = read_all(SALARY_SHEET)
        hit_salary = [r for r in salary_rows if needle in (r.get('標題') or '')]
        if not hit_salary:
            lines.append(f'  ❌ 薪資分頁找不到含「{needle}」的列')
        else:
            for r in hit_salary[:5]:
                lines.append(f'  {r.get("日期")} {r.get("時間")} {r.get("標題")} ${r.get("單價")}')
            if len(hit_salary) > 5:
                lines.append(f'  …另有 {len(hit_salary)-5} 列')
    except Exception as ex:
        lines.append(f'  ⚠️ 讀薪資失敗：{ex}')

    return '\n'.join(lines)
