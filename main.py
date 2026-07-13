"""
=================================================================
  STAKE PLINKO VIP WAGER BOT - AUTO-PILOT (Python Version)
  Konfigurasi : config.json
  API Token   : Replit Secret → STAKE_API_KEY
=================================================================
  Cara pakai:
    1. Set STAKE_API_KEY di Replit Secrets
    2. Sesuaikan config.json sesuai kebutuhan
    3. Jalankan: python main.py
=================================================================
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 0. LOAD ENV & CONFIG
# ─────────────────────────────────────────────
load_dotenv()

API_KEY = os.environ.get("STAKE_API_KEY", "")
if not API_KEY:
    raise SystemExit(
        "[ERROR] STAKE_API_KEY belum diisi di Replit Secrets."
    )

with open("config.json", "r") as f:
    BOT_CONFIG = json.load(f)

API_URL = "https://stake.com/_api/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "x-access-token": API_KEY,
    "Connection":     "keep-alive",
}

# ─────────────────────────────────────────────
# 1. STATE / PENCATAT DATA INTERNAL
# ─────────────────────────────────────────────
stats = {
    "totalWagered":   0.0,
    "currentProfit":  0.0,
    "totalSpins":     0,
    "initialBalance": 0.0,
}

# ─────────────────────────────────────────────
# 2. GRAPHQL QUERIES
# ─────────────────────────────────────────────
PLINKO_BET_MUTATION = """
mutation PlinkoBet($amount: Float!, $rows: Int!, $risk: CasinoGamePlinkoRiskEnum!, $currency: CurrencyEnum!) {
  plinkoBet(amount: $amount, rows: $rows, risk: $risk, currency: $currency) {
    id
    payoutMultiplier
    amount
    payout
    currency
    user {
      balances {
        available { amount currency }
      }
    }
  }
}
"""

BALANCE_QUERY = """
query UserBalance {
  user {
    name
    balances {
      available { amount currency }
    }
  }
}
"""

# ─────────────────────────────────────────────
# 3. FUNGSI API
# ─────────────────────────────────────────────
def fetch_balances() -> tuple[str, float, list]:
    """
    Ambil semua saldo dari Stake API.
    Return: (username, saldo_currency_aktif, daftar_semua_saldo)
    """
    r = requests.post(API_URL, json={"query": BALANCE_QUERY}, headers=HEADERS, timeout=10)
    if not r.ok:
        raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL: {data['errors']}")

    user     = data["data"]["user"]
    username = user["name"]
    balances = user["balances"]
    target   = BOT_CONFIG.get("currency", "btc")

    active_balance = 0.0
    seen_currencies = set()
    all_balances    = []

    for b in balances:
        amt = float(b["available"]["amount"])
        cur = b["available"]["currency"]
        if cur in seen_currencies:          # skip duplikat
            continue
        seen_currencies.add(cur)
        if amt > 0:
            all_balances.append((cur, amt))
        if cur == target:
            active_balance = amt

    return username, active_balance, all_balances


def get_balance_from_bet(bet_data: dict) -> float:
    """Ambil saldo currency aktif dari response bet."""
    target = BOT_CONFIG.get("currency", "btc")
    seen   = set()
    for b in bet_data["user"]["balances"]:
        cur = b["available"]["currency"]
        if cur in seen:
            continue
        seen.add(cur)
        if cur == target:
            return float(b["available"]["amount"])
    return 0.0


def send_bet(amount: float, rows: int, risk: str) -> dict:
    """
    Kirim taruhan Plinko ke Stake.
    Return dict: multiplier, payout, balance.
    """
    payload = {
        "query": PLINKO_BET_MUTATION,
        "variables": {
            "amount":   amount,
            "rows":     rows,
            "risk":     risk,
            "currency": BOT_CONFIG.get("currency", "btc"),
        },
    }
    r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
    if not r.ok:
        raise Exception(f"HTTP {r.status_code}: {r.text[:500]}")
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL Error: {data['errors']}")

    bet = data["data"]["plinkoBet"]
    return {
        "multiplier": float(bet["payoutMultiplier"]),
        "payout":     float(bet["payout"]),
        "balance":    get_balance_from_bet(bet),
    }


# ─────────────────────────────────────────────
# 4. LOGIKA UTAMA BOT
# ─────────────────────────────────────────────
def print_header(username: str, active_bal: float, all_balances: list):
    cur = BOT_CONFIG.get("currency", "btc").upper()
    print("=" * 55)
    print("   STAKE PLINKO WAGER BOT — AUTO-PILOT")
    print("=" * 55)
    print(f"  Username    : {username}")
    for c, a in all_balances:
        marker = " ← aktif" if c == BOT_CONFIG.get("currency", "btc") else ""
        print(f"  Saldo {c.upper():6s}: {a:.8f}{marker}")
    print("─" * 55)
    print(f"  Base Bet    : {BOT_CONFIG['baseBet']:,} {cur}")
    print(f"  Setelan     : {BOT_CONFIG['rows']} Rows | Risk {BOT_CONFIG['risk'].upper()}")
    if BOT_CONFIG.get("maxSpins"):
        print(f"  Max Spins   : {BOT_CONFIG['maxSpins']:,}")
    print(f"  Target Wager: {BOT_CONFIG['targetWager']:,}")
    print(f"  Stop Loss   : -{BOT_CONFIG['stopLoss']:,}")
    print(f"  Take Profit : +{BOT_CONFIG['takeProfit']:,}")
    print("=" * 55)


def stop_bot(reason: str):
    print("\n" + "=" * 55)
    print(f"  BOT BERHENTI: {reason}")
    print("=" * 55)
    print(f"  Total Spins : {stats['totalSpins']:,} kali")
    print(f"  Total Wager : {stats['totalWagered']:,.2f}")
    print(f"  Final Profit: {stats['currentProfit']:+,.2f}")
    print("=" * 55)


def execute_single_bet() -> bool:
    """Satu siklus taruhan. Return False jika bot harus berhenti."""
    cfg    = BOT_CONFIG
    result = send_bet(cfg["baseBet"], cfg["rows"], cfg["risk"])

    profit_loss = result["payout"] - cfg["baseBet"]
    stats["totalWagered"]  += cfg["baseBet"]
    stats["currentProfit"] += profit_loss
    stats["totalSpins"]    += 1

    sign = "+" if stats["currentProfit"] >= 0 else ""
    print(
        f"#{stats['totalSpins']:04d}"
        f"  x{result['multiplier']:.2f}"
        f"  Wager: {stats['totalWagered']:,.0f}"
        f"  Saldo: {result['balance']:,.2f}"
        f"  Profit: {sign}{stats['currentProfit']:,.2f}"
    )

    # Safety Checks
    if cfg.get("maxSpins") and stats["totalSpins"] >= cfg["maxSpins"]:
        stop_bot(f"MAX SPIN ({cfg['maxSpins']:,}) TERCAPAI!")
        return False
    if stats["totalWagered"] >= cfg["targetWager"]:
        stop_bot("TARGET WAGER TERCAPAI! Target dipenuhi dengan aman.")
        return False
    if stats["currentProfit"] <= -cfg["stopLoss"]:
        stop_bot("STOP LOSS TRIGGERED! Menyelamatkan modal inti.")
        return False
    if stats["currentProfit"] >= cfg["takeProfit"]:
        stop_bot("TAKE PROFIT TRIGGERED! Cuan berhasil diamankan.")
        return False

    return True


def start_bot():
    try:
        username, active_bal, all_balances = fetch_balances()
    except Exception as e:
        raise SystemExit(f"[ERROR] Gagal konek ke Stake: {e}")

    print_header(username, active_bal, all_balances)
    stats["initialBalance"] = active_bal

    print("  Bot berjalan... tekan Ctrl+C untuk hentikan manual.")
    print("=" * 55 + "\n")

    retry_delay = 2

    while True:
        try:
            if not execute_single_bet():
                break
            time.sleep(BOT_CONFIG["delayInterval"])

        except KeyboardInterrupt:
            stop_bot("DIHENTIKAN MANUAL oleh pengguna (Ctrl+C).")
            break

        except Exception as e:
            print(f"[ERROR] {e}")
            print(f"        Retry dalam {retry_delay} detik...")
            time.sleep(retry_delay)


# ─────────────────────────────────────────────
# 5. ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()
