"""
=================================================================
  STAKE PLINKO BOT — SIMULASI TEST (Saldo Palsu)
  Saldo Awal : Rp 200.000  |  Base Bet: Rp 1.000
  Mode       : Offline — tanpa koneksi ke Stake
  RTP Simulasi ≈ 99% (sesuai house edge Stake ~1%)
=================================================================
  Jalankan: python test_bot.py
=================================================================
"""

import random
import statistics
from math import comb

# ─────────────────────────────────────────────
# KONFIGURASI SIMULASI
# ─────────────────────────────────────────────
SIM_CONFIG = {
    "startBalance":  200_000,
    "baseBet":         1_000,
    "rows":               15,
    "risk":            "low",
    "stopLoss":      100_000,   # Rp 100.000 (50% modal)
    "takeProfit":    100_000,   # Rp 100.000
    "maxSpins":        5_000,   # Batas spin per sesi
    "jumlahTest":         10,   # Jumlah sesi yang diulang
    "printInterval":     500,   # Cetak log tiap N spin
}

# ─────────────────────────────────────────────
# TABEL MULTIPLIER PLINKO — Low Risk | 15 Rows
# 16 bucket (k=0..15), RTP ≈ 99.03%
# (dihitung ulang dari distribusi binomial B(15,0.5))
# ─────────────────────────────────────────────
MULTIPLIERS = [
    16.0,   # k=0  — paling kiri (langka, ~0.003%)
     9.0,   # k=1
     3.0,   # k=2
     1.4,   # k=3
     1.1,   # k=4
     1.0,   # k=5
     0.9,   # k=6
     0.95,  # k=7  — tengah kiri
     0.95,  # k=8  — tengah kanan
     0.9,   # k=9
     1.0,   # k=10
     1.1,   # k=11
     1.4,   # k=12
     3.0,   # k=13
     9.0,   # k=14
    16.0,   # k=15 — paling kanan (langka, ~0.003%)
]

# Probabilitas binomial B(15, 0.5) → 16 bucket
TOTAL = 2 ** 15   # 32768
PROBS = [comb(15, k) / TOTAL for k in range(16)]

# Verifikasi RTP teori
_rtp_theory = sum(p * m for p, m in zip(PROBS, MULTIPLIERS))

# ─────────────────────────────────────────────
# FUNGSI SIMULASI
# ─────────────────────────────────────────────
def spin_plinko() -> float:
    return random.choices(MULTIPLIERS, weights=PROBS, k=1)[0]


def fmt_rp(val: float, sign: bool = False) -> str:
    prefix = "+" if (sign and val >= 0) else ""
    return f"Rp {prefix}{val:>12,.2f}"


def run_session(session_num: int) -> dict:
    cfg      = SIM_CONFIG
    balance  = cfg["startBalance"]
    bet      = cfg["baseBet"]

    total_wager  = 0.0
    total_profit = 0.0
    spins        = 0
    wins         = 0            # spin dengan payout >= bet
    best_multi   = 0.0
    biggest_win  = 0.0
    biggest_loss = 0.0
    stop_reason  = f"MAX SPIN ({cfg['maxSpins']:,})"
    balance_history = [balance]

    print(f"\n{'━'*62}")
    print(f"  SESI #{session_num:02d}  |  Saldo Awal: Rp {balance:,.0f}")
    print(f"{'━'*62}")
    print(f"  {'Spin':>5}  {'Multi':>6}  {'Wager':>11}  {'Saldo':>12}  {'Profit':>12}")
    print(f"  {'─'*5}  {'─'*6}  {'─'*11}  {'─'*12}  {'─'*12}")

    for _ in range(cfg["maxSpins"]):
        if balance < bet:
            stop_reason = "SALDO HABIS"
            break

        multi        = spin_plinko()
        payout       = bet * multi
        profit_spin  = payout - bet

        balance      += profit_spin
        total_wager  += bet
        total_profit += profit_spin
        spins        += 1

        if payout >= bet:
            wins += 1
        if multi > best_multi:
            best_multi = multi
        if profit_spin > biggest_win:
            biggest_win = profit_spin
        if profit_spin < biggest_loss:
            biggest_loss = profit_spin

        balance_history.append(balance)

        # Cetak tiap N spin dan 5 spin pertama
        if spins <= 5 or spins % cfg["printInterval"] == 0:
            sign = "+" if total_profit >= 0 else ""
            print(
                f"  #{spins:>5}"
                f"  x{multi:.2f} "
                f"  Rp {total_wager:>8,.0f}"
                f"  Rp {balance:>10,.2f}"
                f"  Rp {sign}{total_profit:>9,.2f}"
            )

        # Safety checks
        if total_profit <= -cfg["stopLoss"]:
            stop_reason = "⛔ STOP LOSS"
            break
        if total_profit >= cfg["takeProfit"]:
            stop_reason = "✅ TAKE PROFIT"
            break

    win_rate   = (wins / spins * 100) if spins else 0
    rtp_actual = ((total_wager + total_profit) / total_wager * 100) if total_wager else 0

    return {
        "sesi":          session_num,
        "spins":         spins,
        "stop_reason":   stop_reason,
        "total_wager":   total_wager,
        "total_profit":  total_profit,
        "final_balance": balance,
        "win_rate":      win_rate,
        "rtp_actual":    rtp_actual,
        "best_multi":    best_multi,
        "biggest_win":   biggest_win,
        "biggest_loss":  biggest_loss,
        "max_balance":   max(balance_history),
        "min_balance":   min(balance_history),
    }


