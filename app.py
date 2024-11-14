import os
import json
import datetime
from flask import Flask, request, jsonify
from google.auth.transport.requests import Request
from google.auth import default  # 使用 Google Cloud Run 預設認證
from googleapiclient.discovery import build

app = Flask(__name__)

# 設定時區為 UTC
os.environ['TZ'] = 'UTC'
datetime.datetime.utcnow()  # 使用 UTC 時間

# Google Sheets 設定
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = 'Sheet1!A2:F2'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 使用 Google Cloud Run 預設的服務帳戶來取得憑證
creds, project = default(scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

@app.route('/saveData', methods=['POST'])
def save_data():
    # 檢查請求是否為 JSON 格式
    if not request.is_json:
        print("Error: Request is not JSON")
        return jsonify({'status': 'error', 'message': 'Request must be JSON'}), 400

    try:
        # 解析 JSON 資料
        data = request.json
        print(f"Received data: {data}")

        # 檢查資料欄位是否完整
        required_fields = ['userName', 'userPhone', 'vaccineName', 'appointmentDate', 'userID', 'formTime']
        for field in required_fields:
            if field not in data:
                print(f"Missing field: {field}")
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
