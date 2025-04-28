# src/modules/notifier.py
import os
import requests
from src.utils.logger import get_logger

log = get_logger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        

    def send_alert(self, coin_data: dict):
        if not self.token or not self.chat_id:
            log.error("Telegram credentials not configured. Alert skipped.")
            return
    
        # Логирование данных пула
        log.debug(f"Данные для отправки: {coin_data}")
    
        # Формируем сообщение
        pool_address = coin_data.get("address", "N/A")
        meteora_link = f"https://meteora.ag/dlmm/{pool_address}"  # Пример ссылки
        
        message = (
            f"🚀 **Монета прошла все этапы\!**\n"
            f"• Название: `{coin_data.get('name', 'N/A')}`\n"
            f"• Адрес пула: [{pool_address}]({meteora_link})\n"
            f"• Ratio: `{coin_data.get('ratio', 0.0):.2f}`\n"
            f"• Цена: `{coin_data.get('current_price', 0.0)}`"
        )
        
        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "MarkdownV2"  # Включить Markdown
                }
            )
            # Логирование ответа Telegram
            log.debug(f"Статус: {response.status_code}, Ответ: {response.text}")
            response.raise_for_status()
            log.info("Уведомление отправлено.")
        except Exception as e:
            log.error(f"Ошибка: {str(e)}")
            if hasattr(e, 'response'):
                log.error(f"Тело ошибки: {e.response.text}")