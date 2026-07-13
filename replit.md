# Stake Plinko VIP Wager Bot

Bot otomatis untuk bermain Plinko di Stake.com menggunakan GraphQL API resmi.

## Stack
- **Python 3** + `requests`

## Cara Menjalankan
```bash
# 1. Siapkan file .env
cp .env.example .env
# Isi STAKE_API_KEY di dalam .env

# 2. Jalankan bot
python main.py
```

## Konfigurasi

### API Token — `.env`
| Variable        | Keterangan                          |
|-----------------|-------------------------------------|
| `STAKE_API_KEY` | x-access-token dari akun Stake kamu |

### Pengaturan Bot — `config.json`
| Parameter       | Default     | Keterangan                              |
|-----------------|-------------|-----------------------------------------|
| `baseBet`       | 1000        | Taruhan per spin                        |
| `rows`          | 15          | Jumlah baris Plinko (8/12/15/16)        |
| `risk`          | `"low"`     | Risiko: `low` / `medium` / `high`       |
| `delayInterval` | 0.4 detik   | Jeda antar spin (anti rate-limit)       |
| `targetWager`   | 10.000.000  | Bot pause saat total wager tercapai     |
| `stopLoss`      | 5.000       | Bot pause saat rugi melebihi nilai ini  |
| `takeProfit`    | 20.000      | Bot pause saat profit melebihi nilai ini|

## Struktur File
- `main.py` — script utama bot
- `config.json` — pengaturan bot (bisa diedit bebas)
- `.env` — API token (jangan di-commit ke git)
- `.env.example` — template env
- `Stake.md` — blueprint asli (JavaScript)

## User Preferences
- Bahasa komunikasi: Bahasa Indonesia
