# 使用官方的Python基礎映像
FROM python:3.10-slim

# 設置工作目錄
WORKDIR /app

# 複製當前目錄中的所有檔案到容器的工作目錄
COPY . /app
COPY static /app/static

# 安裝所需的依賴
RUN pip install flask-cors
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# zeabur的8080端口（Flask的預設端口）
EXPOSE 8080

# 設置環境變數
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
# Set the time zone to UTC
ENV TZ=UTC

# 執行Flask應用
CMD ["flask", "run", "--host=0.0.0.0", "--port=8080"]
