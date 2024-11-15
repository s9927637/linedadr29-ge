import os
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory
from google.auth.transport.requests import Request
from google.auth import default  # 使用 Google Cloud Run 預設認證
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from flask_cors import CORS
app = Flask(__name__)
CORS(app)

# 設定時區為 UTC
os.environ['TZ'] = 'UTC'
datetime.datetime.utcnow()  # 使用 UTC 時間

# Google Sheets 設定
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = 'Sheet1!A2:F2'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 讀取環境變數中的 JSON 金鑰內容，並解析為字典
google_creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
if not google_creds_json:
    raise ValueError("環境變數 'GOOGLE_APPLICATION_CREDENTIALS_JSON' 未設置或無內容")

google_creds_info = json.loads(google_creds_json)

# 使用 from_service_account_info 建立憑證物件
creds = Credentials.from_service_account_info(google_creds_info)
service = build('sheets', 'v4', credentials=creds)

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
            return jsonify({'status': 'error', 'message': 'Invalid JSON format'}), 400
        
        # 構建要寫入 Google Sheets 的資料
        values = [
            [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], data['userID'], data['formTime']]
        ]
        body = {'values': values}

        # 寫入 Google Sheets
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption='RAW', body=body).execute()

        return jsonify({'status': 'success', 'message': 'Data saved successfully'}), 200

    except Exception as e:
        # 錯誤處理
        print(f"Error occurred: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
