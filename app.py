import os
import json
import datetime
from flask import Flask, request, jsonify
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials  # 確保引用正確
from googleapiclient.discovery import build

app = Flask(__name__)

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

@app.route('/saveData', methods=['POST'])
def save_data():
    # 檢查 JSON 請求格式
    data = request.get_json()
    if data is None:
        print("Error: Invalid JSON format")
        return jsonify({'status': 'error', 'message': 'Invalid JSON format'}), 400

    try:
        # 確認資料欄位完整性
        required_fields = ['userName', 'userPhone', 'vaccineName', 'appointmentDate', 'userID', 'formTime']
        for field in required_fields:
            if field not in data:
                print(f"Error: Missing field - {field}")
                return jsonify({'status': 'error', 'message': f'Missing field: {field}'}), 400

        # 構建要寫入 Google Sheets 的資料
        values = [
            [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], data['userID'], data['formTime']]
        ]
        body = {'values': values}

        # 寫入 Google Sheets
        print(f"Appending data to Google Sheets: {values}")
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption='RAW', body=body).execute()

        print("Data saved successfully to Google Sheets")
        return jsonify({'status': 'success', 'message': 'Data saved successfully'}), 200

    except Exception as e:
        # 錯誤處理
        print(f"Error occurred: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
