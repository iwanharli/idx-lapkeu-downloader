import os
import json
import asyncio
import httpx
from datetime import datetime
from src.config import fetcher_logger as logger, EMITEN_API, HEADERS, EMITEN_LIST_PATH, BASE_URL

class EmitenFetcher:
    def __init__(self, save_path=EMITEN_LIST_PATH):
        self.save_path = save_path
        os.makedirs(os.path.dirname(self.save_path), exist_ok=True)

    async def fetch_type(self, client, e_type):
        type_label = "Saham" if e_type == 's' else "Obligasi"
        logger.warning(f"[INFO] Mengambil daftar {type_label} terbaru...")
        
        max_retries = 3
        backoff_times = [10, 30, 60]

        for attempt in range(max_retries):
            try:
                response = await client.get(f"{EMITEN_API}?emitenType={e_type}", timeout=30)
                
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
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
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

            output_data = {
                "metadata": {
                    "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_emiten": len(all_emiten),
                    "source": BASE_URL
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
    # For testing purposes if run directly
    import asyncio
    fetcher = EmitenFetcher()
    asyncio.run(fetcher.fetch_all())
