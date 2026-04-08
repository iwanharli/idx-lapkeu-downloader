# IDX Financial Statement Downloader

Alat otomatis berbasis Python untuk mengunduh laporan keuangan dan laporan tahunan dari Bursa Efek Indonesia (IDX) dengan struktur file yang rapi dan otomatis.

## ✨ Fitur Utama

- **Otomatisasi Penuh**: Mengambil metadata langsung dari API IDX.
- **Dukungan Multi-Tahun**: Bisa mengunduh satu tahun tertentu atau rentang tahun sekaligus.
- **Jenis Efek Lengkap**: Mendukung pengunduhan data Saham maupun Obligasi.
- **Antarmuka Interaktif**: Menanyakan pilihan tahun dan jenis efek secara langsung di terminal jika dijalankan tanpa argumen.
- **Struktur Folder Rapi**: File disimpan secara otomatis berdasarkan `jenis_efek/tahun/kode_emiten/`.
- **Ekstensi File Lengkap**: Mengunduh PDF, Excel (.xlsx), dan ZIP (XBRL/Instance).
- **Anti-Blocking**: Dilengkapi dengan headers browser asli dan jeda waktu (rate limiting) agar aman dari blokir IP.
- **Kamus Emiten**: Skrip terpisah untuk memperbarui daftar kode emiten terbaru.

## 🚀 Persiapan & Instalasi

### 1. Prasyarat
- Python 3.x terinstal di sistem Anda.

### 2. Kloning dan Setup Lingkungan
Buka terminal dan jalankan perintah berikut:

```bash
# Masuk ke direktori proyek
cd idx-lapkeu

# Buat virtual environment
python3 -m venv venv

# Aktifkan virtual environment
# Untuk Mac/Linux:
source venv/bin/activate
# Untuk Windows:
.\venv\Scripts\activate

# Instal dependensi
pip install -r requirements.txt
```

## 🛠 Cara Penggunaan

### 1. Menjalankan Secara Interaktif (Direkomendasikan)
Cukup jalankan script utama, dan ikuti petunjuk di terminal:
```bash
python3 main.py
```

### 2. Menjalankan via Command Line (Automasi)
Anda juga bisa memberikan argumen langsung untuk melewati input terminal:

- **Download rentang tahun untuk Saham:**
  ```bash
  python3 main.py --start-year 2022 --end-year 2024 --type saham
  ```
- **Download tahun spesifik untuk Obligasi:**
  ```bash
  python3 main.py --years 2023,2024 --type obligasi
  ```
- **Download keduanya (Saham & Obligasi) sekaligus:**
  ```bash
  python3 main.py --type both --year 2024
  ```

### 3. Memperbarui Daftar Emiten
Untuk memperbarui file `emiten-code.json` dengan daftar perusahaan terbaru dari IDX:
```bash
python3 fetch_emiten.py
```

## 📁 Struktur Folder Hasil Download

File akan disimpan dengan format berikut:
```text
laporan_keuangan/
├── saham/
│   └── 2024/
│       ├── BBCA/
│       │   ├── FinancialStatement-2024-Tahunan-BBCA.pdf
│       │   └── FinancialStatement-2024-Tahunan-BBCA.xlsx
│       └── TLKM/
│           └── ...
├── obligasi/
│   └── 2024/
│       └── ...
└── list_emiten/
    └── emiten-code.json
```

## ⚠️ Catatan Penting

- **Rate Limiting**: Skrip memiliki jeda 1 detik antar file untuk menghormati server IDX. Jangan mempersempit jeda ini secara drastis untuk menghindari blokir IP.
- **Ketersediaan Data**: Portal IDX saat ini umumnya menyediakan data laporan keuangan dari tahun 2022 ke atas.
- **Disk Space**: Mengunduh seluruh emiten (900+) untuk satu tahun penuh bisa memakan ruang penyimpanan yang cukup besar (Gigabytes).

## 📄 Lisensi
Proyek ini dibuat untuk tujuan edukasi dan analisis data pribadi.
