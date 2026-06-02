import os
import sys
from datetime import datetime, timezone, timedelta
from collections import defaultdict

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

sys.setrecursionlimit(5000)

from sheets_helper import read_all
from fuel import monthly_total as fuel_monthly_total
from parking import monthly_total as parking_monthly_total
from ledger import monthly_total as ledger_monthly_total

TAIWAN_TZ = timezone(timedelta(hours=8))

FONT_PATH = os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSansTC-Regular.otf')
_FONT_PROP = None


def _font():
    global _FONT_PROP
    if _FONT_PROP is None and os.path.exists(FONT_PATH):
        font_manager.fontManager.addfont(FONT_PATH)
        _FONT_PROP = font_manager.FontProperties(fname=FONT_PATH)
        plt.rcParams['font.family'] = _FONT_PROP.get_name()
        plt.rcParams['axes.unicode_minus'] = False
        plt.rcParams['text.parse_math'] = False
    return _FONT_PROP


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _lessons_of(row):
    raw = str(row.get('堂數', '') or '').strip()
    if not raw:
        return 1
    try:
        n = int(float(raw))
    except (ValueError, TypeError):
        return 1
    return max(1, n)


def generate_salary_chart_png(filepath, year=None, month=None):
    """產生薪資圓餅圖 + 長條圖，存到 filepath。回傳 True 表示成功、False 表示無資料。"""
    now = datetime.now(TAIWAN_TZ)
    year = year or now.year
    month = month or now.month

    _font()

    rows = read_all('薪資')
    by_title = defaultdict(int)
    total = 0
    count = 0
    for row in rows:
        d = _parse_date(row.get('日期'))
        if not d or d.year != year or d.month != month:
            continue
        try:
            price = int(str(row.get('單價', '')).strip())
        except (ValueError, TypeError):
            continue
        lessons = _lessons_of(row)
        amount = price * lessons
        title = (row.get('標題') or '').strip() or '未分類'
        by_title[title] += amount
        total += amount
        count += lessons

    if count == 0:
        return False

    try:
        fuel_amt, _, fuel_n = fuel_monthly_total(year, month)
    except Exception:
        fuel_amt, fuel_n = 0, 0
    try:
        park_amt, park_n = parking_monthly_total(year, month)
    except Exception:
        park_amt, park_n = 0, 0
    try:
        ledger_exp, _ = ledger_monthly_total(year, month)
    except Exception:
        ledger_exp = 0
    net = total - fuel_amt - park_amt - ledger_exp

    sorted_items = sorted(by_title.items(), key=lambda x: -x[1])
    labels = [t for t, _ in sorted_items]
    values = [v for _, v in sorted_items]

    fig = plt.figure(figsize=(10, 13))
    fig.patch.set_facecolor('#FAFAFA')
    ax1 = fig.add_axes([0.03, 0.54, 0.54, 0.42])   # 圓餅圖（放大、佔滿左上）
    ax2 = fig.add_axes([0.22, 0.06, 0.73, 0.38])   # 收支長條（左留白給課程名）

    cmap = matplotlib.colormaps['tab20']
    colors = [cmap(i % 20) for i in range(len(labels))]

    # === 上：圓餅圖（課程名全移到右側圖例，餅上只留大區塊百分比）===
    SMALL_PCT = 5.0
    def _autopct(p):
        return f'{p:.0f}%' if p >= SMALL_PCT else ''

    wedges, texts, autotexts = ax1.pie(
        values,
        colors=colors,
        autopct=_autopct,
        startangle=90,
        wedgeprops={'edgecolor': 'white', 'linewidth': 2},
        pctdistance=0.78,
    )
    for t in autotexts:
        t.set_color('white')
        t.set_fontweight('bold')
        t.set_fontsize(11)
    ax1.set_title(f'{year}/{month:02d} 薪資分布', fontsize=18, fontweight='bold', pad=20)

    legend_labels = [f'{lab}  ${val:,}（{val / total * 100:.0f}%）'
                     for lab, val in zip(labels, values)]
    ax1.legend(wedges, legend_labels, loc='center left', bbox_to_anchor=(1.02, 0.5),
               fontsize=9, frameon=False)

    # === 下：長條圖 ===
    bar_labels = labels.copy()
    bar_values = values.copy()
    bar_colors = list(colors)
    if fuel_amt > 0:
        bar_labels.append('油費')
        bar_values.append(-fuel_amt)
        bar_colors.append('#E57373')
    if park_amt > 0:
        bar_labels.append('停車')
        bar_values.append(-park_amt)
        bar_colors.append('#FFB74D')
    if ledger_exp > 0:
        bar_labels.append('記帳支出')
        bar_values.append(-ledger_exp)
        bar_colors.append('#BA68C8')

    bars = ax2.barh(range(len(bar_labels)), bar_values, color=bar_colors, edgecolor='white', linewidth=1.5)
    ax2.set_yticks(range(len(bar_labels)))
    ax2.set_yticklabels(bar_labels, fontsize=10)
    ax2.invert_yaxis()
    ax2.axvline(x=0, color='gray', linewidth=0.8)
    ax2.set_title(f'{year}/{month:02d} 收支明細', fontsize=18, fontweight='bold', pad=15)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='x', linestyle='--', alpha=0.3)

    max_abs = max(map(abs, bar_values))
    for bar, val in zip(bars, bar_values):
        width = bar.get_width()
        if width >= 0:
            x = width + max_abs * 0.01
            ha = 'left'
            color = '#333'
        else:
            x = -max_abs * 0.01
            ha = 'right'
            color = 'white'
        ax2.text(x, bar.get_y() + bar.get_height()/2, f'${abs(int(val)):,}',
                 va='center', ha=ha, fontsize=11, fontweight='bold', color=color)
    ax2.set_xlim(-max_abs * 1.15, max_abs * 1.15)

    summary_parts = [f'毛薪 ${total:,}']
    if fuel_amt > 0:
        summary_parts.append(f'油費 -${fuel_amt:,}')
    if park_amt > 0:
        summary_parts.append(f'停車 -${park_amt:,}')
    if ledger_exp > 0:
        summary_parts.append(f'記帳 -${ledger_exp:,}')
    summary_parts.append(f'淨薪 ${net:,}')
    summary = '  |  '.join(summary_parts)
    fig.text(0.5, 0.02, summary, ha='center', fontsize=13, fontweight='bold', color='#333')

    plt.savefig(filepath, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    return True
