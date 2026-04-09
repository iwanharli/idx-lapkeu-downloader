import os
import shutil
from tqdm import tqdm
import argparse

# --- CONFIGURATION ---
SOURCE_DIR = "/Volumes/SARANG COBRA/LAPORAN-KEUANGAN-IDX"
DEST_DIR = "/Volumes/SARANG COBRA/LAPORAN-KEUANGAN-SAJA"

# Filters
ALLOWED_EXTENSIONS = {'.pdf', '.xlsx', '.xls'}
# Keywords to identify "Annual" or "Main" Financial Reports
KEYWORDS = [
    "FinancialStatement", 
    "Tahunan", 
    "AnnualReport", 
    "LKT", 
    "LAI",
    "Laporan_Keuangan", 
    "LaporanKeuangan"
]

def should_copy(filename):
    """
    Check if the file is a financial report based on extension and keywords.
    """
    name_lower = filename.lower()
    ext = os.path.splitext(name_lower)[1]
    
    if ext not in ALLOWED_EXTENSIONS:
        return False
    
    # If it's a PDF/Excel, we check for keywords to avoid copying 
    # things like 'instance.zip' (if it was renamed) or small metadata files.
    # However, since the user wants 'Laporan Keuangan Tahunan', 
    # we filter for those specifically.
    for kw in KEYWORDS:
        if kw.lower() in name_lower:
            return True
            
    return False

def main():
    parser = argparse.ArgumentParser(description="Utility to copy Annual Financial Reports only.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without actually copying.")
    args = parser.parse_args()

    if not os.path.exists(SOURCE_DIR):
        print(f"Error: Source directory not found: {SOURCE_DIR}")
        return

    print(f"Scanning: {SOURCE_DIR}")
    print(f"Target  : {DEST_DIR}")
    if args.dry_run:
        print("!!! DRY RUN MODE - No files will be copied !!!")

    print("🔍 Searching for reports (this may take a while on external drives)...")
    files_to_copy = []
    folder_count = 0
    
    # 1. First Pass: Scan for applicable files
    try:
        for root, dirs, files in os.walk(SOURCE_DIR):
            folder_count += 1
            if folder_count % 100 == 0:
                print(f"\r   Scanned {folder_count} folders, matched {len(files_to_copy)} files...", end="", flush=True)
            
            for file in files:
                if should_copy(file):
                    source_path = os.path.join(root, file)
                    rel_path = os.path.relpath(source_path, SOURCE_DIR)
                    dest_path = os.path.join(DEST_DIR, rel_path)
                    files_to_copy.append((source_path, dest_path))
    except KeyboardInterrupt:
        print("\n\n⚠️  Scan dihentikan oleh pengguna.")
        return

    print(f"\n✅ Scan selesai. Total folder diproses: {folder_count}")

    if not files_to_copy:
        print("❌ Tidak ditemukan laporan yang cocok dengan kriteria.")
        return

    print(f"📦 Ditemukan {len(files_to_copy)} laporan untuk disalin.")

    # 2. Second Pass: Perform Copy
    copied_count = 0
    skipped_count = 0
    
    # Use tqdm for a nice progress bar
    for src, dst in tqdm(files_to_copy, desc="Copying Reports"):
        if args.dry_run:
            # print(f"[DRY-RUN] Copy: {src} -> {dst}")
            copied_count += 1
            continue

        # Create destination directories if they don't exist
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        
        # Skip if already exists and same size (basic check)
        if os.path.exists(dst):
            if os.path.getsize(src) == os.path.getsize(dst):
                skipped_count += 1
                continue
        
        try:
            shutil.copy2(src, dst)
            copied_count += 1
        except Exception as e:
            print(f"\nError copying {src}: {e}")

    print("\n--- Summary ---")
    if args.dry_run:
        print(f"Would have copied: {copied_count} files.")
    else:
        print(f"Successfully copied: {copied_count} files.")
        print(f"Skipped (already exists): {skipped_count} files.")
    print("Done!")

if __name__ == "__main__":
    main()
