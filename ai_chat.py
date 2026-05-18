import json
import os
import urllib.request

SYSTEM_PROMPT = (
    '你是一個幼兒體能教師的智慧助理，名字叫做「葡萄助手」。'
    '用繁體中文回答，語氣親切、簡潔。'
    '專長是幼兒體能教學、教具建議、課程設計。'
)


def ask_ai(question):
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return '⚠️ AI 功能尚未啟用。'

    url = (
        'https://generativelanguage.googleapis.com/v1beta/models/'
        f'gemini-1.5-flash:generateContent?key={api_key}'
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
    except Exception as e:
        return f'⚠️ AI 暫時無法回應，請稍後再試。'
