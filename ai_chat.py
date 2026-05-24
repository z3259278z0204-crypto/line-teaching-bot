import json
import os
import urllib.request

SYSTEM_PROMPT = (
    '你是一個幼兒體能教師的智慧助理，名字叫做「葡萄助手」。'
    '用繁體中文回答，語氣親切、簡潔。'
    '專長是幼兒體能教學、教具建議、課程設計。'
    '\n\n⚠️ 重要規則：'
    '你「無法」執行任何實際動作（新增/刪除/查詢日曆、薪資、記錄）。'
    '如果使用者像是要你做這些操作（例如「新增 X」「幫我加 X」「查 X 薪資」），'
    '請明確告訴他正確指令格式，例如：'
    '「我沒辦法直接幫你新增，請打『新增行程 5/27 16:15 輔大自主課』這樣的格式」。'
    '絕對不要假裝你已經做了什麼操作。'
)


def ask_ai(question):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return '⚠️ AI 功能尚未啟用。'

    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-2.5-flash:generateContent?key={api_key}'
    )
    body = json.dumps({
        'contents': [
            {'role': 'user', 'parts': [{'text': f'{SYSTEM_PROMPT}\n\n問題：{question}'}]}
        ],
        'generationConfig': {'maxOutputTokens': 400}
    }).encode()

    req = urllib.request.Request(
        url, data=body,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            return result['candidates'][0]['content']['parts'][0]['text'].strip()
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        return f'⚠️ AI 錯誤({e.code})：{err_body[:200]}'
    except Exception as e:
        return f'⚠️ AI 連線失敗：{type(e).__name__}: {str(e)[:100]}'
