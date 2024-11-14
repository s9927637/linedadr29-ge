# 使用官方的Python基礎映像
FROM python:3.10-slim

# 設置工作目錄
WORKDIR /app

# 複製當前目錄中的所有檔案到容器的工作目錄
COPY . /app

# 安裝所需的依賴
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 暴露容器的5000端口（Flask的預設端口）
EXPOSE 5000

# 設置環境變數
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# 執行Flask應用
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
