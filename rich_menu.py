import json
import os
import urllib.request
import urllib.parse

LINE_API = 'https://api.line.me/v2/bot'
LINE_DATA_API = 'https://api-data.line.me/v2/bot'
IMAGE_PATH = os.path.join(os.path.dirname(__file__), 'assets', 'richmenu.png')

WIDTH, HEIGHT = 2500, 1686
COLS, ROWS = 3, 3
COL_W, ROW_H = WIDTH // COLS, HEIGHT // ROWS

# 對應 generate_richmenu_image.py 的 CELLS 順序
ACTIONS = [
    '今天行程',
    '新增行程 ',
    '記錄加油',
    '記錄停車',
    '本月薪資',
    '薪資圖表',
    '記錄器材',
    '記帳',
    '說明',
]


def _headers():
    return {
        'Authorization': f'Bearer {os.environ["LINE_CHANNEL_ACCESS_TOKEN"]}',
    }


def _build_areas():
    areas = []
    for i, text in enumerate(ACTIONS):
        col, row = i % COLS, i // COLS
        x = col * COL_W
        y = row * ROW_H
        w = (WIDTH - x) if col == COLS - 1 else COL_W
        h = (HEIGHT - y) if row == ROWS - 1 else ROW_H
        areas.append({
            'bounds': {'x': x, 'y': y, 'width': w, 'height': h},
            'action': {'type': 'message', 'text': text},
        })
    return areas


def _create_menu():
    body = json.dumps({
        'size': {'width': WIDTH, 'height': HEIGHT},
        'selected': True,
        'name': 'main_menu_v2',
        'chatBarText': '選單',
        'areas': _build_areas(),
    }).encode()
    h = _headers()
    h['Content-Type'] = 'application/json'
    req = urllib.request.Request(f'{LINE_API}/richmenu', data=body, headers=h, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['richMenuId']


def _upload_image(menu_id):
    with open(IMAGE_PATH, 'rb') as f:
        data = f.read()
    h = _headers()
    h['Content-Type'] = 'image/png'
    req = urllib.request.Request(
        f'{LINE_DATA_API}/richmenu/{menu_id}/content',
        data=data, headers=h, method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def _set_default(menu_id):
    req = urllib.request.Request(
        f'{LINE_API}/user/all/richmenu/{menu_id}',
        headers=_headers(), method='POST'
    )
    with urllib.request.urlopen(req) as resp:
        resp.read()


def _list_existing():
    req = urllib.request.Request(f'{LINE_API}/richmenu/list', headers=_headers())
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read()).get('richmenus', [])


def _delete(menu_id):
    req = urllib.request.Request(
        f'{LINE_API}/richmenu/{menu_id}', headers=_headers(), method='DELETE'
    )
    try:
        with urllib.request.urlopen(req) as resp:
            resp.read()
    except Exception:
        pass


def setup():
    """全套設定：清掉舊的、建新的、上傳圖、設為預設。"""
    if not os.path.exists(IMAGE_PATH):
        return f'❌ 找不到圖片：{IMAGE_PATH}'

    try:
        for m in _list_existing():
            _delete(m['richMenuId'])
        menu_id = _create_menu()
        _upload_image(menu_id)
        _set_default(menu_id)
        return f'✅ Rich Menu 設定完成\nID: {menu_id}'
    except urllib.error.HTTPError as e:
        return f'❌ LINE API 錯誤 ({e.code}): {e.read().decode("utf-8", errors="ignore")[:300]}'
    except Exception as e:
        return f'❌ 失敗：{type(e).__name__}: {e}'
