import os
import json
import asyncio
import httpx
import logging
from datetime import datetime

# Setup Logger
logger = logging.getLogger("EmitenFetcher")
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File Handler
fh = logging.FileHandler("downloader.log")
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

# Console Handler (Quiet)
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

class EmitenFetcher:
    BASE_URL = "https://www.idx.co.id"
    EMITEN_API = f"{BASE_URL}/primary/Helper/GetEmiten"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    def __init__(self, save_path="laporan_keuangan/list_emiten/emiten-code.json"):
        self.save_path = save_path
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

    async def fetch_type(self, client, e_type):
        type_label = "Saham" if e_type == 's' else "Obligasi"
        logger.warning(f"[INFO] Mengambil daftar {type_label} terbaru...")
        
        max_retries = 3
        backoff_times = [10, 30, 60] # Jeda lebih lama untuk fetch emiten

        for attempt in range(max_retries):
            try:
                response = await client.get(f"{self.EMITEN_API}?emitenType={e_type}", timeout=30)
                
                if response.status_code in [403, 429]:
                    if attempt < max_retries - 1:
                        wait_time = backoff_times[attempt]
                        logger.warning(f"\n[BACKOFF] Terdeteksi pembatasan saat ambil daftar {type_label}. Istirahat {wait_time} detik...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"[ERROR] Gagal mengambil daftar {type_label}: Terblokir permanen (403/429).")
                        return []

                response.raise_for_status()
                data = response.json()
                
                for item in data:
                    item['JenisEfek'] = type_label
                
                logger.info(f"[SUCCESS] Berhasil mengambil {len(data)} data {type_label}.")
                return data
            except Exception as e:
                err_msg = str(e).splitlines()[0]
                if attempt < max_retries - 1:
                    await asyncio.sleep(5)
                    continue
                logger.error(f"[ERROR] Gagal mengambil daftar {type_label}: {err_msg}")
                return []
        return []

    async def fetch_all(self):
        async with httpx.AsyncClient(headers=self.HEADERS, follow_redirects=True) as client:
            tasks = [self.fetch_type(client, 's'), self.fetch_type(client, 'o')]
            results = await asyncio.gather(*tasks)
            
            all_emiten = []
            for r in results:
                all_emiten.extend(r)

            if not all_emiten:
                if os.path.exists(self.save_path):
                    logger.warning("[WARN] Gagal mendapatkan data baru dari IDX. Menggunakan data emiten lama yang tersedia.")
                else:
                    logger.error("[ERROR] Gagal mendapatkan data emiten dan tidak ada data lama yang ditemukan.")
                return

            # Metadata wrapping
            output_data = {
                "metadata": {
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_emiten": len(all_emiten),
                    "source": self.BASE_URL
                },
                "emiten_list": all_emiten
            }

            try:
                with open(self.save_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, indent=4, ensure_ascii=False)
                
                logger.warning(f"[SUCCESS] Daftar emiten diperbarui: {len(all_emiten)} entitas tersimpan.")
            except Exception as e:
                logger.error(f"[ERROR] Gagal menyimpan file JSON: {e}")

if __name__ == "__main__":
    fetcher = EmitenFetcher()
    try:
        asyncio.run(fetcher.fetch_all())
    except KeyboardInterrupt:
        print("\nDihentikan.")
