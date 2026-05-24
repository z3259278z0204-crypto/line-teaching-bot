"""本地一次性執行：產生 Rich Menu 圖片並存到 assets/richmenu.png
產完後 commit 進 repo，setup_richmenu.py 會讀這張上傳到 LINE。
不在 Render 執行（不需要 Pillow 在生產環境）。"""
from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 2500, 1686
COLS, ROWS = 3, 2
CELL_W, CELL_H = WIDTH // COLS, HEIGHT // ROWS

CELLS = [
    ('TODAY',  '今天行程',  '#5B8DEF'),
    ('NEW',    '新增行程',  '#5BC97E'),
    ('SALARY', '本月薪資',  '#F5A623'),
    ('CHART',  '薪資圖表',  '#B964D6'),
    ('GEAR',   '記錄器材',  '#FF7B5C'),
    ('HELP',   '說明',      '#4A4A4A'),
]

FONT_PATH = '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'


def main():
    img = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    draw = ImageDraw.Draw(img)

    label_font = ImageFont.truetype(FONT_PATH, 150)
    sub_font = ImageFont.truetype(FONT_PATH, 70)

    for i, (en, label, color) in enumerate(CELLS):
        col, row = i % COLS, i // COLS
        x0, y0 = col * CELL_W, row * CELL_H
        x1, y1 = x0 + CELL_W, y0 + CELL_H

        pad = 20
        draw.rounded_rectangle(
            (x0 + pad, y0 + pad, x1 - pad, y1 - pad),
            radius=50, fill=color
        )

        # 中文主標籤
        lbox = draw.textbbox((0, 0), label, font=label_font)
        lw, lh = lbox[2] - lbox[0], lbox[3] - lbox[1]
        lx = x0 + (CELL_W - lw) // 2
        ly = y0 + (CELL_H - lh) // 2 - 50
        draw.text((lx + 5, ly + 5), label, font=label_font, fill='#00000044')
        draw.text((lx, ly), label, font=label_font, fill='white')

        # 英文副標
        sbox = draw.textbbox((0, 0), en, font=sub_font)
        sw = sbox[2] - sbox[0]
        sx = x0 + (CELL_W - sw) // 2
        sy = ly + lh + 50
        draw.text((sx, sy), en, font=sub_font, fill='#FFFFFFAA')

    img.save('assets/richmenu.png', 'PNG', optimize=True)
    print('✅ 圖片已產生：assets/richmenu.png')
    print(f'尺寸：{WIDTH}x{HEIGHT}')


if __name__ == '__main__':
    main()
