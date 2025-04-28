# E:\MeteoraMeme\meteora_bot\src\modules\strategy.py

from typing import List, Dict, Any
from src.utils.logger import get_logger

log = get_logger(__name__)


def filter_new_pairs(groups: List[Dict[str, Any]], threshold: float = 1.01) -> List[Dict[str, Any]]:
    filtered_groups = []
    total_groups = len(groups)
    
    for group in groups:
        group_name = group.get("name", "N/A")
        pools = group.get("pairs", [])
        is_new_group = True
        
        for pool in pools:
            try:
                ctv = float(pool.get("cumulative_trade_volume", "0"))
            except ValueError:
                ctv = 0.0
            
            tv24h = pool.get("trade_volume_24h", 0.0)
            ratio = ctv / tv24h if tv24h > 0 else (999999 if ctv > 0 else 0)
            
            if ratio > threshold:
                is_new_group = False
                break

        if is_new_group:
            filtered_groups.append(group)

    log.info(f"New pairs filter: {len(filtered_groups)}/{total_groups} groups remain.")
    return filtered_groups


def filter_large_liquidity_pairs(groups: List[Dict[str, Any]], max_liquidity: float = 1_000_000.0) -> List[
    Dict[str, Any]]:
    """
    Исключает группы (пары), суммарная ликвидность всех пулов которых превышает max_liquidity.
    Это помогает отсеять пары-гиганты, где наша доля будет слишком мала.

    :param groups: Список групп, каждая группа содержит "name" и "pairs".
    :param max_liquidity: Порог суммарной ликвидности (в USD), выше которого пара считается слишком крупной.
    :return: Список групп с суммарной ликвидностью, не превышающей max_liquidity.
    """
    filtered_groups = []
    total_groups = len(groups)
    log.debug(f"Starting filter_large_liquidity_pairs with {total_groups} groups, max_liquidity={max_liquidity}.")
    for group in groups:
        group_name = group.get("name", "N/A")
        total_liq = 0.0
        for pool in group.get("pairs", []):
            try:
                liq_value = float(pool.get("liquidity", "0"))
            except ValueError:
                liq_value = 0.0
            total_liq += liq_value
        if total_liq > max_liquidity:
            # Избыточный вывод закомментирован:
            # log.debug(f"Group '{group_name}' excluded due to high total liquidity: {total_liq:.2f} > {max_liquidity}")
            continue
        else:
            filtered_groups.append(group)
    log.info(f"Filter done: from {total_groups} groups => {len(filtered_groups)} remain after liquidity check.")
    return filtered_groups


def filter_and_sort_by_volume(groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Для каждой группы (пары):
      1. Отсеивает пулы, у которых volume.min_30 меньше, чем liquidity (т.е. ratio < 1).
      2. Для оставшихся пулов вычисляет коэффициент ratio = volume.min_30 / liquidity.
      3. Сортирует пулы внутри группы по убыванию этого коэффициента.
    Затем сортирует группы по значению ratio лучшего пула (первого в списке) в порядке убывания.

    :param groups: Список групп, каждая группа содержит ключ "pairs" с данными пулов.
    :return: Список групп, отфильтрованных и отсортированных по отношению volume.min_30 / liquidity.
    """
    filtered_groups = []
    for group in groups:
        group_name = group.get("name", "N/A")
        valid_pools = []
        for pool in group.get("pairs", []):
            try:
                liquidity = float(pool.get("liquidity", "0"))
            except ValueError:
                liquidity = 0.0
            try:
                vol_min_30 = float(pool.get("volume", {}).get("min_30", 0.0))
            except ValueError:
                vol_min_30 = 0.0
            if liquidity <= 0:
                continue
            ratio = vol_min_30 / liquidity
            if ratio >= 1.0:
                pool["ratio"] = ratio  # сохраняем коэффициент для сортировки
                valid_pools.append(pool)
            # Закомментирован избыточный вывод:
            # else:
            #     log.debug(f"In group '{group_name}', pool '{pool.get('name', 'N/A')}' filtered out: ratio {ratio:.2f} < 1.")
        if valid_pools:
            valid_pools.sort(key=lambda p: p.get("ratio", 0.0), reverse=True)
            group["pairs"] = valid_pools
            filtered_groups.append(group)
        # Закомментирован вывод, если группа не содержит валидных пулов:
        # else:
        #     log.debug(f"Group '{group_name}' has no pools with ratio >= 1 and is excluded from volume analysis.")
    filtered_groups.sort(key=lambda g: g.get("pairs", [{}])[0].get("ratio", 0.0)
    if g.get("pairs") else 0.0, reverse=True)
    log.info(f"After volume filtering and sorting by ratio, {len(filtered_groups)} groups remain.")
    return filtered_groups


def generate_entry_signal(best_pool: Dict[str, Any],
                          price_history: List[float],
                          ratio_threshold: float = 2.0,
                          required_consecutive: int = 3) -> bool:
    """
    Генерирует сигнал для входа в позицию по пулу.
    Условия для сигнала:
      - Лучший пул должен иметь коэффициент ratio (volume.min_30/liquidity) не меньше ratio_threshold.
      - В price_history (списке последних значений current_price) должно быть как минимум required_consecutive значений,
        при этом каждое следующее значение больше предыдущего.

    :param best_pool: Словарь с данными лучшего пула (ожидается наличие ключей 'current_price' и 'ratio').
    :param price_history: Список значений current_price за последние несколько минут.
    :param ratio_threshold: Минимальное требуемое значение ratio для сигнала.
    :param required_consecutive: Количество последовательных минут с ростом цены.
    :return: True, если условия для входа выполнены, иначе False.
    """
    try:
        current_price = float(best_pool.get("current_price", 0))
    except ValueError:
        current_price = 0.0

    ratio = best_pool.get("ratio", 0.0)
    if ratio < ratio_threshold:
        return False

    if len(price_history) < required_consecutive:
        return False

    for i in range(1, required_consecutive):
        if price_history[-i] <= price_history[-i - 1]:
            return False

    return True
