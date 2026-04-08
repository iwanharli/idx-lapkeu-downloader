# 🚀 IDX Financial Downloader (Async)

Downloader laporan keuangan IDX berbasis `asyncio` & `httpx`. Cepat, anti-blokir, dan mendukung penyimpanan NAS. Kini dilengkapi dengan **Premium Web Dashboard!**

## 🛠 Instalasi

```bash
git clone https://github.com/iwanharli/idx-lapkeu-downloader.git
cd idx-lapkeu-downloader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 🖥 Web Dashboard (Rekomendasi)
Jalankan antarmuka visual premium untuk mengontrol dan memantau download:
```bash
python3 web_server.py
```
Lalu buka browser di: [http://localhost:8000](http://localhost:8000)

## 🚀 Perintah CLI
Jika lebih suka menggunakan terminal:
| Perintah | Fungsi |
| :--- | :--- |
| `python3 main.py --from-json` | Jalankan download sesuai daftar emiten terbaru |
| `python3 main.py --years 2024,2025` | Download tahun spesifik |
| `python3 main.py --output /path/to/nas` | Custom lokasi simpan |

## ⚙️ Konfigurasi (.env)
Sesuaikan variabel di file `.env` untuk pengaturan permanen seperti `OUTPUT_DIR` (lokasi NAS), `BATCH_SIZE`, dan `CONCURRENCY_LIMIT`.

---
*Status Log: Cek `downloader.log` (Detail) atau `failed.log` (Gagal).*
