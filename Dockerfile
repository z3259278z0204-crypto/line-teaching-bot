# 教具機器人執行環境：Python 3.12
FROM python:3.12-slim

WORKDIR /app

# 先裝相依（利用快取）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製其餘程式（含 fonts / assets）
COPY . .

# matplotlib 用無視窗後端；監聽埠 8080
ENV MPLBACKEND=Agg
ENV PORT=8080
EXPOSE 8080

CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:8080", "--timeout", "180"]
