import os
import json
import requests
import logging

# Atur log biar kelihatan prosesnya
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def fetch_all(self):
        """Ambil list semua kode emiten (saham & obligasi)"""
        all_emiten = []
        
        for e_type in ['s', 'o']:
            type_label = "Saham" if e_type == 's' else "Obligasi"
            logging.info(f"Mengambil daftar {type_label}...")
            
            try:
                response = self.session.get(f"{self.EMITEN_API}?emitenType={e_type}")
                response.raise_for_status()
                data = response.json()
                
                # Tandain mana yang saham mana yang obligasi
                for item in data:
                    item['JenisEfek'] = type_label
                    all_emiten.append(item)
                    
            except Exception as e:
                logging.error(f"Gagal mengambil daftar {type_label}: {e}")

        # Simpan hasilnya ke file JSON
        try:
            with open(self.save_path, 'w', encoding='utf-8') as f:
                json.dump(all_emiten, f, indent=4, ensure_ascii=False)
            logging.info(f"Berhasil menyimpan {len(all_emiten)} emiten ke: {self.save_path}")
        except Exception as e:
            logging.error(f"Gagal menyimpan file JSON: {e}")

if __name__ == "__main__":
    fetcher = EmitenFetcher()
    fetcher.fetch_all()
