
import sys
import os
from dotenv import load_dotenv
from pathlib import Path 
from src.utils.db import Database
from src.modules.notifier import TelegramNotifier

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, PROJECT_ROOT)

load_dotenv(Path(PROJECT_ROOT) / "config" / "secrets.env")


from src.utils.logger import get_logger
from src.modules.meteora_api import MeteoraAPI
from src.modules.strategy import (
    filter_new_pairs,
    filter_large_liquidity_pairs,
    filter_and_sort_by_volume,
    generate_entry_signal,
)

log = get_logger(__name__)



def main(db, notifier):
    log.info("Bot started.")

    meteora_api = MeteoraAPI()
    groups = meteora_api.get_filtered_pairs()
    if groups is None:
        log.error("Failed to fetch pairs (filtered) from Meteora API.")
        return

    log.info(f"Successfully fetched {len(groups)} filtered pairs from API.")

    # Изменено здесь: фильтруем ТОЛЬКО новые пары
    new_groups = filter_new_pairs(groups, threshold=1.01)  # ← Заменили функцию
    log.info(f"After selecting NEW pairs => we have {len(new_groups)} groups to analyze.")

    # Дальнейшие шаги работают уже с новыми парами
    liquidity_filtered_groups = filter_large_liquidity_pairs(new_groups, max_liquidity=1_000_000.0)  # ← Переменная new_groups
    log.info(f"After exclude 'high-liquidity' pairs => we have {len(liquidity_filtered_groups)} groups to analyze further.")

    final_groups = filter_and_sort_by_volume(liquidity_filtered_groups)
    log.info(f"After volume filtering and sorting, {len(final_groups)} groups remain for final analysis.")

    # Логирование результатов (осталось без изменений)
    for i, group in enumerate(final_groups):
        group_name = group.get("name", "N/A")
        pairs_count = len(group.get("pairs", []))
        best_pool = group.get("pairs", [{}])[0]
        best_ratio = best_pool.get("ratio", 0.0)
        try:
            best_volume = float(best_pool.get("volume", {}).get("min_30", 0.0))
        except ValueError:
            best_volume = 0.0
        try:
            best_liquidity = float(best_pool.get("liquidity", 0.0))
        except ValueError:
            best_liquidity = 0.0
        try:
            best_price = float(best_pool.get("current_price", 0.0))
        except ValueError:
            best_price = 0.0
        best_bin = best_pool.get("bin_step", "N/A")

        log.info(f"Group #{i+1}: {group_name} ({pairs_count} pools) - "
                 f"ratio: {best_ratio:.2f}, volume.min_30: {best_volume:.2f}, "
                 f"liquidity: {best_liquidity:.2f}, current_price: {best_price:.10f}, bin_step: {best_bin}")

   
    if final_groups and len(final_groups[0].get("pairs", [])) > 0:
        best_pool = final_groups[0]["pairs"][0]
        coin_id = best_pool.get("address")
    
        if coin_id != "unknown":
            coin_state = db.get_coin_state(coin_id)
            price_history = coin_state.get("price_history", []) if coin_state else []
            entry_signal = generate_entry_signal(best_pool, price_history, ratio_threshold=4.0, required_consecutive=3)
            log.info(f"Entry signal for best pool in group '{final_groups[0].get('name', 'N/A')}': {entry_signal}")
            
    else:
        log.info("No valid pools in final_groups.")
    

    for group in final_groups:
        for pool in group["pairs"]:
            coin_id = pool["address"]
            if coin_id == "unknown":
                continue

            # Получаем состояние из БД
            coin_state = db.get_coin_state(coin_id)
            current_stage = 0
            current_ratio = 0.0
            price_history = []

            if coin_state:
                current_stage = coin_state["stage"]
                current_ratio = coin_state["current_ratio"]
                price_history = coin_state["price_history"]
            else:
                try:
                    current_ratio = float(pool.get("ratio", 0.0))
                except (TypeError, ValueError):
                    current_ratio = 0.0
                
                db.update_coin_state(
                    coin_id=coin_id,
                    stage=0,
                    current_ratio=current_ratio,
                    price_history=[]
                )

            # Получаем текущие метрики
            try:
                current_ratio = float(pool.get("ratio", 0.0))
                current_price = float(pool.get("current_price", 0.0))
            except (TypeError, ValueError):
                continue  # Пропускаем пул при ошибке конвертации

            # Логика перехода между этапами (исправлены отступы!)
            new_stage = current_stage
            new_price_history = price_history.copy()

            if current_ratio > 4.0:
                if current_stage == 0:
                    new_stage = 1
                    new_price_history = [current_price]
                else:
                    new_price_history.append(current_price)
                    if len(new_price_history) >= 2 and new_price_history[-1] > new_price_history[-2]:
                        new_stage += 1
                    else:
                        new_stage = 0
            else:
                new_stage = 0

            new_price_history = new_price_history[-3:]  # Обрезаем историю

            # Обновляем состояние в БД
            db.update_coin_state(
                coin_id=coin_id,
                stage=new_stage,
                current_ratio=current_ratio,
                price_history=new_price_history
            )

            if new_stage >= 3 and (coin_state is None or coin_state.get("stage", 0) < 3):
                log.info(f"🚨 Coin {coin_id} passed all stages! Sending alert.")
                notifier.send_alert(pool)
                db.reset_coin_state(coin_id)


if __name__ == "__main__":
    import time
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    db = Database()
    notifier = TelegramNotifier()
    
    iteration_counter = 0  # Счетчик итераций
    
    try:
        while True:
            log.info("Starting new iteration...")
            main(db, notifier)
            iteration_counter += 1
            
            # Очистка БД каждый час (60 итераций)
            if iteration_counter >= 60:
                log.info("Очистка БД по расписанию...")
                db.clear_all()
                iteration_counter = 0  # Сброс счетчика
            
            log.info("Iteration completed. Waiting 60 seconds...")
            time.sleep(60)
    except KeyboardInterrupt:
        log.info("Bot stopped by user interrupt")
    except Exception as e:
        log.error(f"Critical error: {str(e)}")
        raise
