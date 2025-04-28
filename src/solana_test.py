# E:\MeteoraMeme\meteora_bot\src\utils\solana_test.py

import os
import time
import requests
import subprocess
import sys
import threading
from dotenv import load_dotenv

from solana.rpc.api import Client
from solders.pubkey import Pubkey

from src.utils.logger import get_logger
from src.utils.helpers import load_config

log = get_logger(__name__)

load_dotenv("C:/Python/Projects/meteora_bot/config/secrets.env")
MY_SOLANA_ADDRESS = os.getenv("MY_SOLANA_ADDRESS")
if not MY_SOLANA_ADDRESS:
    raise ValueError("MY_SOLANA_ADDRESS not in env")

wallet_pubkey = Pubkey.from_string(MY_SOLANA_ADDRESS)

config = load_config()
rpc_endpoint = os.getenv("SOLANA_RPC_ENDPOINT")
client = Client(rpc_endpoint)

#######################################################
# Wrapper Server Utilities
#######################################################
def get_wallet_balance(pubkey: Pubkey) -> float:
    """Получить баланс SOL (в единицах SOL)."""
    resp = client.get_balance(pubkey)
    return resp.value / 1_000_000_000

def log_stream(stream, prefix):
    """Вспомогательная функция для логирования stdout/err subprocess (Node)"""
    for line in iter(stream.readline, ''):
        if not line:
            break
        line_stripped = line.rstrip()
        if line_stripped:
            log.info(f"{prefix} {line_stripped}")

