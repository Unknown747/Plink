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
    raise SystemExit("[ERROR] STAKE_API_KEY belum diisi di Replit Secrets.")

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
def fresh_stats():
    return {
        "totalWagered":   0.0,
        "currentProfit":  0.0,
        "totalSpins":     0,
        "initialBalance": 0.0,
    }

stats = fresh_stats()

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
def fetch_balances() -> tuple:
    """Return (username, saldo_aktif, [(currency, amount), ...])"""
    r = requests.post(API_URL, json={"query": BALANCE_QUERY}, headers=HEADERS, timeout=10)
    if not r.ok:
        raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    if "errors" in data:
        raise Exception(f"GraphQL: {data['errors']}")

    user     = data["data"]["user"]
    username = user["name"]
    target   = BOT_CONFIG.get("currency", "btc")

    active_balance  = 0.0
    seen_currencies = set()
    all_balances    = []

    for b in user["balances"]:
        amt = float(b["available"]["amount"])
        cur = b["available"]["currency"]
        if cur in seen_currencies:
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
    """Kirim taruhan Plinko ke Stake. Return dict: multiplier, payout, balance."""
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
# 4. HELPER DISPLAY
# ─────────────────────────────────────────────
def fmt_duration(seconds: int) -> str:
    """Konversi detik ke format jam/menit/detik yang mudah dibaca."""
    if seconds >= 3600:
        return f"{seconds // 3600} jam"
    if seconds >= 60:
        return f"{seconds // 60} menit"
    return f"{seconds} detik"


def print_header(username: str, all_balances: list, session_num: int):
    cur = BOT_CONFIG.get("currency", "btc").upper()
    print("\n" + "=" * 55)
    print(f"   STAKE PLINKO WAGER BOT — SESI #{session_num}")
    print("=" * 55)
    print(f"  Username    : {username}")
    for c, a in all_balances:
        marker = " ← aktif" if c == BOT_CONFIG.get("currency", "btc") else ""
        print(f"  Saldo {c.upper():6s}: {a:.8f}{marker}")
    print("─" * 55)
    print(f"  Base Bet    : {BOT_CONFIG['baseBet']:,} {cur}")
    print(f"  Setelan     : {BOT_CONFIG['rows']} Rows | Risk {BOT_CONFIG['risk'].upper()}")
    if BOT_CONFIG.get("maxSpins"):
        print(f"  Max Spins   : {BOT_CONFIG['maxSpins']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnMaxSpins', 0))}")
    print(f"  Target Wager: {BOT_CONFIG['targetWager']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnTargetWager', 0))}")
    print(f"  Stop Loss   : -{BOT_CONFIG['stopLoss']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnStopLoss', 0))}")
    print(f"  Take Profit : +{BOT_CONFIG['takeProfit']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnTakeProfit', 0))}")
    print(f"  Delay       : {BOT_CONFIG['delayInterval']}s  |  Retry: {BOT_CONFIG.get('retryDelay', 2)}s")
    print("=" * 55)


def pause_bot(reason: str, pause_seconds: int):
    """Tampilkan summary sesi dan mulai countdown pause."""
    print("\n" + "=" * 55)
    print(f"  ⏸  BOT PAUSE: {reason}")
    print("=" * 55)
    print(f"  Total Spins : {stats['totalSpins']:,} kali")
    print(f"  Total Wager : {stats['totalWagered']:,.2f}")
    print(f"  Profit Sesi : {stats['currentProfit']:+,.2f}")
    print(f"  Istirahat   : {fmt_duration(pause_seconds)}")
    print("=" * 55)

    if pause_seconds <= 0:
        return

    interval = 60 if pause_seconds >= 120 else 10
    elapsed  = 0
    while elapsed < pause_seconds:
        sisa = pause_seconds - elapsed
        print(f"  ⏳ Lanjut dalam {fmt_duration(sisa)}...", flush=True)
        sleep_time = min(interval, sisa)
        time.sleep(sleep_time)
        elapsed += sleep_time

    print("  ▶  Pause selesai, memulai sesi baru...\n")

# ─────────────────────────────────────────────
# 5. LOGIKA UTAMA BOT
# ─────────────────────────────────────────────
def execute_single_bet() -> tuple:
    """
    Satu siklus taruhan.
    Return: (lanjut: bool, pause_detik: int)
    """
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

    # ── Safety Checks ──────────────────────────────
    if cfg.get("maxSpins") and stats["totalSpins"] >= cfg["maxSpins"]:
        return False, cfg.get("pauseOnMaxSpins", 0), "MAX SPIN tercapai, istirahat sebentar"

    if stats["totalWagered"] >= cfg["targetWager"]:
        return False, cfg.get("pauseOnTargetWager", 0), "TARGET WAGER TERCAPAI! Target dipenuhi dengan aman"

    if stats["currentProfit"] <= -cfg["stopLoss"]:
        return False, cfg.get("pauseOnStopLoss", 0), "STOP LOSS — Menyelamatkan modal inti"

    if stats["currentProfit"] >= cfg["takeProfit"]:
        return False, cfg.get("pauseOnTakeProfit", 0), "TAKE PROFIT — Cuan berhasil diamankan"

    return True, 0, ""


def run_session(session_num: int, username: str, all_balances: list):
    """Jalankan satu sesi penuh. Return (pause_detik, alasan)."""
    global stats
    stats = fresh_stats()

    print_header(username, all_balances, session_num)

    _, active_bal, _ = fetch_balances()
    stats["initialBalance"] = active_bal

    print("  Bot berjalan... tekan Ctrl+C untuk hentikan manual.\n")

    retry_delay = BOT_CONFIG.get("retryDelay", 2)

    while True:
        try:
            lanjut, pause_detik, alasan = execute_single_bet()
            if not lanjut:
                return pause_detik, alasan
            time.sleep(BOT_CONFIG["delayInterval"])

        except Exception as e:
            err = str(e)
            if "insufficientBalance" in err:
                return 0, "SALDO HABIS! Top up dulu lalu restart bot"
            print(f"[ERROR] {e}")
            print(f"        Retry dalam {retry_delay} detik...")
            time.sleep(retry_delay)


def start_bot():
    try:
        username, _, all_balances = fetch_balances()
    except Exception as e:
        raise SystemExit(f"[ERROR] Gagal konek ke Stake: {e}")

    session_num = 1

    while True:
        try:
            pause_detik, alasan = run_session(session_num, username, all_balances)

            if "SALDO HABIS" in alasan:
                # Stop total — tidak ada gunanya pause kalau saldo habis
                print("\n" + "=" * 55)
                print(f"  🛑 BOT BERHENTI: {alasan}")
                print("=" * 55)
                break

            pause_bot(alasan, pause_detik)

            # Refresh saldo setelah pause sebelum sesi baru
            try:
                username, _, all_balances = fetch_balances()
            except Exception:
                pass

            session_num += 1

        except KeyboardInterrupt:
            print("\n" + "=" * 55)
            print("  🛑 BOT DIHENTIKAN MANUAL (Ctrl+C)")
            print(f"  Total Sesi  : {session_num}")
            print(f"  Total Spins : {stats['totalSpins']:,} kali")
            print(f"  Total Wager : {stats['totalWagered']:,.2f}")
            print(f"  Profit Sesi : {stats['currentProfit']:+,.2f}")
            print("=" * 55)
            break

# ─────────────────────────────────────────────
# 6. ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()
