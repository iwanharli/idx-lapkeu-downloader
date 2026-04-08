# 🚀 IDX Financial Downloader (Async)

Downloader laporan keuangan IDX berbasis `asyncio` & `httpx`. Cepat, anti-blokir, dan mendukung penyimpanan NAS.

## 🛠 Instalasi

```bash
git clone https://github.com/iwanharli/idx-lapkeu-downloader.git
cd idx-lapkeu-downloader
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## 🚀 Perintah Utama

| Perintah | Fungsi |
| :--- | :--- |
| `python3 main.py --from-json` | Jalankan download sesuai daftar emiten terbaru |
| `python3 main.py --years 2024,2025` | Download tahun spesifik |
| `python3 main.py --output /path/to/nas` | Custom lokasi simpan (overrides .env) |
| `python3 main.py --type saham` | Pilih jenis (saham/obligasi/both) |

## ⚙️ Konfigurasi (.env)
Sesuaikan variabel di file `.env` untuk pengaturan permanen:
- `OUTPUT_DIR`: Folder penyimpanan.
- `BATCH_SIZE`: Jumlah emiten sebelum jeda 1 menit.
- `CONCURRENCY_LIMIT`: Batas download paralel.

## 📂 Struktur Folder
`[OUTPUT_DIR] / [Jenis_Efek] / [Tahun] / [Kode_Emiten] / [File_Laporan]`

---
*Status Log: Cek `downloader.log` (Detail) atau `failed.log` (Gagal).*
