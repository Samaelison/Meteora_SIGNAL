# E:\MeteoraMeme\meteora_bot\src\modules\meteora_api.py

import requests
from src.utils.logger import get_logger
from src.utils.helpers import load_config

log = get_logger(__name__)

class MeteoraAPI:
    def __init__(self):
        config = load_config()
        self.base_url = config["meteora"]["base_url"]

    def get_filtered_pairs(self):
        try:
            endpoint = f"{self.base_url}/pair/all_by_groups"
            params = {
                "limit": 1000,
                "hide_low_tvl": 1000,
                "include_token_mints": "So11111111111111111111111111111111111111112"
            }
            headers = {
                "Accept": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
            log.debug(f"Requesting: {endpoint} with {params}")
            response = requests.get(endpoint, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            groups = data.get("groups", [])
            total = data.get("total", 0)
            log.debug(f"Received {len(groups)} groups from Meteora (filtered). total={total}")
            # Если нужно, можно раскомментировать для отладки:
            # log.debug(f"Full response: {data}")
            return groups
        except requests.exceptions.RequestException as e:
            log.error(f"Error fetching /pair/all_by_groups: {e}")
            return None
