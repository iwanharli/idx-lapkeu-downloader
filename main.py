import os
import time
import requests
from tqdm import tqdm
import logging

# Atur log biar enak dipantau
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("downloader.log"),
        logging.StreamHandler()
    ]
)

class IDXDownloader:
    BASE_URL = "https://www.idx.co.id"
    EMITEN_API = f"{BASE_URL}/primary/Helper/GetEmiten?emitenType=s"
    REPORT_API = f"{BASE_URL}/primary/ListedCompany/GetFinancialReport"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "X-Requested-With": "XMLHttpRequest"
    }

    def __init__(self, save_dir="laporan_keuangan"):
        self.save_dir = save_dir
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        # Kalau nanti kena blokir Cloudflare, mungkin butuh cookies tambahan
        os.makedirs(self.save_dir, exist_ok=True)

    def get_emiten_list(self):
        """Ambil daftar semua perusahaan yang ada di bursa"""
        logging.info("Fetching emiten list...")
        try:
            response = self.session.get(self.EMITEN_API)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"Failed to fetch emiten list: {e}")
            return []

    def get_reports_metadata(self, year, emiten_type="s", report_type="rdf", periode="audit", page_size=100):
        """Ambil metadata buat laporan keuangan (dengan pengulangan halaman otomatis)"""
        logging.info(f"Mengambil metadata Tahun: {year}, Tipe: {report_type}, Efek: {emiten_type}...")
        
        all_results = []
        index_from = 1
        
        while True:
            params = {
                "indexFrom": index_from,
                "pageSize": page_size,
                "year": year,
                "reportType": report_type,
                "EmitenType": emiten_type,
                "periode": periode,
                "SortColumn": "KodeEmiten",
                "SortOrder": "asc"
            }
            try:
                response = self.session.get(self.REPORT_API, params=params)
                response.raise_for_status()
                data = response.json()
                
                results = data.get("Results", [])
                if not results:
                    break
                    
                all_results.extend(results)
                
                # Cek jumlah total yang ada di server (harus pakai ResultCount)
                total = data.get("ResultCount", 0)
                if len(all_results) >= total:
                    break
                    
                index_from += page_size
                logging.info(f"Sudah terambil {len(all_results)} dari {total} data...")
                time.sleep(1) # Jeda biar nggak kena blokir
                
            except Exception as e:
                logging.error(f"Gagal ambil data pada urutan {index_from}: {e}")
                break
                
        return all_results

    def download_file(self, url, filename, subfolder=""):
        """Download file sambil munculin bar prosesnya"""
        full_path = os.path.join(self.save_dir, subfolder)
        os.makedirs(full_path, exist_ok=True)
        filepath = os.path.join(full_path, filename)

        if os.path.exists(filepath):
            return True

        try:
            response = self.session.get(url, stream=True, timeout=30)
            response.raise_for_status()
            
            total_size = int(response.headers.get('content-length', 0))
            
            with open(filepath, 'wb') as f, tqdm(
                desc=filename,
                total=total_size,
                unit='iB',
                unit_scale=True,
                unit_divisor=1024,
                leave=False
            ) as bar:
                for data in response.iter_content(chunk_size=1024):
                    size = f.write(data)
                    bar.update(size)
            return True
        except Exception as e:
            logging.error(f"Error downloading {filename}: {e}")
            return False

    def run(self, year=2026, emiten_type="s", limit=None):
        """Proses utama buat download semua laporan per tahun dan jenis efek"""
        type_name = "saham" if emiten_type == "s" else "obligasi"
        reports = self.get_reports_metadata(year=year, emiten_type=emiten_type)
        
        if not reports:
            logging.warning("No reports found.")
            return

        if limit:
            reports = reports[:limit]
            logging.info(f"Limited run: downloading {limit} reports.")
        else:
            logging.info(f"Found {len(reports)} reports to download.")

        success_count = 0
        for info in tqdm(reports, desc="Overall Progress"):
            kode = info.get("KodeEmiten")
            # Ambil semua lampiran yang ada
            attachments = info.get("Attachments", [])
            
            downloaded_for_emiten = False
            for attachment in attachments:
                file_path = attachment.get("File_Path")
                file_name = attachment.get("File_Name", "")
                
                # Sikat semua jenis file yang ada
                if file_path:
                    download_url = self.BASE_URL + file_path
                    
                    # Create a friendly filename
                    ext = os.path.splitext(file_path)[1]
                    local_filename = f"{file_name}".replace(" ", "_")
                    if not local_filename.endswith(ext):
                        local_filename += ext
                    
                    # Subfolder structure: {type}/{YEAR}/{KODE}
                    subfolder = os.path.join(type_name, str(year), kode)
                    
                    if self.download_file(download_url, local_filename, subfolder=subfolder):
                        downloaded_for_emiten = True
            time.sleep(1) # Jeda dikit biar nggak dikira spam
            
            if downloaded_for_emiten:
                success_count += 1
            
            time.sleep(0.5)
            
        logging.info(f"Download completed. Success: {success_count}/{len(reports)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="IDX Financial Statement Downloader")
    parser.add_argument("--years", type=str, default="2026", help="Years to download (e.g., 2026 or 2022,2023,2024)")
    parser.add_argument("--start-year", type=int, help="Start year for range download")
    parser.add_argument("--end-year", type=int, help="End year for range download")
    parser.add_argument("--type", type=str, default="saham", choices=["saham", "obligasi", "both"], help="Asset type to download")
    parser.add_argument("--limit", type=int, default=None, help="Limit jumlah perusahaan per tahun (buat testing)")
    
    args = parser.parse_args()
    
    downloader = IDXDownloader()
    
    years_to_download = []
    asset_types = []
    
    # Kalau dijalanin polosan (tanpa argumen)
    if not args.start_year and not args.end_year and args.years == "2026" and args.type == "saham":
        print("\n=== IDX Financial Statement Downloader ===")
        
        # 1. Pilih Jenis Efek
        print("\nPilih Jenis Efek:")
        print("1. Saham")
        print("2. Obligasi")
        print("3. Semua (Saham & Obligasi)")
        choice = input("Masukkan pilihan (1-3, default 1): ").strip()
        
        if choice == "2":
            asset_types = ["o"]
        elif choice == "3":
            asset_types = ["s", "o"]
        else:
            asset_types = ["s"]

        # 2. Pilih Rentang Tahun
        try:
            start_in = input("\nMasukkan tahun awal (default 2026): ").strip()
            start = int(start_in) if start_in else 2026
            
            end_in = input("Masukkan tahun akhir (default 2026): ").strip()
            end = int(end_in) if end_in else 2026
            
            if start > end:
                print("Tahun awal tidak boleh lebih besar dari tahun akhir. Menukar posisi...")
                start, end = end, start
                
            years_to_download = list(range(start, end + 1))
        except ValueError:
            print("Input tidak valid, mendownload tahun 2026 saja.")
            years_to_download = [2026]
    else:
        # Ini kalau user pakai perintah langsung di terminal
        if args.start_year and args.end_year:
            years_to_download = list(range(args.start_year, args.end_year + 1))
        else:
            years_to_download = [int(y.strip()) for y in args.years.split(",")]
            
        if args.type == "saham":
            asset_types = ["s"]
        elif args.type == "obligasi":
            asset_types = ["o"]
        else:
            asset_types = ["s", "o"]
    
    for year in years_to_download:
        for a_type in asset_types:
            type_label = "SAHAM" if a_type == "s" else "OBLIGASI"
            logging.info(f"=========== STARTING DOWNLOAD FOR {type_label} - YEAR {year} ===========")
            downloader.run(year=year, emiten_type=a_type, limit=args.limit)
            logging.info(f"=========== COMPLETED DOWNLOAD FOR {type_label} - YEAR {year} ===========")
