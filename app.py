import os
import json
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)

SPREADSHEET_ID = 'YOUR_SPREADSHEET_ID'  # 替換為您的試算表ID
RANGE_NAME = 'Sheet1!A1:F1'  # 根據您的試算表範圍修改

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 檢查並處理Google API認證
creds = None
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

service = build('sheets', 'v4', credentials=creds)

# 接收LIFF表單資料並將資料寫入Google試算表
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
