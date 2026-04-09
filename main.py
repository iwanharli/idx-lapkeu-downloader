import asyncio
import os
import argparse
from datetime import datetime
from src.config import logger, DEFAULT_SAVE_DIR
from src.fetcher import EmitenFetcher
from src.downloader import IDXDownloader

async def main():
    parser = argparse.ArgumentParser(description="IDX Financial Statement Downloader (Async)")
    parser.add_argument("--years", type=str, default=None, help="Tahun (koma sebagai pemisah)")
    parser.add_argument("--start-year", type=int, help="Tahun awal")
    parser.add_argument("--end-year", type=int, help="Tahun akhir")
    parser.add_argument("--type", type=str, default="saham", choices=["saham", "obligasi", "both"], help="Tipe efek")
    parser.add_argument("--limit", type=int, default=None, help="Limit emiten per tahun")
    
    # Defaults from .env / config
    env_concurrency = int(os.getenv("CONCURRENCY_LIMIT", 5))
    env_output = DEFAULT_SAVE_DIR

    parser.add_argument("--concurrency", type=int, default=env_concurrency, help="Jumlah download paralel")
    parser.add_argument("--from-json", action="store_true", help="Ambil daftar kode emiten dari file JSON")
    parser.add_argument("--no-update", action="store_true", help="Lewati update daftar emiten otomatis")
    parser.add_argument("--output", type=str, default=env_output, help="Lokasi penyimpanan laporan (misal path ke NAS)")
    parser.add_argument("--retry-only", action="store_true", help="Hanya proses emiten yang gagal/pending di log status")
    
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
            logger.warning(f"[START] {('SAHAM' if a_type == 's' else 'OBLIGASI')} {year}{( ' (RETRY ONLY)' if args.retry_only else '')}")
            await downloader.run(year=year, emiten_type=a_type, limit=args.limit, from_json=args.from_json, retry_only=args.retry_only)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDihentikan oleh pengguna.")
