import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- CONSTANTS ---
BASE_URL = "https://www.idx.co.id"
REPORT_API = f"{BASE_URL}/primary/ListedCompany/GetFinancialReport"
EMITEN_API = f"{BASE_URL}/primary/Helper/GetEmiten"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest"
}

# --- PATHS ---
DEFAULT_SAVE_DIR = os.getenv("OUTPUT_DIR", "laporan_keuangan")
METADATA_DIR = "metadata"
EMITEN_LIST_PATH = os.path.join(METADATA_DIR, "issuers.json")
STATUS_LOGS_DIR = "status_logs"
LOGS_DIR = "logs"

# Ensure directories exist
os.makedirs(METADATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# --- LOGGING SETUP ---
def setup_logging():
    # Base formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Main Logger
    logger = logging.getLogger("IDXDownloader")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(os.path.join(LOGS_DIR, "downloader.log"))
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)

    # Failed Logger
    failed_logger = logging.getLogger("FailedDownloader")
    if not failed_logger.handlers:
        failed_logger.setLevel(logging.ERROR)
        ffh = logging.FileHandler(os.path.join(LOGS_DIR, "failed.log"))
        ffh.setFormatter(formatter)
        failed_logger.addHandler(ffh)

    # Emiten Fetcher Logger
    fetcher_logger = logging.getLogger("EmitenFetcher")
    if not fetcher_logger.handlers:
        fetcher_logger.setLevel(logging.INFO)
        fetcher_logger.addHandler(fh) # Use the same file handler
        fetcher_logger.addHandler(ch)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    return logger, failed_logger, fetcher_logger

# Initialize loggers
logger, failed_logger, fetcher_logger = setup_logging()
