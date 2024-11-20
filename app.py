import os
import json
import datetime
import logging
import requests
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

RANGE_NAME = 'Sheet1!A2:F2'  # 更新範圍，第二劑和第三劑接種時間在疫苗名稱後面
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


# 計算接種日期
def calculate_vaccine_doses(vaccine_name: str, first_dose_date: str):
    first_dose_date_obj = datetime.datetime.strptime(first_dose_date, '%Y-%m-%d')  # 解析為日期對象

    if vaccine_name == '子宮頸疫苗':
        # 第二劑和第三劑接種時間
        second_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=60)
        third_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=180)
        return second_dose_date_obj.strftime('%Y-%m-%d'), third_dose_date_obj.strftime('%Y-%m-%d')
    
    elif vaccine_name == '欣克疹疫苗' or vaccine_name == 'A肝疫苗':
        # 第二劑接種時間是接種日期後60天
        second_dose_date_obj = first_dose_date_obj + datetime.timedelta(days=60)
        return second_dose_date_obj.strftime('%Y-%m-%d'), None
    
    else:
        return None, None


# 發送 LINE 訊息
def send_line_message(user_id, vaccine_name, first_dose_date, second_dose_date, third_dose_date=None):
    if third_dose_date:
        message_text = (
            f"你的接種疫苗：{vaccine_name}，接種日期是{first_dose_date}，第二劑接種時間：{second_dose_date}，第三劑接種時間：{third_dose_date}。\n"
            "系統會在第三劑接種前3天提醒您接種。"
        )
    else:
        message_text = (
            f"你的接種疫苗：{vaccine_name}，接種日期是{first_dose_date}，第二劑接種時間：{second_dose_date}。\n"
            "系統會在第二劑接種前3天提醒您接種。"
        )
    
    message = {
        "to": user_id,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {LINE_CHANNEL_ACCESS_TOKEN}'
    }
    
    response = requests.post(LINE_API_URL, headers=headers, json=message)
    
    if response.status_code == 200:
        logging.info("LINE message sent successfully")
    else:
        logging.error(f"Failed to send LINE message: {response.text}")


# 根路由處理 index.html
@app.route('/')
def index():
    return send_from_directory('static', 'index.html')


# 處理 /saveData 路由的 POST 請求
@app.route('/saveData', methods=['POST'])
def save_data():
    try:
        # 檢查 JSON 請求格式
        data = request.get_json()
        if data is None:
            logging.error("Invalid JSON format in request")
            return jsonify({'status': 'error', 'message': 'Invalid JSON format'}), 400
        
        logging.debug(f"Received data: {data}")

        # 格式化填表時間為 XXXX年XX月XX日XX時XX分 (24小時制)
        form_time = datetime.datetime.now().strftime('%Y年%m月%d日%H時%M分')

        # 計算接種日期
        second_dose_date, third_dose_date = calculate_vaccine_doses(data['vaccineName'], data['appointmentDate'])

        # 構建要寫入 Google Sheets 的資料
        if third_dose_date is None:  # 只有第二劑接種時間
            values = [
                [data['userName'], data['userPhone'], data['vaccineName'], second_dose_date, None, data['appointmentDate'], data['userID'], form_time]
            ]
        else:  # 第二劑和第三劑接種時間
            values = [
                [data['userName'], data['userPhone'], data['vaccineName'], second_dose_date, third_dose_date, data['appointmentDate'], data['userID'], form_time]
            ]

        body = {'values': values}

        logging.debug(f"Writing data to Google Sheets: {values}")
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption='RAW', body=body).execute()

        # 發送 LINE 訊息
        send_line_message(data['userID'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date)

        logging.info("Data saved successfully to Google Sheets and LINE message sent")
        return jsonify({'status': 'success', 'message': 'Data saved successfully and LINE message sent'}), 200

    except Exception as e:
        logging.error(f"Error occurred while saving data: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
