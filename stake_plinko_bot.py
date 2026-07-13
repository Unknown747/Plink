"""
=================================================================
  STAKE PLINKO VIP WAGER BOT - AUTO-PILOT (Python Version)
  Setelan: Difficulty Low | Rows 15 | Base Bet 1000
=================================================================
  Cara pakai:
    1. Isi API_KEY dengan x-access-token dari akun Stake kamu
    2. Sesuaikan BOT_CONFIG sesuai kebutuhan
    3. Jalankan: python stake_plinko_bot.py
=================================================================
"""

import time
import requests

# ─────────────────────────────────────────────
# 0. KONFIGURASI API
# ─────────────────────────────────────────────
API_KEY  = "ISI_API_KEY_KAMU_DI_SINI"          # x-access-token dari Stake
API_URL  = "https://stake.com/_api/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "x-access-token": API_KEY,
    "Connection":     "keep-alive",
}

# ─────────────────────────────────────────────
# 1. KONFIGURASI PARAMETER BOT
# ─────────────────────────────────────────────
BOT_CONFIG = {
    "baseBet":      1000,        # Taruhan dasar (satuan sesuai akun, misal: 1000 = Rp1.000)
    "rows":         15,          # Jumlah baris Plinko (8 / 12 / 15 / 16)
    "risk":         "low",       # Tingkat risiko: "low" | "medium" | "high"
    "delayInterval": 0.4,        # Jeda antar spin (detik) — aman dari rate-limit

    # Manajemen Risiko & Target
    "targetWager":  10_000_000,  # Bot pause jika total wager mencapai nilai ini
    "stopLoss":      5_000,      # Bot pause jika profit < -stopLoss (Badai Merah)
    "takeProfit":   20_000,      # Bot pause jika profit >= takeProfit (Cuan Kebablasan)
}

# ─────────────────────────────────────────────
# 2. STATE / PENCATAT DATA INTERNAL
# ─────────────────────────────────────────────
stats = {
    "totalWagered":  0.0,
    "currentProfit": 0.0,
    "totalSpins":    0,
    "initialBalance": 0.0,
}

# ─────────────────────────────────────────────
# 3. GRAPHQL QUERIES
# ─────────────────────────────────────────────
PLINKO_BET_MUTATION = """
mutation Plinkobet($amount: Float!, $rows: Int!, $risk: CasinoGamePlinkoRisk!) {
  plinko_bet(amount: $amount, rows: $rows, risk: $risk) {
    id
    active
    payoutMultiplier
    amountMultiplier
    amount
    payout
    updatedAt
    currency
    game {
      name
    }
    user {
      id
      name
      balances {
        available {
          amount
          currency
        }
      }
    }
  }
}
"""

BALANCE_QUERY = """
query UserBalance {
  user {
    balances {
      available {
        amount
        currency
      }
    }
  }
}
"""

# ─────────────────────────────────────────────
# 4. FUNGSI API
# ─────────────────────────────────────────────
def get_current_balance() -> float:
    """Ambil saldo akun saat ini dari Stake API."""
    payload = {"query": BALANCE_QUERY}
    try:
        r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        balances = data["data"]["user"]["balances"]
        # Ambil saldo pertama yang tersedia
        return float(balances[0]["available"]["amount"])
    except Exception as e:
        print(f"[PERINGATAN] Gagal ambil saldo: {e}")
        return 0.0


def send_bet(amount: float, rows: int, risk: str) -> dict:
    """
    Kirim taruhan Plinko ke Stake.
    Return dict berisi multiplier, payout, dan saldo terbaru.
    Raise Exception jika ada error API.
    """
    payload = {
        "query": PLINKO_BET_MUTATION,
        "variables": {
            "amount": amount,
            "rows":   rows,
            "risk":   risk,
        },
    }
    r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=10)
    r.raise_for_status()
    data = r.json()

    if "errors" in data:
        raise Exception(f"API Error: {data['errors']}")

    bet_data = data["data"]["plinko_bet"]
    return {
        "multiplier": float(bet_data["payoutMultiplier"]),
        "payout":     float(bet_data["payout"]),
        "balance":    float(
            bet_data["user"]["balances"][0]["available"]["amount"]
        ),
    }

# ─────────────────────────────────────────────
# 5. LOGIKA UTAMA BOT
# ─────────────────────────────────────────────
def print_header():
    print("=" * 50)
    print("   STAKE PLINKO WAGER BOT — AUTO-PILOT")
    print("=" * 50)
    print(f"  Base Bet    : {BOT_CONFIG['baseBet']:,}")
    print(f"  Setelan     : {BOT_CONFIG['rows']} Rows | Risk {BOT_CONFIG['risk'].upper()}")
    print(f"  Target Wager: {BOT_CONFIG['targetWager']:,}")
    print(f"  Stop Loss   : -{BOT_CONFIG['stopLoss']:,}")
    print(f"  Take Profit : +{BOT_CONFIG['takeProfit']:,}")
    print("=" * 50)


def stop_bot(reason: str):
    print("\n" + "=" * 50)
    print(f"  BOT BERHENTI: {reason}")
    print("=" * 50)
    print(f"  Total Spins : {stats['totalSpins']:,} kali")
    print(f"  Total Wager : {stats['totalWagered']:,.2f}")
    print(f"  Final Profit: {stats['currentProfit']:+,.2f}")
    print("=" * 50)


def execute_single_bet():
    """Satu siklus taruhan — kirim bet, update statistik, cek safety."""
    cfg = BOT_CONFIG

    result = send_bet(cfg["baseBet"], cfg["rows"], cfg["risk"])

    payout     = result["payout"]
    profit_loss = payout - cfg["baseBet"]

    stats["totalWagered"]  += cfg["baseBet"]
    stats["currentProfit"] += profit_loss
    stats["totalSpins"]    += 1

    print(
        f"[Spin #{stats['totalSpins']:>5}] "
        f"Multiplier: {result['multiplier']:.2f}x | "
        f"Wager: {stats['totalWagered']:>12,.0f} | "
        f"Saldo: {result['balance']:>12,.2f} | "
        f"Profit: {stats['currentProfit']:>+12,.2f}"
    )

    # ── Safety Checks ──────────────────────────────
    if stats["totalWagered"] >= cfg["targetWager"]:
        stop_bot("TARGET WAGER TERCAPAI! Target dipenuhi dengan aman.")
        return False

    if stats["currentProfit"] <= -cfg["stopLoss"]:
        stop_bot("STOP LOSS TRIGGERED! Menyelamatkan modal inti.")
        return False

    if stats["currentProfit"] >= cfg["takeProfit"]:
        stop_bot("TAKE PROFIT TRIGGERED! Cuan berhasil diamankan.")
        return False

    return True  # lanjut spin berikutnya


def start_bot():
    print_header()

    stats["initialBalance"] = get_current_balance()
    print(f"  Saldo Awal  : {stats['initialBalance']:,.2f}")
    print("=" * 50)
    print("  Bot berjalan... tekan Ctrl+C untuk hentikan manual.")
    print("=" * 50 + "\n")

    retry_delay = 2  # detik retry saat error jaringan

    while True:
        try:
            should_continue = execute_single_bet()
            if not should_continue:
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
# 6. ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()
