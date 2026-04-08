# 🚀 IDX Financial Downloader (Async Edition)

Halo! Selamat datang di alat sedot data laporan keuangan IDX paling ngebut dan "anti-baper" terhadap blokir server. 😎

Script ini dirancang buat kamu yang males nungguin download satu-satu atau capek karena sering di-PHP-in sama server IDX yang hobi kasih error 403.

## ✨ Kenapa Pake Ini?

- **Ngebut Parah**: Pake tenaga `asyncio`, download-nya keroyokan jadi jauh lebih cepet.
- **Anti-Blokir**: Ada fitur *Backoff* otomatis. Kalau server IDX lagi sensi, script ini bakal "sabar" nunggu bentar terus lanjut lagi.
- **Pantang Menyerah**: Kalau ada download yang gagal di tengah jalan, script bakal otomatis nyoba lagi sampe 10x di akhir proses. Gak ada file yang ketinggalan!
- **Ramah NAS**: Bisa langsung tembak simpen ke NAS atau harddisk eksternal. Memory laptop kamu aman!
- **Gampang Diatur**: Semua settingan tinggal atur di file `.env`. Gak perlu pusing bongkar pasang kode.

## 🛠 Cara Pasang (Gampang Kok!)

1. **Ambil Kodenya**:
   ```bash
   git clone https://github.com/iwanharli/idx-lapkeu-downloader.git
   cd idx-lapkeu-downloader
   ```

2. **Siapin "Lingkungannya"**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Atur Settingan**:
   Copy file `.env.example` jadi `.env` terus edit dikit sesuai selera kamu.
   ```bash
   cp .env.example .env
   ```

## 🚀 Gas Download!

### Cara Paling Manjur
Cukup ketik ini dan biarkan script yang kerja lembur buat kamu:
```bash
python3 main.py --from-json
```

### Opsi Tambahan Buat yang Suka Customize
| Perintah | Fungsinya |
| :--- | :--- |
| `--from-json` | Pakai database lokal (akurat banget!) |
| `--output` | Simpen ke folder khusus (misal ke NAS) |
| `--years` | Pilih tahun tertentu, misal: `2023,2024` |
| `--type` | Mau saham aja, obligasi aja, atau keduanya (`both`) |
| `--no-update` | Langsung download tanpa update daftar emiten |

## 📂 Hasilnya Simpen di Mana?
Tenang, semua udah disusun rapi berdasarkan:
`[Folder_Tujuan] / [Jenis_Efek] / [Tahun] / [Kode_Emiten] / [File_Laporan.pdf]`

## 📝 Catatan Keamanan
- Kalau liat tulisan `[RATE LIMIT]`, itu server lagi minta istirahat. Script bakal otomatis urus itu kok.
- File log lengkap ada di `downloader.log`. Kalau mau liat yang gagal doang, cek di `failed.log`.

---
*Dibuat biar hidup analis saham jadi lebih indah. Selamat berburu data!* 📈🔥
