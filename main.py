import os
import re
import uuid
from flask import Flask, request, abort, send_file
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi,
    ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from database import Database
from excel_export import generate_excel
from calendar_query import query_schedule
from calendar_add import add_event
from ai_chat import ask_ai

app = Flask(__name__)
configuration = Configuration(access_token=os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
db = Database()


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
    with ApiClient(configuration) as client:
        MessagingApi(client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


def process(user_id, text):
    text_lower = text.lower()

    # 全域指令（任何狀態都優先）
    if text in ('說明', '幫助', 'help', '?', '？'):
        return (
            '📚 教具記錄小幫手\n\n'
            '📅 行程\n'
            '🔸 今天行程 / 明天行程\n'
            '🔸 新增行程 明天10點 體能課\n\n'
            '🧰 教具記錄\n'
            '🔸 記錄教具 → 開始新增\n'
            '🔸 查看記錄 → 最近5筆\n'
            '🔸 查第3週 / 查5/14\n'
            '🔸 匯出Excel → 下載連結\n'
            '🔸 刪除最後一筆\n\n'
            '🤖 AI 助理\n'
            '🔸 直接說任何問題，AI 自動回答'
        )

    if text in ('今天行程', '今天', '查行程', '行程', '今日行程'):
        return query_schedule(0)

    if text in ('明天行程', '明天', '明日行程'):
        return query_schedule(1)

    if text in ('後天行程', '後天'):
        return query_schedule(2)

    if text.startswith('新增行程') or text.startswith('加行程') or text.startswith('建立行程'):
        raw = re.sub(r'^(新增行程|加行程|建立行程)\s*', '', text).strip()
        if not raw:
            return ('請輸入行程資訊，格式如下：\n\n'
                    '新增行程 明天10點 體能課\n'
                    '新增行程 5/20 下午3點 家長會 地點：學校')
        return add_event(raw)

    if text in ('記錄教具', '紀錄教具', '新增', '新增教具', '記錄', '紀錄', 'start'):
        db.set_state(user_id, 'waiting_week', None, None)
        return '📅 請問這是第幾週或哪個日期？\n（例如：第3週、5/14）'

    if text_lower in ('匯出excel', '匯出', '下載', '下載excel', 'excel'):
        return export_excel(user_id)

    if text in ('查看記錄', '我的記錄', '記錄列表'):
        return show_recent(user_id)

    if text.startswith('查') and len(text) > 1:
        keyword = text[1:].strip()
        return search_records(user_id, keyword)

    if text in ('刪除最後一筆', '刪除'):
        deleted = db.delete_last(user_id)
        return f'🗑️ 已刪除：{deleted}' if deleted else '找不到可刪除的記錄。'

    if text in ('取消', 'cancel'):
        db.clear_state(user_id)
        return '已取消目前操作。說「記錄教具」可重新開始。'

    # 狀態機
    state = db.get_state(user_id)

    if state == 'waiting_week':
        db.set_state(user_id, 'waiting_tools', text, None)
        return f'✅ 日期：{text}\n\n🧰 這週用了哪些教具？\n（多個教具用頓號分隔，例如：呼拉圈、跳繩、平衡板）'

    if state == 'waiting_tools':
        week = db.get_temp_week(user_id)
        db.set_state(user_id, 'waiting_notes', week, text)
        return f'✅ 教具：{text}\n\n📝 活動目標或備註？\n（直接說「無」可跳過）'

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
            '繼續說「記錄教具」可新增，\n說「匯出Excel」可下載。'
        )

    # 任何不認識的訊息交給 AI
    return ask_ai(text)


def export_excel(user_id):
    records = db.get_all_records(user_id)
    if not records:
        return '⚠️ 目前沒有記錄，請先說「記錄教具」新增。'
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
        return '目前沒有記錄，說「記錄教具」開始新增吧！'
    lines = ['📋 最近5筆記錄：\n']
    for r in records:
        notes = r['notes'] if r['notes'] else '無'
        lines.append(f'📅 {r["week"]}\n🧰 {r["tools"]}\n📝 {notes}\n')
    return '\n'.join(lines)


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
        download_name='教具記錄.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
