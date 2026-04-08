# 🚀 IDX Financial Statement Downloader

Otomasi pengunduhan laporan keuangan dari Bursa Efek Indonesia (IDX) dengan performa tinggi (`Asyncio`).

## 📦 Quick Start
```bash
pip install -r requirements.txt
python3 main.py
```

## ✨ Fitur Unggulan
- **Full Async**: Download paralel cepat via `httpx`.
- **Anti-Blokir**: Mekanisme `Retry` & `Exponential Backoff` cerdas.
- **Auto-Sync**: Daftar emiten diperbarui otomatis setiap dijalankan.
- **Pembersih URL**: Menangani link rusak/double slash secara otomatis.
- **Mode Akurat**: `--from-json` untuk memastikan tidak ada emiten terlewat.

## 🛠 Penggunaan CLI
| Perintah | Fungsi |
| :--- | :--- |
| `python3 main.py` | Jalankan secara interaktif (Tersedia menu) |
| `python3 main.py --from-json` | Mode Iterasi (Paling Aman & Akurat) |
| `python3 main.py --years 2024 --type saham` | Download spesifik |
| `python3 main.py --no-update` | Jalankan tanpa update daftar emiten |

## ⚠️ Penting
- **Limit**: Gunakan `--concurrency 5` (Default) agar tidak diblokir.
- **Python**: Minimal versi **3.10**.

---
*Dibuat untuk analisis data dan edukasi.*
