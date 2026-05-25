import json
import os
import urllib.request
import urllib.parse

SHEETS_BASE = 'https://sheets.googleapis.com/v4/spreadsheets'


def _spreadsheet_id():
    return os.environ['SPREADSHEET_ID']


def _get_access_token():
    data = urllib.parse.urlencode({
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
        'refresh_token': os.environ['GOOGLE_REFRESH_TOKEN'],
        'grant_type': 'refresh_token',
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data, method='POST')
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())['access_token']


def _request(url, method='GET', body=None):
    token = _get_access_token()
    headers = {'Authorization': f'Bearer {token}'}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def read_all(sheet_name):
    """讀某分頁所有資料列，回傳 [{欄位名: 值, ...}, ...]"""
    sid = _spreadsheet_id()
    rng = urllib.parse.quote(sheet_name)
    data = _request(f'{SHEETS_BASE}/{sid}/values/{rng}')
    values = data.get('values', [])
    if not values:
        return []
    headers = values[0]
    rows = []
    for row in values[1:]:
        padded = row + [''] * (len(headers) - len(row))
        rows.append(dict(zip(headers, padded)))
    return rows


def _read_headers(sheet_name):
    sid = _spreadsheet_id()
    rng = urllib.parse.quote(f'{sheet_name}!1:1')
    data = _request(f'{SHEETS_BASE}/{sid}/values/{rng}')
    return data.get('values', [[]])[0]


def append_row(sheet_name, row_dict):
    """依分頁標頭順序追加一列"""
    sid = _spreadsheet_id()
    headers = _read_headers(sheet_name)
    row = [str(row_dict.get(h, '')) for h in headers]
    rng = urllib.parse.quote(sheet_name)
    url = f'{SHEETS_BASE}/{sid}/values/{rng}:append?valueInputOption=USER_ENTERED'
    return _request(url, method='POST', body={'values': [row]})


def append_rows(sheet_name, list_of_dicts):
    """批次追加多筆。一次 API 完成所有列。"""
    if not list_of_dicts:
        return None
    sid = _spreadsheet_id()
    headers = _read_headers(sheet_name)
    values = [[str(d.get(h, '')) for h in headers] for d in list_of_dicts]
    rng = urllib.parse.quote(sheet_name)
    url = f'{SHEETS_BASE}/{sid}/values/{rng}:append?valueInputOption=USER_ENTERED'
    return _request(url, method='POST', body={'values': values})


def delete_rows_by_indices(sheet_name, row_indices):
    """一次刪除多列（傳入的是 1-based row 編號清單，含標頭那列為第 1 列）。
    傳入時不需排序，內部會從大到小排避免索引偏移。"""
    if not row_indices:
        return 0
    sid = _spreadsheet_id()
    sheet_id = _get_sheet_id(sheet_name)
    sorted_rows = sorted(set(row_indices), reverse=True)
    requests = [{
        'deleteDimension': {
            'range': {
                'sheetId': sheet_id,
                'dimension': 'ROWS',
                'startIndex': r - 1,
                'endIndex': r,
            }
        }
    } for r in sorted_rows]
    _request(f'{SHEETS_BASE}/{sid}:batchUpdate', method='POST', body={'requests': requests})
    return len(sorted_rows)


def find_price(title):
    """依價目表「關鍵字」做包含比對，回傳 (單價, 匹配的關鍵字) 或 (None, None)"""
    rows = read_all('價目表')
    for row in rows:
        keyword = (row.get('關鍵字') or '').strip()
        if keyword and keyword in title:
            try:
                price = int(str(row.get('單價', '')).strip())
                return price, keyword
            except (ValueError, TypeError):
                return None, keyword
    return None, None


def delete_row_by_match(sheet_name, match_col, match_value):
    """刪除指定欄位 = 指定值的第一筆資料列。回傳 True/False"""
    sid = _spreadsheet_id()
    rng = urllib.parse.quote(sheet_name)
    data = _request(f'{SHEETS_BASE}/{sid}/values/{rng}')
    values = data.get('values', [])
    if not values:
        return False
    headers = values[0]
    if match_col not in headers:
        return False
    col_idx = headers.index(match_col)

    target_row = None
    for i, row in enumerate(values[1:], start=2):
        if len(row) > col_idx and row[col_idx].strip() == str(match_value).strip():
            target_row = i
            break
    if not target_row:
        return False

    sheet_id = _get_sheet_id(sheet_name)
    body = {
        'requests': [{
            'deleteDimension': {
                'range': {
                    'sheetId': sheet_id,
                    'dimension': 'ROWS',
                    'startIndex': target_row - 1,
                    'endIndex': target_row
                }
            }
        }]
    }
    _request(f'{SHEETS_BASE}/{sid}:batchUpdate', method='POST', body=body)
    return True


def delete_row_by_dict(sheet_name, criteria):
    """以多欄條件刪除第一筆全部符合的資料列。criteria = {欄位名: 值}"""
    sid = _spreadsheet_id()
    rng = urllib.parse.quote(sheet_name)
    data = _request(f'{SHEETS_BASE}/{sid}/values/{rng}')
    values = data.get('values', [])
    if not values:
        return False
    headers = values[0]
    col_idx = {}
    for col_name in criteria:
        if col_name not in headers:
            return False
        col_idx[col_name] = headers.index(col_name)

    target_row = None
    for i, row in enumerate(values[1:], start=2):
        ok = True
        for col_name, expected in criteria.items():
            idx = col_idx[col_name]
            actual = row[idx].strip() if len(row) > idx else ''
            if actual != str(expected).strip():
                ok = False
                break
        if ok:
            target_row = i
            break
    if not target_row:
        return False

    sheet_id = _get_sheet_id(sheet_name)
    body = {
        'requests': [{
            'deleteDimension': {
                'range': {
                    'sheetId': sheet_id,
                    'dimension': 'ROWS',
                    'startIndex': target_row - 1,
                    'endIndex': target_row
                }
            }
        }]
    }
    _request(f'{SHEETS_BASE}/{sid}:batchUpdate', method='POST', body=body)
    return True


def _get_sheet_id(sheet_name):
    sid = _spreadsheet_id()
    data = _request(f'{SHEETS_BASE}/{sid}?fields=sheets.properties')
    for s in data.get('sheets', []):
        props = s.get('properties', {})
        if props.get('title') == sheet_name:
            return props.get('sheetId')
    raise ValueError(f'找不到分頁：{sheet_name}')
