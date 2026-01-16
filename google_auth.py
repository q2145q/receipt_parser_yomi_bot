from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle

# Области доступа для Google API
SCOPES = [
    'https://www.googleapis.com/auth/drive',  # ИЗМЕНЕНО: полный доступ к Drive
    'https://www.googleapis.com/auth/spreadsheets'
]

def get_google_credentials():
    """
    Получение credentials для Google API.
    При первом запуске откроет браузер для авторизации.
    """
    creds = None
    
    # Проверяем, есть ли сохраненный token
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    # Если нет валидных credentials, получаем новые
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Сохраняем credentials для следующих запусков
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return creds