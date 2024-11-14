import os
import json
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.service_account import Credentials  # 修正這行
from googleapiclient.discovery import build

app = Flask(__name__)

SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')
RANGE_NAME = 'Sheet1!A1:F1'

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 使用服務帳戶檔案來取得憑證
creds = Credentials.from_service_account_file('googlesheetapi_key.json', scopes=SCOPES)

service = build('sheets', 'v4', credentials=creds)

@app.route('/saveData', methods=['POST'])
def save_data():
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

if __name__ == '__main__':
    app.run(debug=True)
