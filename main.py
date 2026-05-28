import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from flask import Flask, request, abort, send_file

TAIWAN_TZ = timezone(timedelta(hours=8))
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from database import Database
from excel_export import generate_excel
import json as _json
from calendar_query import query_schedule, query_schedule_date
from calendar_add import add_event
from calendar_delete import list_upcoming, delete_event, find_and_delete
from ai_chat import ask_ai
from salary import monthly_summary, list_prices, monthly_chart
from fuel import save_fuel, monthly_summary as fuel_monthly_summary, monthly_total as fuel_monthly_total, last_fill_performance, oil_change_warning, delete_last_fuel
from parking import save_parking, monthly_summary as parking_monthly_summary, monthly_total as parking_monthly_total, delete_last_parking
from ledger import save_entry as ledger_save_entry, monthly_summary as ledger_monthly_summary, delete_last_entry as ledger_delete_last, EXPENSE_CATEGORIES, INCOME_CATEGORIES

app = Flask(__name__)
configuration = Configuration(access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
db = Database()


@app.route('/ping')
def ping():
    return 'pong', 200


@app.route('/setup-richmenu')
def setup_richmenu():
    from rich_menu import setup
    return setup(), 200, {'Content-Type': 'text/plain; charset=utf-8'}


@app.route('/sync')
def sync_endpoint():
    import traceback
    try:
        from sync import sync_salary
        return sync_salary(), 200, {'Content-Type': 'text/plain; charset=utf-8'}
    except Exception as e:
        return (
            f'❌ 同步失敗\n{type(e).__name__}: {e}\n\n{traceback.format_exc()[:2000]}',
            200, {'Content-Type': 'text/plain; charset=utf-8'}
        )


@app.route('/webhook', methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    reply = process(user_id, text)

    if isinstance(reply, dict) and reply.get('type') == 'image':
        messages = []
        if reply.get('text'):
            messages.append(TextMessage(text=reply['text']))
        messages.append(ImageMessage(
            originalContentUrl=reply['image_url'],
            previewImageUrl=reply['image_url'],
        ))
    else:
        messages = [TextMessage(text=reply)]

    with ApiClient(configuration) as client:
        MessagingApi(client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=messages,
            )
        )


def process(user_id, text):
    text_lower = text.lower()

    # 全域指令（任何狀態都優先）
    if text in ('說明', '幫助', 'help', '?', '？'):
        return (
            '📚 葡萄助手\n\n'
            '📅 行程\n'
            '🔸 今天行程 / 明天行程\n'
            '🔸 5/20行程 → 查特定日期\n'
            '🔸 新增行程 明天10點 體能課\n'
            '🔸 刪除行程 → 列出可刪行程\n'
            '🔸 刪除行程 5/27 16:15 輔大自主課（直接刪）\n\n'
            '💰 薪資\n'
            '🔸 本月薪資 / 上月薪資（含淨薪）\n'
            '🔸 薪資圖表 → 視覺化\n'
            '🔸 價目表 → 查目前價格設定\n\n'
            '⛽ 加油\n'
            '🔸 記錄加油 → 開始新增\n'
            '🔸 本月加油 → 月度摘要 + 油耗\n\n'
            '📒 記帳\n'
            '🔸 記帳 → 開始記一筆（收入/支出）\n'
            '🔸 本月記帳 → 收支摘要\n'
            '🔸 刪除最後記帳 → 反悔\n\n'
            '🧰 器材記錄\n'
            '🔸 記錄器材 → 開始新增\n'
            '🔸 查看記錄 → 最近5筆\n'
            '🔸 查第3週 / 查5/14\n'
            '🔸 匯出Excel → 下載連結\n'
            '🔸 刪除最後一筆\n\n'
            '🤖 AI 助理\n'
            '🔸 直接說任何問題，AI 自動回答'
        )

    if text in ('本月薪資', '薪資', '這個月薪資', '查薪資', '看薪資', '本月收入'):
        return monthly_summary()

    if text in ('上月薪資', '上個月薪資', '查上月薪資'):
        now = datetime.now(TAIWAN_TZ)
        prev = now.replace(day=1) - timedelta(days=1)
        return monthly_summary(prev.year, prev.month)

    if text in ('價目表', '查價', '價格', '看價目表', '看價格', '查價目表'):
        return list_prices()

    if text in ('薪資圖表', '圖表', '本月圖表', '薪資視覺化', '視覺化'):
        try:
            from chart import generate_salary_chart_png
            token = uuid.uuid4().hex[:10]
            filepath = f'/tmp/chart_{token}.png'
            ok = generate_salary_chart_png(filepath)
            if not ok:
                return monthly_chart()
            db.save_token(token, filepath)
            url = f'{BASE_URL}/image/{token}.png'
            return {
                'type': 'image',
                'image_url': url,
                'text': monthly_summary(),
            }
        except Exception as ex:
            import traceback, sys
            tb_lines = traceback.format_exc().strip().split('\n')
            head = '\n'.join(tb_lines[:6])
            tail = '\n'.join(tb_lines[-4:])
            return f'⚠️ 圖表產生失敗 [v7 py={sys.version_info.major}.{sys.version_info.minor}]\n\n=頭=\n{head}\n\n=尾=\n{tail}\n\n（已退回文字版）\n\n' + monthly_chart()

    if text in ('本月加油', '加油記錄', '查加油', '看加油'):
        return fuel_monthly_summary()

    if text in ('刪除最後加油', '刪除加油', '刪除最後一筆加油'):
        try:
            desc = delete_last_fuel()
        except Exception as ex:
            return f'⚠️ 刪除失敗：{ex}'
        if not desc:
            return '加油記錄是空的，沒有可刪除的資料。'
        return f'🗑️ 已刪除最後一筆加油：\n{desc}'

    if text in ('本月停車', '停車記錄', '查停車', '本月停車費', '停車費'):
        return parking_monthly_summary()

    if text in ('記錄停車', '紀錄停車', '新增停車'):
        db.set_state(user_id, 'waiting_parking_amount', None, None)
        return '🅿️ 開始記錄停車費\n\n1️⃣ 金額？（例如：50）\n（或說「取消」中止）'

    if text in ('刪除最後停車', '刪除停車', '刪除最後一筆停車'):
        try:
            desc = delete_last_parking()
        except Exception as ex:
            return f'⚠️ 刪除失敗：{ex}'
        if not desc:
            return '停車費記錄是空的，沒有可刪除的資料。'
        return f'🗑️ 已刪除最後一筆停車費：\n{desc}'

    if text.startswith('停車'):
        rest = text[2:].strip()
        if rest:
            parts = rest.split(None, 1)
            try:
                amount = int(float(parts[0].replace('$', '').replace(',', '').replace('元', '')))
            except ValueError:
                return '⚠️ 停車費格式：停車 50 或 停車 50 仁愛親子館\n（第一個值要是金額）'
            location = parts[1].strip() if len(parts) > 1 else ''
            try:
                save_parking(amount, location)
            except Exception as ex:
                return f'⚠️ 寫入失敗：{ex}'
            loc_str = f'\n📍 {location}' if location else ''
            return f'✅ 停車費記錄完成！\n\n💰 ${amount:,}{loc_str}'

    if text in ('本月記帳', '記帳記錄', '查記帳', '本月收支', '收支'):
        return ledger_monthly_summary()

    if text in ('刪除最後記帳', '刪除記帳', '刪除最後一筆記帳'):
        try:
            desc = ledger_delete_last()
        except Exception as ex:
            return f'⚠️ 刪除失敗：{ex}'
        if not desc:
            return '記帳記錄是空的，沒有可刪除的資料。'
        return f'🗑️ 已刪除最後一筆記帳：\n{desc}'

    if text in ('記帳', '記一筆', '新增記帳', '記錄記帳', '紀錄記帳'):
        db.set_state(user_id, 'waiting_ledger_type', None, None)
        return '📒 開始記帳\n\n1️⃣ 這筆是收入還是支出？\n（說「收入」或「支出」，或說「取消」中止）'

    if text in ('同步', '同步薪資', '同步行事曆', 'sync'):
        from sync import sync_salary
        return sync_salary()

    if text in ('記錄加油', '紀錄加油', '加油', '新增加油'):
        db.set_state(user_id, 'waiting_fuel_mileage', None, None)
        return '⛽ 開始記錄加油\n\n1️⃣ 目前里程？（例如：56000）'

    if text in ('今天行程', '今天', '查行程', '行程', '今日行程'):
        return query_schedule(0)

    if text in ('明天行程', '明天', '明日行程'):
        return query_schedule(1)

    if text in ('後天行程', '後天'):
        return query_schedule(2)

    if text in ('刪除行程', '刪行程'):
        msg, refs = list_upcoming(7)
        if refs:
            db.set_delete_refs(user_id, _json.dumps(refs))
        return msg

    # 帶參數的刪除：刪除行程 5/27 16:15 輔大自主課
    if text.startswith('刪除行程') or text.startswith('刪行程'):
        query = re.sub(r'^(刪除行程|刪行程)\s*', '', text).strip()
        msg, refs = find_and_delete(query)
        if refs:
            db.set_delete_refs(user_id, _json.dumps(refs))
        return msg

    # 查特定日期行程：例如「查5/20行程」、「5/20行程」、「查行程5/20」
    # 排除掉新增/加/建立/刪除開頭，避免攔截到寫入指令
    date_pattern = re.search(r'(\d{1,2}/\d{1,2})', text)
    if (date_pattern and '行程' in text
            and not text.startswith(('新增', '加行程', '建立', '刪除', '刪'))):
        return query_schedule_date(date_pattern.group(1))

    if text.startswith('新增行程') or text.startswith('加行程') or text.startswith('建立行程'):
        raw = re.sub(r'^(新增行程|加行程|建立行程)\s*', '', text).strip()
        if not raw:
            return ('請輸入行程資訊，格式如下：\n\n'
                    '新增行程 明天10點 體能課\n'
                    '新增行程 5/20 下午3點 家長會 地點：學校')
        return add_event(raw)

    if (text in ('新增', '新增教具', '新增器材', 'start')
            or text.startswith(('記錄', '紀錄'))):
        db.set_state(user_id, 'waiting_week', None, None)
        return '📅 請問這是第幾週或哪個日期？\n（例如：第3週、5/14）'

    if text_lower in ('匯出excel', '匯出', '下載', '下載excel', 'excel'):
        return export_excel(user_id)

    if text in ('查看記錄', '我的記錄', '記錄列表'):
        return show_recent(user_id)

    if text.startswith('查') and len(text) > 1:
        keyword = text[1:].strip()
        if keyword in ('薪資', '本月薪資', '本月收入', '收入', '這個月薪資'):
            return monthly_summary()
        if keyword in ('上月薪資', '上個月薪資'):
            now = datetime.now(TAIWAN_TZ)
            prev = now.replace(day=1) - timedelta(days=1)
            return monthly_summary(prev.year, prev.month)
        if keyword in ('價目表', '價格'):
            return list_prices()
        if keyword in ('加油', '本月加油', '油費'):
            return fuel_monthly_summary()
        return search_records(user_id, keyword)

    if text in ('刪除最後一筆', '刪除'):
        deleted = db.delete_last(user_id)
        return f'🗑️ 已刪除：{deleted}' if deleted else '找不到可刪除的記錄。'

    if text in ('取消', 'cancel'):
        db.clear_state(user_id)
        return '已取消目前操作。可從選單重新開始，或說「說明」看所有指令。'

    # 狀態機
    state = db.get_state(user_id)

    if state == 'waiting_delete':
        refs_json = db.get_delete_refs(user_id)
        if text.isdigit() and refs_json:
            idx = int(text) - 1
            refs = _json.loads(refs_json)
            if 0 <= idx < len(refs):
                ref = refs[idx]
                cal_id, event_id, title = ref[0], ref[1], ref[2]
                event_date = ref[3] if len(ref) > 3 else None
                event_time = ref[4] if len(ref) > 4 else None
                ok = delete_event(cal_id, event_id)
                db.clear_state(user_id)
                salary_msg = ''
                if ok and event_date and event_time:
                    try:
                        from sheets_helper import delete_row_by_dict
                        ed_slash = event_date.replace('-', '/')
                        if delete_row_by_dict('薪資', {
                            '日期': ed_slash, '時間': event_time, '標題': title
                        }):
                            salary_msg = '\n💸 對應薪資記錄已移除'
                    except Exception:
                        pass
                return f'🗑️ 已刪除：{title}{salary_msg}' if ok else f'⚠️ 刪除失敗：{title}'
            db.clear_state(user_id)
            return '⚠️ 編號超出範圍，已取消。'
        db.clear_state(user_id)
        return '已取消刪除。'

    if state == 'waiting_fuel_mileage':
        try:
            mileage = int(float(text.replace(',', '').replace('km', '').strip()))
        except ValueError:
            return '⚠️ 里程要是數字，例如：56000\n（或說「取消」中止）'
        db.set_state(user_id, 'waiting_fuel_liters', _json.dumps({'mileage': mileage}), None)
        return f'✅ 里程：{mileage:,} km\n\n2️⃣ 加了幾公升？（例如：38）'

    if state == 'waiting_fuel_liters':
        try:
            liters = float(text.replace('L', '').replace('l', '').strip())
        except ValueError:
            return '⚠️ 公升要是數字，例如：38\n（或說「取消」中止）'
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        data['liters'] = liters
        db.set_state(user_id, 'waiting_fuel_amount', _json.dumps(data), None)
        return f'✅ 油量：{liters} L\n\n3️⃣ 總金額？（例如：1800）'

    if state == 'waiting_fuel_amount':
        try:
            amount = int(float(text.replace('$', '').replace(',', '').replace('元', '').strip()))
        except ValueError:
            return '⚠️ 金額要是數字，例如：1800\n（或說「取消」中止）'
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        data['amount'] = amount
        db.set_state(user_id, 'waiting_fuel_station', _json.dumps(data), None)
        return f'✅ 金額：${amount:,}\n\n4️⃣ 加油站？（直接說「無」可跳過）'

    if state == 'waiting_fuel_station':
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        station = '' if text in ('無', '跳過', '無') else text
        data['station'] = station
        db.set_state(user_id, 'waiting_fuel_oil', _json.dumps(data), None)
        return '✅ 加油站：' + (station if station else '（跳過）') + '\n\n5️⃣ 這次有換機油嗎？\n（說「有」或「無」）'

    if state == 'waiting_fuel_oil':
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        oil_change = text in ('有', 'Y', 'y', '是', '換了', '換', 'yes', 'YES')
        station = data.get('station', '')
        try:
            save_fuel(data['mileage'], data['liters'], data['amount'], station, oil_change=oil_change)
        except Exception as ex:
            db.clear_state(user_id)
            return f'⚠️ 寫入失敗：{ex}'
        db.clear_state(user_id)
        station_str = f'\n⛽ {station}' if station else ''
        oil_str = '\n🔧 已記錄：本次換機油' if oil_change else ''

        perf_str = ''
        try:
            perf = last_fill_performance(data['mileage'], data['liters'])
        except Exception:
            perf = None
        if perf:
            trip_km, km_per_l, avg, diff_pct = perf
            if avg > 0:
                if diff_pct >= 5:
                    judge = f'🟢 比平均高 {diff_pct:.1f}%'
                elif diff_pct <= -5:
                    judge = f'🔴 比平均低 {abs(diff_pct):.1f}%'
                else:
                    judge = f'⚪ 接近平均（{diff_pct:+.1f}%）'
                perf_str = (
                    f'\n\n━━━━━━━━━━\n'
                    f'📊 這次油耗表現\n'
                    f'🛣 跨距：{int(trip_km):,} km\n'
                    f'⛽ 油耗：{km_per_l:.1f} km/L\n'
                    f'📈 平均：{avg:.1f} km/L\n'
                    f'{judge}'
                )
            else:
                perf_str = (
                    f'\n\n━━━━━━━━━━\n'
                    f'📊 這次油耗\n'
                    f'🛣 跨距：{int(trip_km):,} km\n'
                    f'⛽ 油耗：{km_per_l:.1f} km/L'
                )

        oil_warn = ''
        try:
            warn = oil_change_warning(data['mileage'])
        except Exception:
            warn = None
        if warn:
            oil_warn = f'\n\n━━━━━━━━━━\n{warn}'

        return (
            f'✅ 加油記錄完成！\n\n'
            f'📏 里程：{data["mileage"]:,} km\n'
            f'🛢 油量：{data["liters"]} L\n'
            f'💰 金額：${data["amount"]:,}{station_str}{oil_str}'
            f'{perf_str}{oil_warn}\n\n'
            '說「本月加油」可看月度摘要'
        )

    if state == 'waiting_ledger_type':
        if '收入' in text:
            entry_type = '收入'
            cats = INCOME_CATEGORIES
        elif '支出' in text:
            entry_type = '支出'
            cats = EXPENSE_CATEGORIES
        else:
            return '⚠️ 請說「收入」或「支出」\n（或說「取消」中止）'
        db.set_state(user_id, 'waiting_ledger_category', _json.dumps({'type': entry_type}), None)
        cat_lines = '\n'.join(f'{i + 1}. {c}' for i, c in enumerate(cats))
        return f'✅ 類型：{entry_type}\n\n2️⃣ 選類別（回數字或直接打字）：\n{cat_lines}'

    if state == 'waiting_ledger_category':
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        cats = INCOME_CATEGORIES if data.get('type') == '收入' else EXPENSE_CATEGORIES
        if text.isdigit() and 1 <= int(text) <= len(cats):
            category = cats[int(text) - 1]
        else:
            category = text.strip()
        if not category:
            return '⚠️ 請選類別（回數字或直接打字）'
        data['category'] = category
        db.set_state(user_id, 'waiting_ledger_amount', _json.dumps(data), None)
        return f'✅ 類別：{category}\n\n3️⃣ 金額？（例如：120）'

    if state == 'waiting_ledger_amount':
        try:
            amount = int(float(text.replace('$', '').replace(',', '').replace('元', '').strip()))
        except ValueError:
            return '⚠️ 金額要是數字，例如：120\n（或說「取消」中止）'
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        data['amount'] = amount
        db.set_state(user_id, 'waiting_ledger_notes', _json.dumps(data), None)
        return f'✅ 金額：${amount:,}\n\n4️⃣ 備註？（直接說「無」可跳過）'

    if state == 'waiting_ledger_notes':
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        notes = '' if text in ('無', '跳過') else text
        try:
            ledger_save_entry(data['type'], data['category'], data['amount'], notes)
        except Exception as ex:
            db.clear_state(user_id)
            return f'⚠️ 寫入失敗：{ex}'
        db.clear_state(user_id)
        icon = '📥' if data['type'] == '收入' else '📤'
        notes_str = f'\n📝 {notes}' if notes else ''
        return (
            f'✅ 記帳完成！\n\n'
            f'{icon} {data["type"]}｜{data["category"]}\n'
            f'💰 ${data["amount"]:,}{notes_str}\n\n'
            '說「本月記帳」可看收支摘要'
        )

    if state == 'waiting_parking_amount':
        try:
            amount = int(float(text.replace('$', '').replace(',', '').replace('元', '').strip()))
        except ValueError:
            return '⚠️ 金額要是數字，例如：50\n（或說「取消」中止）'
        db.set_state(user_id, 'waiting_parking_location', _json.dumps({'amount': amount}), None)
        return f'✅ 金額：${amount:,}\n\n2️⃣ 地點？（直接說「無」可跳過）'

    if state == 'waiting_parking_location':
        data = _json.loads(db.get_temp_week(user_id) or '{}')
        location = '' if text in ('無', '跳過') else text.strip()
        try:
            save_parking(data['amount'], location)
        except Exception as ex:
            db.clear_state(user_id)
            return f'⚠️ 寫入失敗：{ex}'
        db.clear_state(user_id)
        loc_str = f'\n📍 {location}' if location else ''
        return (
            f'✅ 停車費記錄完成！\n\n'
            f'💰 ${data["amount"]:,}{loc_str}\n\n'
            '說「本月停車」可看月度摘要'
        )

    if state == 'waiting_week':
        db.set_state(user_id, 'waiting_tools', text, None)
        return f'✅ 日期：{text}\n\n🧰 這週用了哪些教具？\n（多個教具用頓號分隔，例如：呼拉圈、跳繩、平衡板）'

    if state == 'waiting_tools':
        week = db.get_temp_week(user_id)
        db.set_state(user_id, 'waiting_notes', week, text)
        return f'✅ 器材：{text}\n\n📝 活動目標或備註？\n（直接說「無」可跳過）'

    if state == 'waiting_notes':
        week, tools = db.get_temp_data(user_id)
        notes = '' if text == '無' else text
        db.save_record(user_id, week, tools, notes)
        db.clear_state(user_id)
        notes_display = notes if notes else '（無）'
        return (
            f'✅ 記錄完成！\n\n'
            f'📅 {week}\n'
            f'🧰 {tools}\n'
            f'📝 {notes_display}\n\n'
            '繼續說「記錄器材」可新增，\n說「匯出Excel」可下載。'
        )

    # 像在做動作但格式不對的明顯指令，給格式提示，不要丟給 AI 演戲
    if (text.startswith(('新增', '加', '建立', '幫我加', '幫我新增'))
            and not text.startswith('加油')):
        return ('⚠️ 指令格式不完整。\n\n'
                '✅ 新增行程：\n新增行程 5/27 16:15 輔大自主課\n\n'
                '✅ 記錄器材：記錄器材\n'
                '✅ 記錄加油：記錄加油')

    # 任何不認識的訊息交給 AI
    return ask_ai(text)


def export_excel(user_id):
    records = db.get_all_records(user_id)
    if not records:
        return '⚠️ 目前沒有記錄，請先說「記錄器材」新增。'
    token = uuid.uuid4().hex[:10]
    filepath = f'/tmp/export_{token}.xlsx'
    generate_excel(records, filepath)
    db.save_token(token, filepath)
    url = f'{BASE_URL}/download/{token}'
    return f'✅ Excel 已準備好！\n\n📥 點此下載（10分鐘內有效）：\n{url}'


def search_records(user_id, keyword):
    records = db.search_by_week(user_id, keyword)
    if not records:
        return f'🔍 找不到「{keyword}」的記錄。\n\n試試：查第3週、查5/14'
    lines = [f'🔍 「{keyword}」的查詢結果（{len(records)}筆）：\n']
    for r in records:
        notes = r['notes'] if r['notes'] else '無'
        lines.append(f'📅 {r["week"]}\n🧰 {r["tools"]}\n📝 {notes}\n')
    return '\n'.join(lines)


def show_recent(user_id):
    records = db.get_recent(user_id, 5)
    if not records:
        return '目前沒有記錄，說「記錄器材」開始新增吧！'
    lines = ['📋 最近5筆記錄：\n']
    for r in records:
        notes = r['notes'] if r['notes'] else '無'
        lines.append(f'📅 {r["week"]}\n🧰 {r["tools"]}\n📝 {notes}\n')
    return '\n'.join(lines)


@app.route('/image/<token>.png')
def image(token):
    from datetime import datetime, timedelta, timezone
    filepath, created_at = db.get_token(token)
    if not filepath or not os.path.exists(filepath):
        return '圖片已過期', 404
    age = datetime.now(timezone.utc) - created_at
    if age > timedelta(minutes=30):
        return '圖片已過期', 410
    return send_file(filepath, mimetype='image/png')


@app.route('/download/<token>')
def download(token):
    from datetime import datetime, timedelta, timezone
    filepath, created_at = db.get_token(token)
    if not filepath:
        return '連結不存在或已失效。', 404
    if not os.path.exists(filepath):
        return '檔案已過期，請重新匯出。', 404
    age = datetime.now(timezone.utc) - created_at
    if age > timedelta(minutes=10):
        return '連結已超過10分鐘，請重新說「匯出Excel」。', 410
    return send_file(
        filepath,
        as_attachment=True,
        download_name='器材記錄.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