def print_session_summary(r: dict):
    label = "✅ UNTUNG" if r["total_profit"] >= 0 else "❌ RUGI"
    sign  = "+" if r["total_profit"] >= 0 else ""
    print(f"\n  ┌─ HASIL SESI #{r['sesi']:02d}  [{label}]  Berhenti: {r['stop_reason']}")
    print(f"  │  Spin       : {r['spins']:>6,} kali   |  Wager Total: Rp {r['total_wager']:>12,.0f}")
    print(f"  │  Win Rate   : {r['win_rate']:>5.1f}%        |  RTP Aktual : {r['rtp_actual']:>6.2f}%")
    print(f"  │  Best Multi : x{r['best_multi']:.2f}         |  Biggest Win: Rp {r['biggest_win']:>8,.0f}")
    print(f"  │  Saldo Max  : Rp {r['max_balance']:>10,.2f}  |  Saldo Min  : Rp {r['min_balance']:>10,.2f}")
    print(f"  └─ Final Bal  : Rp {r['final_balance']:>10,.2f}  |  Profit: Rp {sign}{r['total_profit']:>10,.2f}")


def print_grand_summary(results: list):
    profits    = [r["total_profit"]  for r in results]
    wagers     = [r["total_wager"]   for r in results]
    win_rates  = [r["win_rate"]      for r in results]
    rtps       = [r["rtp_actual"]    for r in results]
    spins_list = [r["spins"]         for r in results]
    untung     = sum(1 for p in profits if p >= 0)

    print(f"\n{'═'*62}")
    print(f"  RINGKASAN KESELURUHAN — {len(results)} SESI TEST")
    print(f"{'═'*62}")
    print(f"  Total Spin       : {sum(spins_list):>8,} spin")
    print(f"  Rata² per Sesi   : {statistics.mean(spins_list):>8,.0f} spin")
    print(f"  Total Wager      : Rp {sum(wagers):>12,.0f}")
    print(f"{'─'*62}")
    print(f"  Sesi Untung      : {untung}/{len(results)} ({untung/len(results)*100:.0f}%)")
    print(f"  Profit Terbaik   : Rp {max(profits):>+12,.2f}")
    print(f"  Profit Terburuk  : Rp {min(profits):>+12,.2f}")
    print(f"  Profit Rata²     : Rp {statistics.mean(profits):>+12,.2f}")
    if len(profits) > 1:
        print(f"  Std Dev Profit   : Rp {statistics.stdev(profits):>12,.2f}")
    print(f"{'─'*62}")
    print(f"  Win Rate Rata²   : {statistics.mean(win_rates):>6.1f}%")
    print(f"  RTP Teori        : {_rtp_theory*100:>6.2f}%")
    print(f"  RTP Aktual Rata² : {statistics.mean(rtps):>6.2f}%  (house edge ~{100-statistics.mean(rtps):.2f}%)")
    print(f"{'═'*62}")

    # Tabel per sesi
    print(f"\n  {'Sesi':>5}  {'Spin':>6}  {'Wager':>12}  {'Profit':>12}  {'Stop Reason'}")
    print(f"  {'─'*5}  {'─'*6}  {'─'*12}  {'─'*12}  {'─'*18}")
    for r in results:
        sign = "+" if r["total_profit"] >= 0 else ""
        print(
            f"  #{r['sesi']:>4}  "
            f"{r['spins']:>6,}  "
            f"Rp {r['total_wager']:>9,.0f}  "
            f"Rp {sign}{r['total_profit']:>9,.0f}  "
            f"{r['stop_reason']}"
        )
    print(f"\n  Catatan: Simulasi menggunakan RTP teori {_rtp_theory*100:.2f}%")
    print(f"           Hasil nyata di Stake dapat berbeda tergantung variance.\n")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("═" * 62)
    print("  STAKE PLINKO — SIMULASI OFFLINE")
    print("═" * 62)
    print(f"  Modal Awal    : Rp {SIM_CONFIG['startBalance']:,}")
    print(f"  Base Bet      : Rp {SIM_CONFIG['baseBet']:,}")
    print(f"  Risk / Rows   : {SIM_CONFIG['risk'].upper()} / {SIM_CONFIG['rows']} Rows")
    print(f"  Stop Loss     : Rp {SIM_CONFIG['stopLoss']:,}")
    print(f"  Take Profit   : Rp {SIM_CONFIG['takeProfit']:,}")
    print(f"  Max Spin/Sesi : {SIM_CONFIG['maxSpins']:,}")
    print(f"  Jumlah Sesi   : {SIM_CONFIG['jumlahTest']}")
    print(f"  RTP Teori     : {_rtp_theory*100:.2f}%  (house edge {(1-_rtp_theory)*100:.2f}%)")
    print("═" * 62)

    all_results = []
    for i in range(1, SIM_CONFIG["jumlahTest"] + 1):
        result = run_session(i)
        print_session_summary(result)
        all_results.append(result)

    print_grand_summary(all_results)
