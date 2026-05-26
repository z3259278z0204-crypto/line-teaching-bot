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
    return _FONT_PROP


def _parse_date(s):
    s = (s or '').strip()
    for fmt in ('%Y/%m/%d', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


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
        title = (row.get('標題') or '').strip() or '未分類'
        by_title[title] += price
        total += price
        count += 1

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
    net = total - fuel_amt - park_amt

    sorted_items = sorted(by_title.items(), key=lambda x: -x[1])
    labels = [t for t, _ in sorted_items]
    values = [v for _, v in sorted_items]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 11))
    fig.patch.set_facecolor('#FAFAFA')

    colors = plt.cm.Set2(range(len(labels)))

    # === 上：圓餅圖 ===
    fp = _FONT_PROP
    wedges, texts, autotexts = ax1.pie(
        values,
        labels=labels,
        colors=colors,
        autopct=lambda p: f'${int(p*total/100):,} ({p:.0f}%)',
        startangle=90,
        textprops={'fontsize': 12, 'fontproperties': fp},
        wedgeprops={'edgecolor': 'white', 'linewidth': 2},
    )
    for t in autotexts:
        t.set_color('white')
        t.set_fontweight('bold')
        t.set_fontsize(11)
        if fp:
            t.set_fontproperties(fp)
    for t in texts:
        if fp:
            t.set_fontproperties(fp)
    ax1.set_title(f'{year}/{month:02d} 薪資分布', fontsize=18, fontweight='bold', pad=20, fontproperties=fp)

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

    bars = ax2.barh(range(len(bar_labels)), bar_values, color=bar_colors, edgecolor='white', linewidth=1.5)
    ax2.set_yticks(range(len(bar_labels)))
    ax2.set_yticklabels(bar_labels, fontsize=12, fontproperties=fp)
    ax2.invert_yaxis()
    ax2.axvline(x=0, color='gray', linewidth=0.8)
    ax2.set_title(f'{year}/{month:02d} 收支明細', fontsize=18, fontweight='bold', pad=15, fontproperties=fp)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)
    ax2.grid(axis='x', linestyle='--', alpha=0.3)

    for bar, val in zip(bars, bar_values):
        width = bar.get_width()
        x = width + (max(map(abs, bar_values)) * 0.01) if width >= 0 else width - (max(map(abs, bar_values)) * 0.01)
        ha = 'left' if width >= 0 else 'right'
        ax2.text(x, bar.get_y() + bar.get_height()/2, f'${abs(int(val)):,}',
                 va='center', ha=ha, fontsize=11, fontweight='bold', fontproperties=fp)

    summary = f'毛薪 ${total:,}  |  油費 -${fuel_amt:,}  |  停車 -${park_amt:,}  |  淨薪 ${net:,}'
    fig.text(0.5, 0.02, summary, ha='center', fontsize=13, fontweight='bold', color='#333', fontproperties=fp)

    plt.subplots_adjust(left=0.15, right=0.95, top=0.93, bottom=0.08, hspace=0.35)
    plt.savefig(filepath, dpi=120, facecolor=fig.get_facecolor())
    plt.close(fig)
    return True
