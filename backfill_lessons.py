"""一次性回填「薪資」分頁的「堂數」欄。

讀 Calendar 過去 90 天事件，依 (日期, 時間, 標題) 對應 Sheet 列，
重新計算正確堂數寫回。已正確的列不動，找不到對應的列也不動。

執行方式：
- 本機：python backfill_lessons.py
- LINE 指令：「回填堂數」（main.py 已綁定）
"""
from sync import _fetch_events, _event_key, _lessons_from_event, SALARY_SHEET
from sheets_helper import read_all, update_cells, _read_headers


def backfill_lessons():
    try:
        events = _fetch_events()
    except Exception as ex:
        return f'⚠️ 取得行事曆失敗：{ex}'

    headers = _read_headers(SALARY_SHEET)
    if '堂數' not in headers:
        return (
            '⚠️ 「薪資」分頁找不到「堂數」欄。\n\n'
            '請先到 Google Sheet 的「薪資」分頁，在標頭列加一欄叫「堂數」（建議放在「單價」後面），再回來執行一次。'
        )

    event_lessons = {}
    for e in events:
        key = _event_key(e)
        if not key:
            continue
        event_lessons[key] = _lessons_from_event(e)

    rows = read_all(SALARY_SHEET)
    matched = 0
    needs_update = 0
    skipped = 0
    updates = []
    for i, r in enumerate(rows, start=2):
        d = (r.get('日期') or '').strip()
        t = (r.get('時間') or '').strip()
        title = (r.get('標題') or '').strip()
        if not (d and t and title):
            continue
        key = (d, t, title)
        if key not in event_lessons:
            skipped += 1
            continue
        matched += 1
        new_lessons = event_lessons[key]
        cur_raw = str(r.get('堂數', '') or '').strip()
        try:
            cur = int(float(cur_raw)) if cur_raw else None
        except (ValueError, TypeError):
            cur = None
        if cur == new_lessons:
            continue
        updates.append((i, '堂數', new_lessons))
        needs_update += 1

    written = update_cells(SALARY_SHEET, updates) if updates else 0
    return (
        '🔄 堂數回填完成\n\n'
        f'✏️ 更新：{written} 列\n'
        f'✅ 已正確（不動）：{matched - needs_update} 列\n'
        f'⏭ Calendar 查無對應：{skipped} 列'
    )


if __name__ == '__main__':
    print(backfill_lessons())
