from sheets_handler import SheetsHandler
import os
from dotenv import load_dotenv

load_dotenv()

sheets = SheetsHandler(os.getenv('GOOGLE_SHEET_ID'))
sheets.setup_headers()
print("✅ Заголовки обновлены!")