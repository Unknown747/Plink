"""
=================================================================
  STAKE PLINKO VIP WAGER BOT - AUTO-PILOT (Python Version)
  Konfigurasi : config.json
  API Token   : .env  (STAKE_API_KEY)
=================================================================
  Cara pakai:
    1. cp .env.example .env  → isi STAKE_API_KEY
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
        "[ERROR] STAKE_API_KEY belum diisi.\n"
        "Salin .env.example → .env lalu isi token kamu."
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
    active
    payoutMultiplier
    amountMultiplier
    amount
    payout
    updatedAt
    currency
    game
    user {
      id
      name
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
def get_all_balances() -> list:
    """Ambil semua saldo dari semua currency."""
    try:
        r = requests.post(API_URL, json={"query": BALANCE_QUERY}, headers=HEADERS, timeout=10)
        if not r.ok:
            print(f"[PERINGATAN] Gagal ambil saldo HTTP {r.status_code}: {r.text[:300]}")
            return []
        data = r.json()
        if "errors" in data:
            print(f"[PERINGATAN] GraphQL error saldo: {data['errors']}")
            return []
        user = data["data"]["user"]
        print(f"  Username    : {user['name']}")
        balances = user["balances"]
        # Tampilkan semua saldo yang ada isinya
        has_funds = []
        for b in balances:
            amt = float(b["available"]["amount"])
            cur = b["available"]["currency"]
            if amt > 0:
                print(f"  Saldo {cur.upper():6s}: {amt:.8f}")
                has_funds.append(b["available"])
        if not has_funds:
            print("  [!] Semua saldo kosong. Pastikan currency di config.json sesuai.")
        return has_funds
    except Exception as e:
        print(f"[PERINGATAN] Gagal ambil saldo: {e}")
        return []


def get_current_balance() -> float:
    """Ambil saldo untuk currency yang dikonfigurasi."""
    target_currency = BOT_CONFIG.get("currency", "btc")
    try:
        r = requests.post(API_URL, json={"query": BALANCE_QUERY}, headers=HEADERS, timeout=10)
        if not r.ok:
            print(f"[PERINGATAN] Gagal ambil saldo HTTP {r.status_code}: {r.text[:300]}")
            return 0.0
        data = r.json()
        if "errors" in data:
            print(f"[PERINGATAN] GraphQL error saldo: {data['errors']}")
            return 0.0
        balances = data["data"]["user"]["balances"]
        for b in balances:
            if b["available"]["currency"] == target_currency:
                return float(b["available"]["amount"])
        return 0.0
    except Exception as e:
        print(f"[PERINGATAN] Gagal ambil saldo: {e}")
        return 0.0


def send_bet(amount: float, rows: int, risk: str) -> dict:
    """
    Kirim taruhan Plinko ke Stake.
    Return dict: multiplier, payout, balance.
    Raise Exception jika ada error API.
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
        "balance":    float(bet["user"]["balances"][0]["available"]["amount"]),
    }

# ─────────────────────────────────────────────
# 4. LOGIKA UTAMA BOT
# ─────────────────────────────────────────────
def print_header():
    print("=" * 55)
    print("   STAKE PLINKO WAGER BOT — AUTO-PILOT")
    print("=" * 55)
    print(f"  Base Bet    : {BOT_CONFIG['baseBet']:,}")
    print(f"  Setelan     : {BOT_CONFIG['rows']} Rows | Risk {BOT_CONFIG['risk'].upper()}")
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
    cfg = BOT_CONFIG
    result = send_bet(cfg["baseBet"], cfg["rows"], cfg["risk"])

    profit_loss = result["payout"] - cfg["baseBet"]
    stats["totalWagered"]  += cfg["baseBet"]
    stats["currentProfit"] += profit_loss
    stats["totalSpins"]    += 1

    profit_sign = "+" if stats["currentProfit"] >= 0 else ""
    print(
        f"#{stats['totalSpins']:04d}"
        f"  x{result['multiplier']:.2f}"
        f"  Wager: {stats['totalWagered']:,.0f}"
        f"  Saldo: {result['balance']:,.2f}"
        f"  Profit: {profit_sign}{stats['currentProfit']:,.2f}"
    )

    # Safety Checks
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
    print_header()

    get_all_balances()
    stats["initialBalance"] = get_current_balance()
    print(f"  Saldo {BOT_CONFIG.get('currency','btc').upper():6s}: {stats['initialBalance']:.8f}")
    print("=" * 55)
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
            print(f"[ERROR] Koneksi Error/Lag: {e}")
            print(f"        Mencoba ulang dalam {retry_delay} detik...")
            time.sleep(retry_delay)


# ─────────────────────────────────────────────
# 5. ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()
