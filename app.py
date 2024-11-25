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
def delayed_reply(user_id):
    # 等待 10 秒後回覆第二劑施打時間
    time.sleep(10)
    
    # 查詢 Google Sheets 獲取接種紀錄
    result = get_vaccine_record(user_id)
    
    if result['status'] == 'success':
        # 獲取接種紀錄
        records = result['data']
        vaccine_name = records[0][2]  # 假設疫苗名稱在第三欄
        second_dose_date = records[0][4]  # 假設第二劑在第五欄
        third_dose_date = records[0][5]   # 假設第三劑在第六欄
        
        # 發送第二劑接種時間的訊息
        send_line_message_reminder(user_id, vaccine_name, second_dose_date)

        # 如果有第三劑，則再等 10 秒後回覆第三劑施打時間
        if third_dose_date:
            time.sleep(10)
            send_line_message_reminder(user_id, vaccine_name, None, third_dose_date)
        
        # 在發送完訊息後再標註 Google Sheets 中的接種紀錄
        mark_vaccine_record(user_id, second_dose_date, third_dose_date)
    else:
        send_line_message_reminder(user_id, "未找到您的接種紀錄。")

# 查詢接種紀錄的函數
def get_vaccine_record(user_id):
    try:
        logging.debug(f"查詢用戶 {user_id} 的疫苗接種記錄")

        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range='Sheet1!A:H'  # 假設資料在 A 到 H 欄
        ).execute()

        values = result.get('values', [])
        user_records = []

        for row in values:
            if len(row) > 6 and row[6] == user_id:  # 假設 userID 在第七欄
                user_records.append(row)

        if user_records:
            logging.info(f"找到用戶 {user_id} 的接種記錄")
            return {'status': 'success', 'data': user_records}
        else:
            logging.warning(f"未找到用戶 {user_id} 的接種記錄")
            return {'status': 'error', 'message': '未找到接種紀錄'}

    except Exception as e:
        logging.error(f"查詢接種紀錄時發生錯誤: {e}")
        return {'status': 'error', 'message': str(e)}

# 標註接種紀錄的函數
def mark_vaccine_record(user_id, second_dose_date, third_dose_date):
    try:
        # 更新 Google Sheets 中的接種紀錄
        range_to_update = 'Sheet1!I2:J2'  # 假設標註在 I 和 J 欄
        values = [
            ["已提醒", "已提醒" if third_dose_date else ""]
        ]
        body = {'values': values}

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_to_update,
            valueInputOption='RAW',
            body=body
        ).execute()

        logging.info("接種紀錄已標註成功")
    except Exception as e:
        logging.error(f"標註接種紀錄時發生錯誤: {e}")

# 第一個發送 LINE 訊息的函數
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

# 第二個發送 LINE 訊息的函數
def send_line_message_reminder(user_id, vaccine_name=None, second_dose_date=None, third_dose_date=None):
    if not user_id:
        logging.error("無效的 user_id: 未提供 user_id")
        return

    if second_dose_date and third_dose_date:
        message_text = (
            f"提醒您，您的{vaccine_name}第二劑接種時間為：{second_dose_date}，已經可以接種囉！"
        )
    elif second_dose_date:
        message_text = (
            f"提醒您，您的{vaccine_name}第二劑接種時間為：{second_dose_date}，已經可以接種囉！"
        )
    elif third_dose_date:
        message_text = (
            f"提醒您，您的{vaccine_name}第三劑接種時間為：{third_dose_date}，已經可以接種囉！"
        )
    else:
        message_text = "未提供接種時間資訊。"

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

        # 立即回覆用戶接種疫苗的詳細資訊
        send_line_message(data['userID'], data['vaccineName'], data['appointmentDate'], second_dose_date, third_dose_date)

        # 在 save_data 函數中新增以下行
        threading.Thread(target=delayed_reply, args=(data['userID'],)).start()  

        logging.info("資料成功儲存至 Google Sheets 且 LINE 訊息已發送")
        return jsonify({'status': 'success', 'message': '資料成功儲存並發送 LINE 訊息'}), 200

    except Exception as e:
        logging.error(f"儲存資料時發生錯誤: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
