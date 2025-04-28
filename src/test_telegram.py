import os
import requests
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / "config" / "secrets.env"
load_dotenv(dotenv_path=env_path)

def send_test_message():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    
    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={
            "chat_id": chat_id,
            "text": "🚀 Тестовое сообщение через синхронный запрос"
        }
    )
    
    print("Статус:", response.status_code)
    print("Ответ:", response.json())

if __name__ == "__main__":
    send_test_message()