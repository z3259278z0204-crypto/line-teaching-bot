"""本地一次性執行：產生 Rich Menu 圖片並存到 assets/richmenu.png
產完後 commit 進 repo，rich_menu.py 會讀這張上傳到 LINE。
不在 Render 執行（不需要 Pillow 在生產環境）。
風格：C 深色高雅（深藍底 + 螢光色 icon + 白字）"""
import os
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2500, 1686
COLS, ROWS = 4, 2
CELL_W, CELL_H = WIDTH // COLS, HEIGHT // ROWS

FONT_PATH = os.path.join(os.path.dirname(__file__), 'fonts', 'NotoSansTC-Regular.otf')


# ============== ICON 繪製函式 ==============

def icon_calendar(draw, cx, cy, size, color):
    w = size
    h = size * 0.95
    x0, y0 = cx - w//2, cy - h//2
    draw.rounded_rectangle((x0 + w*0.18, y0 - h*0.08, x0 + w*0.28, y0 + h*0.12),
                            radius=int(w*0.025), fill=color)
    draw.rounded_rectangle((x0 + w*0.72, y0 - h*0.08, x0 + w*0.82, y0 + h*0.12),
                            radius=int(w*0.025), fill=color)
    draw.rounded_rectangle((x0, y0, x0+w, y0+h),
                            radius=int(w*0.06), outline=color, width=int(w*0.045))
    draw.rounded_rectangle((x0, y0, x0+w, y0+h*0.28),
                            radius=int(w*0.06), fill=color)
    draw.rectangle((x0, y0+h*0.18, x0+w, y0+h*0.28), fill=color)
    cell_w = w / 4
    cell_h = (h - h*0.28) / 3
    for r in range(3):
        for c in range(4):
            gx = x0 + c*cell_w + cell_w*0.2
            gy = y0 + h*0.28 + r*cell_h + cell_h*0.2
            gx2 = gx + cell_w*0.6
            gy2 = gy + cell_h*0.6
            draw.ellipse((gx, gy, gx2, gy2), fill=color)


def icon_plus(draw, cx, cy, size, color):
    r = size // 2
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=color, width=int(size*0.08))
    bar = int(size*0.5)
    thick = int(size*0.12)
    draw.rounded_rectangle((cx-bar//2, cy-thick//2, cx+bar//2, cy+thick//2),
                            radius=thick//2, fill=color)
    draw.rounded_rectangle((cx-thick//2, cy-bar//2, cx+thick//2, cy+bar//2),
                            radius=thick//2, fill=color)


def icon_fuel(draw, cx, cy, size, color):
    w = size * 0.65
    h = size * 0.92
    x0, y0 = cx - w//2, cy - h//2 + size*0.05
    draw.rounded_rectangle((x0, y0, x0+w, y0+h),
                            radius=int(w*0.12), outline=color, width=int(size*0.06))
    draw.rectangle((x0+w*0.15, y0-size*0.06, x0+w*0.85, y0+size*0.06),
                    fill=color)
    inner = int(size*0.05)
    draw.rounded_rectangle((x0+inner*2, y0+size*0.18, x0+w-inner*2, y0+size*0.42),
                            radius=int(inner*1.5), fill=color)
    nx = x0 + w + size*0.02
    ny = y0 + size*0.25
    draw.rectangle((nx, ny, nx+size*0.08, ny+size*0.18), fill=color)
    draw.rectangle((nx+size*0.08, ny-size*0.06, nx+size*0.18, ny+size*0.05), fill=color)


def icon_parking(draw, cx, cy, size, color):
    r = size // 2
    draw.rounded_rectangle((cx-r, cy-r, cx+r, cy+r),
                            radius=int(size*0.18), outline=color, width=int(size*0.08))
    pf = ImageFont.truetype(FONT_PATH, int(size*0.85))
    bbox = draw.textbbox((0,0), 'P', font=pf)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1] - int(size*0.04)),
              'P', font=pf, fill=color)


def icon_money(draw, cx, cy, size, color):
    r = size // 2
    draw.ellipse((cx-r, cy-r, cx+r, cy+r),
                  outline=color, width=int(size*0.08))
    pf = ImageFont.truetype(FONT_PATH, int(size*0.75))
    bbox = draw.textbbox((0,0), '$', font=pf)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1] - int(size*0.05)),
              '$', font=pf, fill=color)


