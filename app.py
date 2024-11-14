import os
import json
from flask import Flask, request
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)

# 從環境變數中獲取配置
SPREADSHEET_ID = os.getenv('SPREADSHEET_ID')  # 從環境變數獲取試算表ID
RANGE_NAME = os.getenv('RANGE_NAME', 'Sheet1!A1:F1')  # 從環境變數獲取範圍，默認為 'Sheet1!A1:F1'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 使用上傳的憑證JSON文件來進行身份驗證
creds = None
# 檢查憑證文件是否存在
if os.path.exists('google sheet api.json'):
    # 從google sheet api.json載入憑證
    creds = Credentials.from_service_account_file('google sheet api.json', scopes=SCOPES)

# 如果沒有有效的憑證，則進行身份驗證
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