def start_wrapper_server() -> subprocess.Popen:
    """Запускаем локальный Node-сервер (meteora_wrapper.js)"""
    node_path = "C:/Program Files/nodejs/node.exe"
    wrapper_script = "C:/Python/Projects/meteora_bot/src/meteora_wrapper.js"
    log.info(f"Starting wrapper server via: {node_path} {wrapper_script}")

    process = subprocess.Popen(
        [node_path, wrapper_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        universal_newlines=True,
        bufsize=1
    )

    thread_stdout = threading.Thread(target=log_stream, args=(process.stdout, "NODE_OUT:"), daemon=True)
    thread_stderr = threading.Thread(target=log_stream, args=(process.stderr, "NODE_ERR:"), daemon=True)
    thread_stdout.start()
    thread_stderr.start()

    time.sleep(5)
    if process.poll() is not None:
        stdout, stderr = process.communicate()
        log.error("Meteora wrapper server terminated unexpectedly.")
        log.error(f"stdout: {stdout}")
        log.error(f"stderr: {stderr}")
        raise RuntimeError("Meteora wrapper server failed to start.")
    return process

def stop_wrapper_server(process: subprocess.Popen):
    """Шлём shutdown запрос на Node-сервер и ждём"""
    url = "http://localhost:3000/shutdown"
    log.info(f"Sending shutdown request to {url}")
    try:
        resp = requests.post(url, timeout=10)
        resp.raise_for_status()
        log.info(f"Shutdown request response: {resp.text}")
    except Exception as e:
        log.error(f"Error on shutdown request: {e}")

    try:
        process.wait(timeout=10)
        log.info("Wrapper server exited gracefully.")
    except Exception as e:
        log.warning(f"Server did not exit in 10s, forcing kill: {e}")
        process.kill()
        log.info("Wrapper server forcibly killed.")

def simple_post(url, json_data=None):
    """Утилита для HTTP POST с JSON"""
    r = requests.post(url, json=json_data, timeout=120)
    r.raise_for_status()
    return r.json()

#######################################################
# API Wrappers
#######################################################
def swap_with_price_impact(lb_pair: str, amount_in: str, swap_y_to_x: bool, price_impact_bps: str):
    payload = {
        "lbPair": lb_pair,
        "amountIn": amount_in,
        "swapYtoX": swap_y_to_x,
        "priceImpactBps": price_impact_bps
    }
    return simple_post("http://localhost:3000/swap_with_price_impact", json_data=payload)

def add_liquidity_spot(lb_pair: str, amount_sol: str, strategy_type: int):
    payload = {
        "lbPair": lb_pair,
        "amountSol": amount_sol,
        "strategyType": str(strategy_type)
    }
    return simple_post("http://localhost:3000/add_liquidity_spot", json_data=payload)

def add_liquidity_x_only(lb_pair: str, strategy_type: int):
    payload = {
        "lbPair": lb_pair,
        "strategyType": str(strategy_type)
    }
    return simple_post("http://localhost:3000/add_liquidity_x_only", json_data=payload)

def remove_liquidity_and_close(lb_pair: str, position_pubkey: str):
    payload = {
        "lbPair": lb_pair,
        "positionPubkey": position_pubkey
    }
    return simple_post("http://localhost:3000/remove_liquidity_and_close", json_data=payload)

def get_active_bin(lb_pair: str):
    """Возвращает dict c "activeBinId" (int) и "price" (str)"""
    payload = {"lbPair": lb_pair}
    return simple_post("http://localhost:3000/get_active_bin", json_data=payload)

def get_pool_mints(lb_pair: str):
    payload = {"lbPair": lb_pair}
    return simple_post("http://localhost:3000/get_pool_mints", json_data=payload)

def list_positions_by_user_and_lbpair(lb_pair: str, user_pubkey: str):
    """
    /list_positions_by_user_and_lbpair
    Возвращает структуру вида:
    {
      "activeBin": { "binId": int, "price": str|null },
      "userPositions": [
        {
          "publicKey": str,
          "positionData": { ... }
        },
        ...
      ]
    }
    """
    payload = {
        "lbPair": lb_pair,
        "userPubkey": user_pubkey
    }
    return simple_post("http://localhost:3000/list_positions_by_user_and_lbpair", json_data=payload)

#######################################################
# attempt_with_retries (для swap и т.д., кроме remove)
#######################################################
def attempt_with_retries(action_func, max_retries=20, description=""):
    """
    Старый метод, используемый для чего угодно, кроме remove.
    """
    err_msg = ""
    for attempt in range(1, max_retries + 1):
        try:
            return action_func()
        except Exception as e:
            err_msg = str(e)
            log.warning(f"[{description}] attempt {attempt} => error: {err_msg}")
            time.sleep(3)
    raise RuntimeError(f"Failed to {description} after {max_retries} attempts, last error: {err_msg}")

#######################################################
# attempt_with_retries_check_position_removed (для remove)
#######################################################
def attempt_with_retries_check_position_removed(
    remove_func,
    lb_pair: str,
    position_pubkey: str,
    max_retries=20,
    description=""
):
    """
    Если при удалении ловим ошибку (404, Signature expired и т.д.),
    проверяем list_positions_by_user_and_lbpair => вдруг позиция уже нет,
    тогда считаем удалённой и выходим.
    """
    err_msg = ""
    for attempt in range(1, max_retries + 1):
        try:
            return remove_func(lb_pair, position_pubkey)
        except Exception as e:
            err_msg = str(e)
            log.warning(f"[{description}] attempt {attempt} => error: {err_msg}")

            # Проверим, не исчезла ли позиция
            try:
                pos_info = list_positions_by_user_and_lbpair(lb_pair, MY_SOLANA_ADDRESS)
                user_positions = pos_info.get("userPositions", [])
                found = any(p.get("publicKey") == position_pubkey for p in user_positions)
                if not found:
                    log.info(f"[{description}] Position {position_pubkey} not found => remove success.")
                    return {
                        "txSignatures": [],
                        "finalSolBalance": 0,
                        "finalXBalance": "0",
                        "message": "Position already removed."
                    }
            except Exception as ee:
                log.warning(f"[{description}] additional check => error: {ee}")

            time.sleep(5)

    raise RuntimeError(f"Failed to {description} after {max_retries} attempts, last error: {err_msg}")

#######################################################
# attempt_with_retries_check_for_open (add liq => polling 20s)
#######################################################
def attempt_with_retries_check_for_open(
    action_func,
    old_sol_balance: float,
    sol_needed_decrease: float = 0.05,
    max_retries=20,
    polling_interval=2,
    polling_total=20,   # <--- УВЕЛИЧИЛИ ДО 20 СЕКУНД
    description="",
    lb_pair=None,
    user_pubkey=None
):
    """
    Если при попытке открыть позицию (BID/SPOT) ловим ошибку,
    делаем 20-секундный polling баланса SOL (каждые 2с).
      - Если delta >= 0.05 => считаем, что позиция всё же открылась => дергаем list_positions.
      - Иначе (по истечении 20с) => перед следующим retry
        мы тоже дергаем list_positions => вдруг позиция всё же появилась.
    """
    err_msg = ""
    for attempt in range(1, max_retries + 1):
        try:
            # 1) Сразу пытаемся вызвать action_func()
            return action_func()
        except Exception as e:
            err_msg = str(e)
            log.warning(f"[{description}] attempt {attempt} => error: {err_msg}")

            # 2) Короткий polling 20 сек, каждые 2 сек
            log.info(f"[{description}] => Starting short polling of SOL for up to {polling_total}s...")
            start_ts = time.time()
            recognized = False
            while (time.time() - start_ts) < polling_total:
                curr_sol = get_wallet_balance(wallet_pubkey)
                delta = old_sol_balance - curr_sol

                # LOGGING delta
                log.info(f"[{description}] poll => delta={delta:.5f}, needed={sol_needed_decrease:.2f}")

                if delta >= sol_needed_decrease:
                    log.info(f"[{description}] Despite error, SOL dropped {delta:.4f} >= {sol_needed_decrease:.4f}")
                    log.info("=> Attempting to find real positionPubkey via list_positions...")

                    if not lb_pair or not user_pubkey:
                        log.warning("No lb_pair / user_pubkey provided => returning None as pubkey.")
                        return {"positionPubkey": None}

                    positions_info = list_positions_by_user_and_lbpair(lb_pair, user_pubkey)
                    user_positions = positions_info.get("userPositions", [])

                    if len(user_positions) == 1:
                        real_pubkey = user_positions[0]["publicKey"]
                        log.info(f"[{description}] Found exactly one position => {real_pubkey}")
                        return {"positionPubkey": real_pubkey}
                    else:
                        msg = (f"Balance dropped but found {len(user_positions)} positions => {user_positions}")
                        log.error(msg)
                        raise RuntimeError(msg)

                time.sleep(polling_interval)

            # 3) Если за 20с не упало на 0.05 => ещё одна safety-проверка list_positions
            log.info(f"[{description}] => Poll ended. Checking list_positions_by_user_and_lbpair before next retry.")
            if lb_pair and user_pubkey:
                positions_info = list_positions_by_user_and_lbpair(lb_pair, user_pubkey)
                user_positions = positions_info.get("userPositions", [])
                if len(user_positions) == 1:
                    real_pubkey = user_positions[0]["publicKey"]
                    log.info(f"[{description}] Poll didn't see delta, but found 1 pos => {real_pubkey}")
                    return {"positionPubkey": real_pubkey}
                else:
                    log.info(f"[{description}] after poll: found {len(user_positions)} positions => going to next retry.")

            # => идём на следующий retry
            time.sleep(5)

    raise RuntimeError(f"Failed to {description} after {max_retries} attempts, last error: {err_msg}")

#######################################################
# Polling for SOL after remove (no change)
#######################################################
def poll_for_sol_balance_increase(old_balance: float, deposit_sol: float, overhead: float = 0.06):
    min_increase = overhead + 0.9 * deposit_sol
    log.info(f"[poll_for_sol_balance_increase] waiting until SOL increases by >= {min_increase:.4f}")

    while True:
        curr = get_wallet_balance(wallet_pubkey)
        delta = curr - old_balance
        if delta >= min_increase:
            log.info(f"[poll_for_sol_balance_increase] OK: delta={delta:.4f} >= {min_increase:.4f}")
            break
        else:
            log.info(f"[poll_for_sol_balance_increase] still waiting... delta={delta:.4f} < {min_increase:.4f}")
            time.sleep(2)

def poll_for_sol_return_min_increase(
    old_balance: float,
    min_increase: float,
    first_wait: int,
    second_wait: int,
    remove_func,
    remove_lb_pair: str,
    remove_pubkey: str,
):
    start_time = time.time()
    while True:
        elapsed = time.time() - start_time
        if elapsed > first_wait:
            log.warning(f"[poll_for_sol_return_min_increase] first_wait={first_wait}s expired => second remove attempt")
            remove_func(remove_lb_pair, remove_pubkey)
            break

        curr_balance = get_wallet_balance(wallet_pubkey)
        delta = curr_balance - old_balance
        if delta >= min_increase:
            log.info(f"[poll_for_sol_return_min_increase] OK after first wait => delta={delta:.4f} >= {min_increase:.4f}")
            return
        else:
            time.sleep(2)

    log.info(f"[poll_for_sol_return_min_increase] waiting second_wait={second_wait}s after second remove")
    start2 = time.time()
    while True:
        elapsed2 = time.time() - start2
        if elapsed2 > second_wait:
            raise RuntimeError(
                f"poll_for_sol_return_min_increase => Not reached delta >= {min_increase:.4f} after second remove as well."
            )

        curr_balance = get_wallet_balance(wallet_pubkey)
        delta = curr_balance - old_balance
        if delta >= min_increase:
            log.info(f"[poll_for_sol_return_min_increase] OK after second remove => delta={delta:.4f} >= {min_increase:.4f}")
            return
        else:
            time.sleep(2)

#######################################################
# Main Strategy
#######################################################
def main():
    print("ENTER MAIN()")
    log.info("=== Bot started ===")
    log.info(f"RPC endpoint={rpc_endpoint}")

    server_proc = None
    try:
        server_proc = start_wrapper_server()

        lb_pair = "71qnE9YXPfUP47KrNJ75MkrNbcE5QuAyt5qaarcg2avP"
        mints_info = get_pool_mints(lb_pair)
        mintX = mints_info["mintX"]
        decimalsX = mints_info["decimalsX"]

        currentMode = "BID"
        positionPubkey = None
        binIDposition = None
        is_rearranging = False

        deposit_amount_sol = 0.1
        overhead_sol = 0.06

        # Упрощённые helpers:
        def remove_position_safely(_lb_pair: str, _position_pubkey: str, desc: str):
            return attempt_with_retries_check_position_removed(
                remove_func=remove_liquidity_and_close,
                lb_pair=_lb_pair,
                position_pubkey=_position_pubkey,
                max_retries=15,
                description=desc
            )

        def open_bid_position():
            old_sol_balance = get_wallet_balance(wallet_pubkey)
            return attempt_with_retries_check_for_open(
                action_func=lambda: add_liquidity_spot(lb_pair, str(deposit_amount_sol), 2),
                old_sol_balance=old_sol_balance,
                sol_needed_decrease=0.05,
                max_retries=15,
                polling_interval=2,
                polling_total=20,  # 20s
                description="open BID position",
                lb_pair=lb_pair,
                user_pubkey=MY_SOLANA_ADDRESS
            )

        def open_spot_position():
            old_sol_balance = get_wallet_balance(wallet_pubkey)
            return attempt_with_retries_check_for_open(
                action_func=lambda: add_liquidity_x_only(lb_pair, 0),
                old_sol_balance=old_sol_balance,
                sol_needed_decrease=0.05,
                max_retries=15,
                polling_interval=2,
                polling_total=20,  # 20s
                description="open SPOT position",
                lb_pair=lb_pair,
                user_pubkey=MY_SOLANA_ADDRESS
            )

        # Вспомогательная обёртка для get_active_bin
        def safe_get_active_bin(pair: str):
            """Вызываем get_active_bin с retry, чтобы не падать при временных 500/timeout."""
            return attempt_with_retries(
                action_func=lambda: get_active_bin(pair),
                max_retries=20,
                description="get_active_bin"
            )

        # 1) Изначально открываем BID
        try:
            is_rearranging = True
            bid_resp = open_bid_position()
            positionPubkey = bid_resp.get("positionPubkey")
            if not positionPubkey:
                raise RuntimeError("No positionPubkey returned after initial open BID.")

            active_bin_info = safe_get_active_bin(lb_pair)
            binIDposition = active_bin_info["activeBinId"]
            log.info(f"Opened initial BID => positionPubkey={positionPubkey}, binIDpos={binIDposition}")
        finally:
            is_rearranging = False

        # 2) Основной цикл
        while True:
            time.sleep(30)

            if is_rearranging:
                log.info("Skipping iteration: rearranging in progress.")
                continue

            # Вместо прямого get_active_bin:
            active_bin_info = safe_get_active_bin(lb_pair)  # <--- retry-обёртка
            currentActiveBinId = active_bin_info["activeBinId"]
            log.info(f"Loop => mode={currentMode}, binIDpos={binIDposition}, activeBin={currentActiveBinId}")

            if currentMode == "BID":
                # a) BID->BID
                if currentActiveBinId > binIDposition:
                    is_rearranging = True
                    log.info("Price > binIDposition => remove old BID and re-open new BID.")
                    try:
                        old_sol_balance = get_wallet_balance(wallet_pubkey)

                        remove_position_safely(lb_pair, positionPubkey, desc="remove old BID")
                        positionPubkey = None

                        poll_for_sol_balance_increase(old_sol_balance, deposit_amount_sol, overhead_sol)
                        log.info("Waiting 60s before re-opening BID position...")
                        time.sleep(60)  # Добавляем задержку 60 секунд

                        new_bid_resp = open_bid_position()
                        new_pubkey = new_bid_resp.get("positionPubkey")
                        if not new_pubkey:
                            raise RuntimeError("No positionPubkey after re-opening BID.")
                        positionPubkey = new_pubkey

                        new_bin_info = safe_get_active_bin(lb_pair)
                        binIDposition = new_bin_info["activeBinId"]
                        log.info(f"Re-opened BID => positionPubkey={positionPubkey}, binIDpos={binIDposition}")
                    finally:
                        is_rearranging = False
                        
                        
                # b) BID->SPOT                        
                elif currentActiveBinId < (binIDposition - 69):
                    is_rearranging = True
                    log.info("Price < (binIDposition - 69) => switching to SPOT.")
                    try:
                        old_position_pubkey = positionPubkey
                        old_sol_balance = get_wallet_balance(wallet_pubkey)

                        remove_position_safely(lb_pair, old_position_pubkey, desc="remove old BID")
                        positionPubkey = None

                        poll_for_sol_return_min_increase(
                            old_balance=old_sol_balance,
                            min_increase=0.05,
                            first_wait=60,
                            second_wait=120,
                            remove_func=lambda lp, ppub: remove_position_safely(lp, ppub, "second remove BID"),
                            remove_lb_pair=lb_pair,
                            remove_pubkey=old_position_pubkey
                        )
                        log.info("Waiting 60s before opening SPOT position...")
                        time.sleep(60)  # Добавляем задержку 60 секунд

                        spot_resp = open_spot_position()
                        new_pubkey = spot_resp.get("positionPubkey")
                        if not new_pubkey:
                            raise RuntimeError("No positionPubkey returned after opening SPOT.")
                        positionPubkey = new_pubkey

                        new_bin_info = safe_get_active_bin(lb_pair)
                        binIDposition = new_bin_info["activeBinId"]
                        currentMode = "SPOT"
                        log.info(f"Switched to SPOT => positionPubkey={positionPubkey}, binIDpos={binIDposition}")
                    finally:
                        is_rearranging = False

            else:
                # *** SPOT MODE ***
                # c) SPOT->SPOT
                if currentActiveBinId < binIDposition:
                    is_rearranging = True
                    log.info("Price < binIDposition => re-open SPOT lower.")
                    try:
                        old_position_pubkey = positionPubkey
                        old_sol_balance = get_wallet_balance(wallet_pubkey)

                        remove_position_safely(lb_pair, old_position_pubkey, desc="remove old SPOT")
                        positionPubkey = None

                        poll_for_sol_return_min_increase(
                            old_balance=old_sol_balance,
                            min_increase=0.05,
                            first_wait=60,
                            second_wait=120,
                            remove_func=lambda lp, ppub: remove_position_safely(lp, ppub, "second remove SPOT"),
                            remove_lb_pair=lb_pair,
                            remove_pubkey=old_position_pubkey
                        )
                        log.info("Waiting 60s before re-opening SPOT position...")
                        time.sleep(60)  # Добавляем задержку 60 секунд

                        resp_spot2 = open_spot_position()
                        new_pubkey = resp_spot2.get("positionPubkey")
                        if not new_pubkey:
                            raise RuntimeError("No positionPubkey after re-opening SPOT.")
                        positionPubkey = new_pubkey

                        new_bin_info = safe_get_active_bin(lb_pair)
                        binIDposition = new_bin_info["activeBinId"]
                        log.info(f"Re-opened SPOT => positionPubkey={positionPubkey}, binIDpos={binIDposition}")
                    finally:
                        is_rearranging = False

                # d) SPOT->finish
                elif currentActiveBinId >= (binIDposition + 69):
                    is_rearranging = True
                    log.info("Price > (binIDposition + 69) => final close.")
                    try:
                        remove_position_safely(lb_pair, positionPubkey, desc="final close SPOT")
                        positionPubkey = None
                        log.info("All done. Exiting loop.")
                        break
                    finally:
                        is_rearranging = False

        # end while

    except Exception as e:
        log.error(f"Error in main strategy: {e}")

    finally:
        if server_proc:
            stop_wrapper_server(server_proc)
        log.info("=== End ===")

if __name__ == "__main__":
    main()
