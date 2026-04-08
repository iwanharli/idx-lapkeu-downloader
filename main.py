import os
import asyncio
import httpx
import aiofiles
from tqdm.asyncio import tqdm
import logging
import argparse
import time
import json
from datetime import datetime
from dotenv import load_dotenv
from fetch_emiten import EmitenFetcher

# Load environment variables
load_dotenv()

# Setup Logger
logger = logging.getLogger("IDXDownloader")
logger.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

# File Handler (Detailed)
fh = logging.FileHandler("downloader.log")
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

# Console Handler (Quiet)
ch = logging.StreamHandler()
ch.setLevel(logging.WARNING)
ch.setFormatter(formatter)

logger.addHandler(fh)
logger.addHandler(ch)

# Failed Logger
failed_logger = logging.getLogger("FailedDownloader")
failed_logger.setLevel(logging.ERROR)
ffh = logging.FileHandler("failed.log")
ffh.setFormatter(formatter)
failed_logger.addHandler(ffh)

# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

class IDXDownloader:
    BASE_URL = "https://www.idx.co.id"
    REPORT_API = f"{BASE_URL}/primary/ListedCompany/GetFinancialReport"
    EMITEN_LIST_PATH = "laporan_keuangan/list_emiten/emiten-code.json"
    
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan",
        "Accept": "application/json, text/plain, */*",
        "X-Requested-With": "XMLHttpRequest"
    }

    def __init__(self, save_dir="laporan_keuangan", concurrency_limit=5):
        self.save_dir = save_dir
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
        # Load from .env or default
        meta_limit = int(os.getenv("META_CONCURRENCY", 1))
        self.meta_semaphore = asyncio.Semaphore(meta_limit) 
        
        self.batch_size = int(os.getenv("BATCH_SIZE", 20))
        self.batch_cooldown = int(os.getenv("BATCH_COOLDOWN", 60))
        
        self.failed_queue = [] # Antrean untuk percobaan ulang di akhir
        os.makedirs(self.save_dir, exist_ok=True)

    async def get_reports_metadata(self, client, year, emiten_type="s", emiten_code=None, report_type="rdf", periode="audit", page_size=2000):
        params = {
            "indexFrom": 1,
            "pageSize": page_size,
            "year": year,
            "reportType": report_type,
            "EmitenType": emiten_type,
            "periode": periode,
            "SortColumn": "KodeEmiten",
            "SortOrder": "asc"
        }
        
        if emiten_code:
            params["kodeEmiten"] = emiten_code

        max_retries = 3
        backoff_times = [5, 15, 30] 

        for attempt in range(max_retries):
            async with self.meta_semaphore:
                try:
                    if emiten_code:
                        await asyncio.sleep(0.5)
                        
                    response = await client.get(self.REPORT_API, params=params, timeout=30)
                    
                    if response.status_code in [403, 429]:
                        if attempt < max_retries - 1:
                            wait_time = backoff_times[attempt]
                            logger.warning(f"[BACKOFF] Terdeteksi pembatasan server untuk {emiten_code if emiten_code else emiten_type}. Istirahat {wait_time} detik...")
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            logger.info(f"[METADATA_FAIL] {emiten_code}: Terblokir permanen (403/429) setelah {max_retries} percobaan.")
                            return []

                    response.raise_for_status()
                    data = response.json()
                    return data.get("Results", [])
                    
                except Exception as e:
                    err_msg = str(e).splitlines()[0]
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)
                        continue
                    logger.info(f"[METADATA_FAIL] {emiten_code if emiten_code else emiten_type}: {err_msg}")
                    return []
        return []

    async def download_file(self, client, url, filename, emiten_code, subfolder="", is_recovery=False):
        full_path = os.path.join(self.save_dir, subfolder)
        filepath = os.path.join(full_path, filename)

        async with self.semaphore:
            try:
                if not is_recovery:
                    await asyncio.sleep(0.1)

                if os.path.exists(filepath):
                    async with client.stream("GET", url, timeout=10) as response:
                        if response.status_code == 200:
                            remote_size = int(response.headers.get('content-length', 0))
                            local_size = os.path.getsize(filepath)
                            if local_size == remote_size:
                                logger.info(f"[SKIPPED]    | {emiten_code} | {filename}")
                                return "skipped"
                
                async with client.stream("GET", url, timeout=60) as response:
                    if response.status_code == 404:
                        logger.error(f"[NOT FOUND]  | {emiten_code} | {filename}")
                        return "failed"
                    
                    if response.status_code in [403, 429]:
                        logger.error(f"[RATE LIMIT] | {emiten_code} | {filename}")
                        raise httpx.HTTPStatusError(f"Server returned {response.status_code}", request=response.request, response=response)

                    response.raise_for_status()
                    os.makedirs(full_path, exist_ok=True)
                    async with aiofiles.open(filepath, mode='wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            await f.write(chunk)
                    
                    logger.info(f"[SUCCESS]    | {emiten_code} | {filename}")
                    return "success"
            except Exception as e:
                err_msg = str(e).splitlines()[0]
                if "404 Not Found" in err_msg:
                    logger.error(f"[NOT FOUND]  | {emiten_code} | {filename}")
                elif any(x in err_msg for x in ["403", "429", "Forbidden", "Too Many Requests"]):
                    if "[RATE LIMIT]" not in err_msg:
                        logger.error(f"[RATE LIMIT] | {emiten_code} | {filename}")
                else:
                    logger.error(f"[FAILED]     | {emiten_code} | {filename} - {err_msg}")
                
                if not is_recovery:
                    failed_logger.error(f"{emiten_code} | {filename} | {url} | {err_msg}")
                    self.failed_queue.append({
                        "url": url,
                        "filename": filename,
                        "emiten_code": emiten_code,
                        "subfolder": subfolder
                    })
                return "failed"

    async def run_recovery(self, client):
        if not self.failed_queue:
            return 0

        logger.warning(f"[RECOVERY] Memulai proses ulang untuk {len(self.failed_queue)} file yang gagal...")
        
        max_rounds = 10
        recovered_count = 0

        for round_num in range(1, max_rounds + 1):
            if not self.failed_queue:
                break
            
            logger.warning(f"[RECOVERY] Putaran {round_num}/{max_rounds} - Mencoba {len(self.failed_queue)} file...")
            
            current_queue = self.failed_queue.copy()
            self.failed_queue = []
            
            pbar = tqdm(total=len(current_queue), desc=f"Recovery Round {round_num}")
            tasks = [self.download_file(client, f["url"], f["filename"], f["emiten_code"], f["subfolder"], is_recovery=True) for f in current_queue]
            results = await asyncio.gather(*tasks)
            
            for i, result in enumerate(results):
                if result == "success":
                    recovered_count += 1
                else:
                    self.failed_queue.append(current_queue[i])
                pbar.update(1)
            
            pbar.close()
            
            if self.failed_queue and round_num < max_rounds:
                wait_btn = 5 * round_num 
                logger.warning(f"[RECOVERY] Selesai putaran {round_num}. Istirahat {wait_btn} detik...")
                await asyncio.sleep(wait_btn)

        return recovered_count

    async def process_emiten(self, client, emiten_code, year, emiten_type, subfolder_prefix):
        reports = await self.get_reports_metadata(client, year, emiten_type=emiten_type, emiten_code=emiten_code)
        
        res = {
            "emiten_status": "no_data",
            "file_stats": {"success": 0, "skipped": 0, "failed": 0}
        }

        if not reports:
            return res

        file_tasks = []
        for info in reports:
            attachments = info.get("Attachments", [])
            for attachment in attachments:
                file_path = attachment.get("File_Path")
                file_name = attachment.get("File_Name", "")
                if file_path:
                    cleaned_path = file_path.replace("//", "/")
                    if not cleaned_path.startswith("/"):
                        cleaned_path = "/" + cleaned_path
                    download_url = self.BASE_URL + cleaned_path
                    
                    ext = os.path.splitext(file_path)[1]
                    local_filename = f"{file_name}".replace(" ", "_").replace("/", "_")
                    if not local_filename.endswith(ext):
                        local_filename += ext
                    
                    subfolder = os.path.join(subfolder_prefix, str(year), emiten_code)
                    file_tasks.append(self.download_file(client, download_url, local_filename, emiten_code, subfolder=subfolder))

        if not file_tasks:
            res["emiten_status"] = "no_files"
            return res

        file_results = await asyncio.gather(*file_tasks)
        
        for r in file_results:
            res["file_stats"][r] += 1

        if res["file_stats"]["success"] > 0:
            res["emiten_status"] = "downloaded"
        elif res["file_stats"]["failed"] > 0:
            res["emiten_status"] = "partial_failed"
        else:
            res["emiten_status"] = "skipped"
            
        return res

    async def run(self, year=2024, emiten_type="s", limit=None, from_json=False):
        type_name = "saham" if emiten_type == "s" else "obligasi"
        type_label = type_name.upper()
        
        async with httpx.AsyncClient(headers=self.HEADERS, follow_redirects=True, timeout=None) as client:
            emiten_to_process = []
            
            if from_json:
                if not os.path.exists(self.EMITEN_LIST_PATH):
                    logger.error(f"[ERROR] File {self.EMITEN_LIST_PATH} tidak ditemukan.")
                    return
                
                with open(self.EMITEN_LIST_PATH, 'r') as f:
                    data = json.load(f)
                    all_emiten = data.get("emiten_list", [])
                    filter_label = "Saham" if emiten_type == "s" else "Obligasi"
                    emiten_to_process = [e.get("KodeEmiten") for e in all_emiten if e.get("JenisEfek") == filter_label]
                    
                logger.warning(f"[INFO] Mode Iterasi aktif. Memproses {len(emiten_to_process)} emiten dari JSON.")
            else:
                bulk_reports = await self.get_reports_metadata(client, year, emiten_type=emiten_type)
                emiten_to_process = sorted(list(set(r.get("KodeEmiten") for r in bulk_reports)))
                logger.warning(f"[INFO] Mode Bulk aktif. Ditemukan {len(emiten_to_process)} emiten dengan laporan.")

            if limit:
                emiten_to_process = emiten_to_process[:limit]
                logger.warning(f"[INFO] Limit aktif: Hanya memproses {limit} emiten.")

            if not emiten_to_process:
                logger.warning(f"[WARN] Tidak ada emiten untuk diproses.")
                return

            emiten_stats = {"downloaded": 0, "skipped": 0, "failed": 0, "no_data": 0}
            total_file_stats = {"success": 0, "skipped": 0, "failed": 0}
            
            pbar = tqdm(total=len(emiten_to_process), desc=f"IDX {type_label} {year}")
            
            tasks = [self.process_emiten(client, code, year, emiten_type, type_name) for code in emiten_to_process]
            
            processed_count = 0
            for task in asyncio.as_completed(tasks):
                res = await task
                processed_count += 1
                
                status = res["emiten_status"]
                
                if status in ["downloaded", "partial_failed"]:
                    emiten_stats["downloaded"] += 1
                elif status == "skipped":
                    emiten_stats["skipped"] += 1
                elif status == "no_data" or status == "no_files":
                    emiten_stats["no_data"] += 1
                else:
                    emiten_stats["failed"] += 1
                
                total_file_stats["success"] += res["file_stats"]["success"]
                total_file_stats["skipped"] += res["file_stats"]["skipped"]
                total_file_stats["failed"] += res["file_stats"]["failed"]
                
                pbar.update(1)

                if processed_count % self.batch_size == 0 and processed_count < len(emiten_to_process):
                    logger.warning(f"[COOLDOWN] Sudah memproses {processed_count} emiten. Istirahat {self.batch_cooldown} detik...")
                    await asyncio.sleep(self.batch_cooldown)
            pbar.close()

            initial_failed = total_file_stats["failed"]
            recovered = 0
            if self.failed_queue:
                recovered = await self.run_recovery(client)
                total_file_stats["success"] += recovered
                total_file_stats["failed"] -= recovered

            total_files = sum(total_file_stats.values())

            logger.warning(f"")
            logger.warning(f"[SUMMARY] {type_label} {year}")
            logger.warning(f"  - Total Emiten    : {len(emiten_to_process)}")
            logger.warning(f"  - Emiten Terdownload : {emiten_stats['downloaded']}")
            logger.warning(f"  - Emiten Terskip     : {emiten_stats['skipped']}")
            if emiten_stats['no_data'] > 0:
                logger.warning(f"  - Emiten No Data     : {emiten_stats['no_data']}")
            logger.warning(f"--------------------------------------------")
            logger.warning(f"  - Total Files     : {total_files}")
            logger.warning(f"  - Downloaded      : {total_file_stats['success']} (Recovered: {recovered})")
            logger.warning(f"  - Skipped         : {total_file_stats['skipped']}")
            logger.warning(f"  - Failed          : {total_file_stats['failed']}")
            logger.warning(f"============================================")

async def main():
    parser = argparse.ArgumentParser(description="IDX Financial Statement Downloader (Async)")
    parser.add_argument("--years", type=str, default=None, help="Tahun (koma sebagai pemisah)")
    parser.add_argument("--start-year", type=int, help="Tahun awal")
    parser.add_argument("--end-year", type=int, help="Tahun akhir")
    parser.add_argument("--type", type=str, default="saham", choices=["saham", "obligasi", "both"], help="Tipe efek")
    parser.add_argument("--limit", type=int, default=None, help="Limit emiten per tahun")
    
    # Defaults from .env if available
    env_concurrency = int(os.getenv("CONCURRENCY_LIMIT", 5))
    env_output = os.getenv("OUTPUT_DIR", "laporan_keuangan")

    parser.add_argument("--concurrency", type=int, default=env_concurrency, help="Jumlah download paralel")
    parser.add_argument("--from-json", action="store_true", help="Ambil daftar kode emiten dari file JSON")
    parser.add_argument("--no-update", action="store_true", help="Lewati update daftar emiten otomatis")
    parser.add_argument("--output", type=str, default=env_output, help="Lokasi penyimpanan laporan (misal path ke NAS)")
    
    args = parser.parse_args()
    
    if not args.no_update:
        fetcher = EmitenFetcher()
        await fetcher.fetch_all()
    
    downloader = IDXDownloader(save_dir=args.output, concurrency_limit=args.concurrency)
    years_to_download = []
    asset_types = []
    
    if not args.start_year and not args.end_year and not args.years:
        print("\n=== IDX Financial Statement Downloader (Async) ===")
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

        try:
            cur_year = datetime.now().year
            start_in = input(f"\nMasukkan tahun awal (default {cur_year}): ").strip()
            start = int(start_in) if start_in else cur_year
            
            end_in = input(f"Masukkan tahun akhir (default {cur_year}): ").strip()
            end = int(end_in) if end_in else cur_year
            
            if start > end:
                start, end = end, start
            years_to_download = list(range(start, end + 1))
        except ValueError:
            print("Input tidak valid, gunakan tahun berjalan.")
            years_to_download = [datetime.now().year]
    else:
        if args.start_year and args.end_year:
            years_to_download = list(range(args.start_year, args.end_year + 1))
        elif args.years:
            years_to_download = [int(y.strip()) for y in args.years.split(",")]
        else:
            years_to_download = [datetime.now().year]
            
        if args.type == "saham":
            asset_types = ["s"]
        elif args.type == "obligasi":
            asset_types = ["o"]
        else:
            asset_types = ["s", "o"]
    
    for year in years_to_download:
        for a_type in asset_types:
            logger.warning(f"[START] {('SAHAM' if a_type == 's' else 'OBLIGASI')} {year}")
            await downloader.run(year=year, emiten_type=a_type, limit=args.limit, from_json=args.from_json)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDihentikan oleh pengguna.")
