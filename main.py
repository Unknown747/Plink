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
import logging
import os
import time
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv

# ─────────────────────────────────────────────
# 0. LOAD ENV
# ─────────────────────────────────────────────
load_dotenv()

API_KEY = os.environ.get("STAKE_API_KEY", "")
if not API_KEY:
    raise SystemExit("[ERROR] STAKE_API_KEY belum diisi di Replit Secrets.")

API_URL = "https://stake.com/_api/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "x-access-token": API_KEY,
    "Connection":     "keep-alive",
}

# ─────────────────────────────────────────────
# 1. LOGGER (Console + File dengan rotasi)
#    Maks 3 file × 500 KB = 1.5 MB total
# ─────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)

_logger = logging.getLogger("plinko_bot")
_logger.setLevel(logging.INFO)

_fh = RotatingFileHandler(
    "logs/bot.log",
    maxBytes=500_000,   # 500 KB per file
    backupCount=3,       # simpan 3 file lama → maks 1.5 MB total
    encoding="utf-8",
)
_fh.setFormatter(logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
_logger.addHandler(_fh)


def log(msg: str):
    """Cetak ke console sekaligus tulis ke log file."""
    print(msg, flush=True)
    _logger.info(msg)


# ─────────────────────────────────────────────
# 2. CONFIG (reload setiap sesi)
# ─────────────────────────────────────────────
def load_config() -> dict:
    with open("config.json", "r") as f:
        return json.load(f)

BOT_CONFIG = load_config()   # load awal

# ─────────────────────────────────────────────
# 2b. TIMER GLOBAL (mulai saat bot pertama kali jalan)
# ─────────────────────────────────────────────
BOT_START_TIME: float = 0.0

def elapsed_str() -> str:
    """Kembalikan waktu berjalan dalam format HH:MM:SS."""
    s = int(time.time() - BOT_START_TIME)
    return f"{s//3600:02d}:{(s%3600)//60:02d}:{s%60:02d}"

# ─────────────────────────────────────────────
# 3. STATE / PENCATAT DATA INTERNAL
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
# 4. GRAPHQL QUERIES
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
# 5. FUNGSI API
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
# 6. HELPER DISPLAY
# ─────────────────────────────────────────────
def fmt_duration(seconds: int) -> str:
    if seconds >= 3600:
        return f"{seconds // 3600} jam"
    if seconds >= 60:
        return f"{seconds // 60} menit"
    return f"{seconds} detik"


def print_header(username: str, all_balances: list, session_num: int):
    cur = BOT_CONFIG.get("currency", "btc").upper()
    log("\n" + "=" * 55)
    log(f"   STAKE PLINKO WAGER BOT — SESI #{session_num}")
    log("=" * 55)
    log(f"  Username    : {username}")
    for c, a in all_balances:
        marker = " ← aktif" if c == BOT_CONFIG.get("currency", "btc") else ""
        log(f"  Saldo {c.upper():6s}: {a:.8f}{marker}")
    log("─" * 55)
    log(f"  Base Bet    : {BOT_CONFIG['baseBet']:,} {cur}")
    log(f"  Setelan     : {BOT_CONFIG['rows']} Rows | Risk {BOT_CONFIG['risk'].upper()}")
    if BOT_CONFIG.get("maxSpins"):
        log(f"  Max Spins   : {BOT_CONFIG['maxSpins']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnMaxSpins', 0))}")
    log(f"  Target Wager: {BOT_CONFIG['targetWager']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnTargetWager', 0))}")
    log(f"  Stop Loss   : -{BOT_CONFIG['stopLoss']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnStopLoss', 0))}")
    log(f"  Take Profit : +{BOT_CONFIG['takeProfit']:,}  → pause {fmt_duration(BOT_CONFIG.get('pauseOnTakeProfit', 0))}")
    log(f"  Delay       : {BOT_CONFIG['delayInterval']}s  |  Retry: {BOT_CONFIG.get('retryDelay', 2)}s  |  Max Retry: {BOT_CONFIG.get('maxRetries', 5)}x")
    log("=" * 55)


def pause_bot(reason: str, pause_seconds: int):
    log("\n" + "=" * 55)
    log(f"  ⏸  BOT PAUSE: {reason}")
    log("=" * 55)
    log(f"  Total Spins : {stats['totalSpins']:,} kali")
    log(f"  Total Wager : {stats['totalWagered']:,.2f}")
    log(f"  Profit Sesi : {stats['currentProfit']:+,.2f}")
    log(f"  Istirahat   : {fmt_duration(pause_seconds)}")
    log("=" * 55)

    if pause_seconds <= 0:
        return

    # Tidur dalam satu blok — tidak spam log selama pause
    # Hanya cetak pengingat setiap 30 menit untuk pause panjang (agar VPS
    # terasa "hidup" di console tanpa membengkakkan log file)
    remind_interval = 1800 if pause_seconds >= 1800 else pause_seconds
    elapsed = 0
    while elapsed < pause_seconds:
        sisa       = pause_seconds - elapsed
        sleep_time = min(remind_interval, sisa)
        time.sleep(sleep_time)
        elapsed += sleep_time
        if elapsed < pause_seconds:
            log(f"  ⏳ Lanjut dalam {fmt_duration(pause_seconds - elapsed)}...")

    log("  ▶  Pause selesai, memulai sesi baru...\n")

# ─────────────────────────────────────────────
# 7. LOGIKA UTAMA BOT
# ─────────────────────────────────────────────
def execute_single_bet() -> tuple:
    """
    Satu siklus taruhan.
    Return: (lanjut: bool, pause_detik: int, alasan: str)
    """
    cfg    = BOT_CONFIG
    result = send_bet(cfg["baseBet"], cfg["rows"], cfg["risk"])

    profit_loss = result["payout"] - cfg["baseBet"]
    stats["totalWagered"]  += cfg["baseBet"]
    stats["currentProfit"] += profit_loss
    stats["totalSpins"]    += 1

    sign = "+" if stats["currentProfit"] >= 0 else ""
    log(
        f"#{stats['totalSpins']:04d}"
        f" | x{result['multiplier']:.2f}"
        f" | Wager: {stats['totalWagered']:,.0f}"
        f" | Saldo: {result['balance']:,.2f}"
        f" | Profit: {sign}{stats['currentProfit']:,.2f}"
        f" | {elapsed_str()}"
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
    global stats, BOT_CONFIG

    # ── Reload config setiap awal sesi ──
    try:
        BOT_CONFIG = load_config()
    except Exception as e:
        log(f"[WARN] Gagal reload config, pakai config lama: {e}")

    stats = fresh_stats()
    print_header(username, all_balances, session_num)

    # Ambil saldo aktif dari data yang sudah di-fetch — tidak perlu API call lagi
    target = BOT_CONFIG.get("currency", "btc")
    stats["initialBalance"] = next((a for c, a in all_balances if c == target), 0.0)

    log("  Bot berjalan... tekan Ctrl+C untuk hentikan manual.\n")

    retry_base  = BOT_CONFIG.get("retryDelay", 2)
    max_retries = BOT_CONFIG.get("maxRetries", 5)
    retry_count = 0   # counter error berturut-turut

    while True:
        try:
            lanjut, pause_detik, alasan = execute_single_bet()
            retry_count = 0   # reset setelah bet berhasil
            if not lanjut:
                return pause_detik, alasan
            time.sleep(BOT_CONFIG["delayInterval"])

        except Exception as e:
            err = str(e)

            # Saldo habis → stop langsung
            if "insufficientBalance" in err:
                return 0, "SALDO HABIS! Top up dulu lalu restart bot"

            retry_count += 1

            # Melebihi batas retry → stop sesi
            if retry_count >= max_retries:
                return 0, f"KONEKSI GAGAL {max_retries}x BERTURUT-TURUT — periksa jaringan/VPS"

            # Exponential backoff: 2s → 4s → 8s → 16s … capped 60s
            backoff = min(retry_base * (2 ** (retry_count - 1)), 60)
            log(f"[ERROR] {e}")
            log(f"        Retry {retry_count}/{max_retries} dalam {backoff:.0f} detik...")
            time.sleep(backoff)


def start_bot():
    global BOT_START_TIME
    BOT_START_TIME = time.time()

    try:
        username, _, all_balances = fetch_balances()
    except Exception as e:
        raise SystemExit(f"[ERROR] Gagal konek ke Stake: {e}")

    session_num = 1

    while True:
        try:
            pause_detik, alasan = run_session(session_num, username, all_balances)

            # Kondisi stop total
            if "SALDO HABIS" in alasan or "KONEKSI GAGAL" in alasan:
                log("\n" + "=" * 55)
                log(f"  🛑 BOT BERHENTI: {alasan}")
                log("=" * 55)
                break

            pause_bot(alasan, pause_detik)

            # Refresh saldo & username sebelum sesi baru
            try:
                username, _, all_balances = fetch_balances()
            except Exception:
                pass

            session_num += 1

        except KeyboardInterrupt:
            log("\n" + "=" * 55)
            log("  🛑 BOT DIHENTIKAN MANUAL (Ctrl+C)")
            log(f"  Total Sesi  : {session_num}")
            log(f"  Total Spins : {stats['totalSpins']:,} kali")
            log(f"  Total Wager : {stats['totalWagered']:,.2f}")
            log(f"  Profit Sesi : {stats['currentProfit']:+,.2f}")
            log("=" * 55)
            break

# ─────────────────────────────────────────────
# 8. ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    start_bot()
