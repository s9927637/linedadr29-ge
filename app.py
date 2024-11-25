import os
import json
import datetime
import logging
import requests
import pytz
import time
import threading
from flask import Flask, request, jsonify, send_from_directory
from google.auth.transport.requests import Request
from google.auth import default
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from flask_cors import CORS


# 設置日誌
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
CORS(app)

# 設定時區為 UTC
os.environ['TZ'] = 'UTC'
datetime.datetime.utcnow()

# Google Sheets 設定
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
if not SPREADSHEET_ID:
    logging.error("環境變數 'SPREADSHEET_ID' 未設置")
    raise ValueError("環境變數 'SPREADSHEET_ID' 未設置")

RANGE_NAME = 'Sheet1!A2:H2'  # 更新範圍，第二劑和第三劑接種時間在疫苗名稱後面
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

google_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
if not google_creds_json:
    logging.error("環境變數 'GOOGLE_APPLICATION_CREDENTIALS_JSON' 未設置")
    raise ValueError("環境變數 'GOOGLE_APPLICATION_CREDENTIALS_JSON' 未設置或無內容")

google_creds_info = json.loads(google_creds_json)
creds = Credentials.from_service_account_info(google_creds_info)
service = build('sheets', 'v4', credentials=creds)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN')
LINE_API_URL = "https://api.line.me/v2/bot/message/push"


# 新增的功能：延遲回覆用戶的施打時間
def delayed_reply(user_id, second_dose_date, third_dose_date):
    # 等待 10 秒後回覆第二劑施打時間
    time.sleep(10)
    send_line_message(user_id, f"您的第二劑接種時間為：{second_dose_date}。")

    # 如果有第三劑，則再等 10 秒後回覆第三劑施打時間
    if third_dose_date:
        time.sleep(10)
        send_line_message(user_id, f"您的第三劑接種時間為：{third_dose_date}。")

# 計算接種日期
def calculate_vaccine_doses(vaccine_name: str, first_dose_date: str):
    first_dose_date_obj = datetime.datetime.strptime(first_dose_date, '%Y-%m-%d')  # 解析為日期對象

    if vaccine_name == '子宮頸疫苗':
        # 第二劑和第三劑接種時間
        second_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=60)
        third_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=180)
        return second_dose_date_obj.strftime('%Y-%m-%d'), third_dose_date_obj.strftime('%Y-%m-%d')
    
    elif vaccine_name in ['欣克疹疫苗', 'A肝疫苗']:
        # 第二劑接種時間是接種日期後60天
        second_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=60)
        return second_dose_date_obj.strftime('%Y-%m-%d'), None
    
    else:
        return None, None

# 發送 LINE 訊息
def send_line_message(user_id, vaccine_name, first_dose_date, second_dose_date, third_dose_date=None):
    if not user_id:
        logging.error("無效的 user_id: 未提供 user_id")
        return

    if third_dose_date:
        message_text = (
            f"你的接種疫苗：{vaccine_name}\n接種日期：{first_dose_date}\n第二劑接種時間：{second_dose_date}\n第三劑接種時間：{third_dose_date}。\n"
            "我們會在第二劑及第三劑接種前3天傳送訊息提醒您接種。"
        )
    else:
        message_text = (
            f"你的接種疫苗：{vaccine_name}\n接種日期：{first_dose_date}\n第二劑接種時間：{second_dose_date}。\n"
            "我們會在第二劑接種前3天傳送訊息提醒您接種。"
        )

    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }

    message = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }

    response = requests.post(LINE_API_URL, headers=headers, json=message)

    if response.status_code == 200:
        logging.info("LINE 訊息發送成功")
    else:
        logging.error(f"發送 LINE 訊息失敗: {response.text}")


# 根路由處理 index.html
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


@app.route('/saveData', methods=['POST'])
def save_data():
    try:
        # 檢查 JSON 請求格式
        data = request.get_json()
        if data is None:
            logging.error("請求中的 JSON 格式無效")
            return jsonify({'status': 'error', 'message': '無效的 JSON 格式'}), 400
        
        logging.debug(f"接收到資料: {data}")

        # 檢查 userID 是否存在
        if not data.get('userID'):
            logging.error(f"缺少 userID，請求資料: {data}")
            return jsonify({'status': 'error', 'message': '缺少 userID'}), 400

        # 確保填表時間格式正確並以台北時間顯示
        taipei_tz = pytz.timezone('Asia/Taipei')  # 設定台北時區
        form_time = datetime.datetime.now(taipei_tz).strftime('%Y年%m月%d日%H時%M分')  # 使用台北時間

        # 計算接種日期
        second_dose_date, third_dose_date = calculate_vaccine_doses(data['vaccineName'], data['appointmentDate'])

        # 構建要寫入 Google Sheets 的資料，根據欄位順序進行設置
        if data['vaccineName'] == '子宮頸疫苗':
            if third_dose_date is None:  # 只有第二劑接種時間
                values = [
                    [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], second_dose_date, None, data['userID'], form_time, "已提醒", None]
                ]
            else:  # 第二劑和第三劑接種時間
                values = [
                    [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date, data['userID'], form_time, "已提醒", "已提醒"]
                ]
        elif data['vaccineName'] in ['欣克疹疫苗', 'A肝疫苗']:
            if third_dose_date is None:  # 只有第二劑接種時間
                values = [
                    [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], second_dose_date, None, data['userID'], form_time, None, "已提醒"]
                ]
            else:  # 第二劑和第三劑接種時間
                values = [
                    [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date, data['userID'], form_time, None, "已提醒"]
                ]
        else:
            values = [
                [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date, data['userID'], form_time, None, None]
            ]

        body = {'values': values}

        logging.debug(f"寫入 Google Sheets 的資料: {values}")
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption='RAW', body=body).execute()
        

# 在 save_data 函數中新增以下行
threading.Thread(target=delayed_reply, args=(data['userID'], second_dose_date, third_dose_date)).start()  

        # 發送 LINE 訊息
        send_line_message(data['userID'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date)

        logging.info("資料成功儲存至 Google Sheets 且 LINE 訊息已發送")
        return jsonify({'status': 'success', 'message': '資料成功儲存並發送 LINE 訊息'}), 200

    except Exception as e:
        logging.error(f"儲存資料時發生錯誤: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

# 設置日誌
logging.basicConfig(level=logging.DEBUG)

@app.route('/log', methods=['POST'])
def log_error():
    data = request.get_json()
    if data is None or 'message' not in data:
        return jsonify({'status': 'error', 'message': '無效的日誌格式'}), 400

    # 記錄日誌
    logging.error(data['message'])
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