def icon_chart(draw, cx, cy, size, color):
    w = size * 0.9
    h = size * 0.9
    x0, y0 = cx - w//2, cy - h//2
    draw.line((x0, y0+h, x0+w, y0+h), fill=color, width=int(size*0.05))
    draw.line((x0, y0, x0, y0+h), fill=color, width=int(size*0.05))
    bw = w * 0.18
    gap = (w - bw*3) / 4
    heights = [h*0.45, h*0.78, h*0.62]
    for i, bh in enumerate(heights):
        bx = x0 + gap + i*(bw+gap)
        by = y0 + h - bh
        draw.rounded_rectangle((bx, by, bx+bw, y0+h),
                                radius=int(bw*0.18), fill=color)


def icon_tools(draw, cx, cy, size, color):
    w = size * 0.95
    h = size * 0.75
    x0, y0 = cx - w//2, cy - h//2 + size*0.05
    handle_w = w * 0.4
    draw.rounded_rectangle((cx - handle_w//2, y0 - size*0.18, cx + handle_w//2, y0),
                            radius=int(size*0.08), outline=color, width=int(size*0.06))
    draw.rounded_rectangle((x0, y0, x0+w, y0+h),
                            radius=int(size*0.06), fill=color)
    lock_w = w * 0.18
    lock_h = h * 0.45
    lx = cx - lock_w//2
    ly = y0 + h*0.25
    draw.rounded_rectangle((lx, ly, lx+lock_w, ly+lock_h),
                            radius=int(size*0.03), fill='white')


def icon_help(draw, cx, cy, size, color):
    r = size // 2
    draw.ellipse((cx-r, cy-r, cx+r, cy+r),
                  outline=color, width=int(size*0.08))
    pf = ImageFont.truetype(FONT_PATH, int(size*0.75))
    bbox = draw.textbbox((0,0), '?', font=pf)
    tw = bbox[2]-bbox[0]
    th = bbox[3]-bbox[1]
    draw.text((cx - tw//2 - bbox[0], cy - th//2 - bbox[1] - int(size*0.05)),
              '?', font=pf, fill=color)


# 8 格內容（順序對應 rich_menu.py 的 ACTIONS）
CELLS = [
    (icon_calendar, '今天行程'),
    (icon_plus,     '新增行程'),
    (icon_fuel,     '記錄加油'),
    (icon_parking,  '記錄停車'),
    (icon_money,    '本月薪資'),
    (icon_chart,    '薪資圖表'),
    (icon_tools,    '記錄器材'),
    (icon_help,     '說明'),
]

# 螢光色配色
COLORS = ['#5EE7DF', '#7DFFB3', '#FFA45B', '#FFD66B',
          '#FFCB47', '#C792EA', '#6BB1FF', '#9CA3AF']


def main():
    img = Image.new('RGB', (WIDTH, HEIGHT), '#0F1119')
    draw = ImageDraw.Draw(img)

    for i, (icon_fn, label) in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        x0, y0 = col*CELL_W, row*CELL_H
        pad = 26
        color = COLORS[i]
        # 卡片：深色
        draw.rounded_rectangle((x0+pad, y0+pad, x0+CELL_W-pad, y0+CELL_H-pad),
                                radius=58, fill='#1C2034')
        cx = x0 + CELL_W//2
        cy = y0 + CELL_H//2 - 100
        # icon
        icon_fn(draw, cx, cy, 260, color)
        # label
        lf = ImageFont.truetype(FONT_PATH, 92)
        bbox = draw.textbbox((0,0), label, font=lf)
        tw = bbox[2]-bbox[0]
        lx = x0 + (CELL_W - tw)//2 - bbox[0]
        ly = y0 + CELL_H - 200
        draw.text((lx, ly), label, font=lf, fill='#FFFFFF')

    os.makedirs(os.path.join(os.path.dirname(__file__), 'assets'), exist_ok=True)
    out_path = os.path.join(os.path.dirname(__file__), 'assets', 'richmenu.png')
    img.save(out_path, 'PNG', optimize=True)
    print(f'✅ 圖片已產生：{out_path}')
    print(f'尺寸：{WIDTH}x{HEIGHT}（{COLS}x{ROWS} = {COLS*ROWS} 格）')


if __name__ == '__main__':
    main()
