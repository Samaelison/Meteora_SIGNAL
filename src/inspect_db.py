# inspect_db.py
import sqlite3
import json
from datetime import datetime

def print_db():
    conn = sqlite3.connect('meteora_bot.db')
    cursor = conn.cursor()
    
    # Получить все записи из таблицы
    cursor.execute("SELECT coin_id, stage, current_ratio, last_checked, price_history FROM coin_states")
    rows = cursor.fetchall()
    
    print("\n" + "="*50)
    print(f"Всего записей: {len(rows)}")
    print("="*50)
    
    for row in rows:
        # Преобразуем timestamp в читаемую дату (если есть)
        last_checked = datetime.fromtimestamp(row[3]).strftime('%Y-%m-%d %H:%M:%S') if row[3] else "N/A"
        
        # Десериализуем историю цен из JSON
        try:
            price_history = json.loads(row[4]) if row[4] else []
        except json.JSONDecodeError:
            price_history = "Ошибка декодирования"
            
        print(f"""
Адрес пула: {row[0]}
Текущий этап: {row[1]}
Последний ratio: {row[2]:.2f}
Последняя проверка: {last_checked}
История цен: {price_history}
{'-'*50}""")
    
    conn.close()

if __name__ == "__main__":
    print_db()