import os
import json
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)

# Google Sheets API 設定
SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID'
RANGE_NAME = 'Sheet1!A1:D1'  # 根據需要修改範圍

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

creds = None
# 若之前有存儲的憑證，載入它們
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file(
            'credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    # 保存憑證供下次使用
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('sheets', 'v4', credentials=creds)

@app.route('/saveData', methods=['POST'])
def save_data():
    data = request.json
    values = [
        [data['userID'], data['userName'], data['vaccineName'], data['appointmentDate']]
    ]
    body = {
        'values': values
    }
    # 將資料寫入 Google 試算表
    service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID, range=RANGE_NAME,
        valueInputOption='RAW', body=body).execute()
    return json.dumps({'status': 'success'}), 200

if __name__ == '__main__':
    app.run(debug=True)
