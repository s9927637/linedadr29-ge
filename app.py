import os
import json
import datetime
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials  # 修正這行
from googleapiclient.discovery import build

app = Flask(__name__)

# 設定時區為 UTC
os.environ['TZ'] = 'UTC'
datetime.datetime.utcnow()  # 使用 UTC 時間

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = 'Sheet1!A2:F2'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 使用服務帳戶檔案來取得憑證
creds = Credentials.from_service_account_file('googlesheetapi_key.json', scopes=SCOPES)

service = build('sheets', 'v4', credentials=creds)

@app.route('/saveData', methods=['POST'])
def save_data():
    try:
        data = request.json
        values = [
            [data['userName'], data['userPhone'], data['vaccineName'], data['appointmentDate'], data['userID'], data['formTime']]
        ]
        body = {
            'values': values
        }
        service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
            valueInputOption='RAW', body=body).execute()
        return json.dumps({'status': 'success'}), 200
    except Exception as e:
        print(f"Error occurred: {e}")
        return json.dumps({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
