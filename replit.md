# Stake Plinko VIP Wager Bot

Bot otomatis untuk bermain Plinko di Stake.com menggunakan GraphQL API resmi.

## Stack
- **Python 3** + `requests`

## Cara Menjalankan
```bash
python stake_plinko_bot.py
```

## Konfigurasi
Edit bagian `BOT_CONFIG` dan `API_KEY` di `stake_plinko_bot.py`:

| Parameter      | Default        | Keterangan                              |
|----------------|----------------|-----------------------------------------|
| `API_KEY`      | *(wajib diisi)*| x-access-token dari akun Stake kamu     |
| `baseBet`      | 1000           | Taruhan per spin                        |
| `rows`         | 15             | Jumlah baris Plinko (8/12/15/16)        |
| `risk`         | `"low"`        | Risiko: `low` / `medium` / `high`       |
| `delayInterval`| 0.4 detik      | Jeda antar spin (anti rate-limit)       |
| `targetWager`  | 10.000.000     | Bot pause saat total wager tercapai     |
| `stopLoss`     | 5.000          | Bot pause saat rugi melebihi nilai ini  |
| `takeProfit`   | 20.000         | Bot pause saat profit melebihi nilai ini|

## File Utama
- `stake_plinko_bot.py` — script utama bot
- `Stake.md` — blueprint asli (JavaScript)

## User Preferences
- Bahasa komunikasi: Bahasa Indonesia
