import os
import asyncio
import httpx
import aiofiles
from tqdm.asyncio import tqdm
import json
from datetime import datetime
from src.config import logger, failed_logger, BASE_URL, REPORT_API, EMITEN_LIST_PATH, STATUS_LOGS_DIR, HEADERS

class IDXDownloader:
    def __init__(self, save_dir="laporan_keuangan", concurrency_limit=5, on_progress=None):
        self.save_dir = save_dir
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        self.on_progress = on_progress
        
        # Load from .env or default via config/env
        meta_limit = int(os.getenv("META_CONCURRENCY", 1))
        self.meta_semaphore = asyncio.Semaphore(meta_limit) 
        
        self.batch_size = int(os.getenv("BATCH_SIZE", 20))
        self.batch_cooldown = int(os.getenv("BATCH_COOLDOWN", 60))
        
        self.failed_queue = [] # Antrean untuk percobaan ulang di akhir
        os.makedirs(self.save_dir, exist_ok=True)
        os.makedirs(STATUS_LOGS_DIR, exist_ok=True)

    def _get_status_file_path(self, year, emiten_type):
        type_name = "saham" if emiten_type == "s" else "obligasi"
        return os.path.join(STATUS_LOGS_DIR, f"{type_name}_{year}_status.json")

    def load_status(self, year, emiten_type):
        path = self._get_status_file_path(year, emiten_type)
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {"metadata": {"year": year, "type": emiten_type}, "issuers": {}}

    def save_status(self, year, emiten_type, status_data):
        path = self._get_status_file_path(year, emiten_type)
        status_data["metadata"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(path, 'w') as f:
            json.dump(status_data, f, indent=4)

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
                        
                    response = await client.get(REPORT_API, params=params, timeout=30)
                    
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
                                logger.info(f"[SKIPPED] | {emiten_code:<5} | {filename}")
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
                    
                    logger.info(f"[SUCCESS] | {emiten_code:<5} | {filename}")
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
                    failed_logger.error(f"{emiten_code:<5} | {filename} | {url} | {err_msg}")
                    logger.error(f"[FAILED]  | {emiten_code:<5} | {filename} - {err_msg}")
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

        msg = f"Memulai proses ulang untuk {len(self.failed_queue)} file yang gagal..."
        logger.warning(f"[RECOVERY] {msg}")
        if self.on_progress:
            await self.on_progress({"type": "status", "message": msg, "mode": "recovery"})
        
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

    async def process_emiten(self, client, emiten_code, year, emiten_type, subfolder_prefix, existing_issuer_status=None):
        reports = await self.get_reports_metadata(client, year, emiten_type=emiten_type, emiten_code=emiten_code)
        
        issuer_status = existing_issuer_status or {
            "emiten_code": emiten_code,
            "status": "pending",
            "last_attempt": None,
            "files": []
        }
        
        file_stats = {"success": 0, "skipped": 0, "failed": 0}

        if not reports:
            issuer_status["status"] = "no_data"
            issuer_status["last_attempt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return issuer_status

        success_files_map = {f["filename"]: f for f in issuer_status.get("files", []) if f["status"] == "success"}

        file_tasks = []
        pending_files_info = []

        for info in reports:
            attachments = info.get("Attachments", [])
            for attachment in attachments:
                file_path = attachment.get("File_Path")
                file_name = attachment.get("File_Name", "")
                if file_path:
                    cleaned_path = file_path.replace("//", "/")
                    if not cleaned_path.startswith("/"):
                        cleaned_path = "/" + cleaned_path
                    download_url = BASE_URL + cleaned_path
                    
                    ext = os.path.splitext(file_path)[1]
                    local_filename = f"{file_name}".replace(" ", "_").replace("/", "_")
                    if not local_filename.endswith(ext):
                        local_filename += ext
                    
                    subfolder = os.path.join(subfolder_prefix, str(year), emiten_code)
                    
                    is_already_done = False
                    if local_filename in success_files_map:
                        full_save_path = os.path.join(self.save_dir, subfolder, local_filename)
                        if os.path.exists(full_save_path):
                            is_already_done = True
                    
                    if is_already_done:
                        file_stats["skipped"] += 1
                        continue

                    file_tasks.append(self.download_file(client, download_url, local_filename, emiten_code, subfolder=subfolder))
                    pending_files_info.append({
                        "filename": local_filename,
                        "url": download_url,
                        "status": "pending"
                    })

        if not file_tasks and file_stats["skipped"] == 0:
            issuer_status["status"] = "no_files"
            issuer_status["last_attempt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return issuer_status

        if file_tasks:
            file_results = await asyncio.gather(*file_tasks)
            for i, result in enumerate(file_results):
                file_stats[result] += 1
                file_info = pending_files_info[i]
                file_info["status"] = result
                
                found = False
                for existing_file in issuer_status["files"]:
                    if existing_file["filename"] == file_info["filename"]:
                        existing_file["status"] = result
                        found = True
                        break
                if not found:
                    issuer_status["files"].append(file_info)

        has_failed = any(f["status"] == "failed" for f in issuer_status["files"])
        all_success = all(f["status"] == "success" for f in issuer_status["files"])
        
        if all_success and len(issuer_status["files"]) > 0:
            issuer_status["status"] = "completed"
        elif has_failed:
            issuer_status["status"] = "partial_failed"
        elif len(issuer_status["files"]) > 0:
            issuer_status["status"] = "downloading"
            
        issuer_status["last_attempt"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return issuer_status

    async def run(self, year=2024, emiten_type="s", limit=None, from_json=False, retry_only=False):
        type_name = "saham" if emiten_type == "s" else "obligasi"
        type_label = type_name.upper()
        
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=None) as client:
            emiten_to_process = []
            status_data = self.load_status(year, emiten_type)
            
            if from_json:
                if not os.path.exists(EMITEN_LIST_PATH):
                    logger.error(f"[ERROR] File {EMITEN_LIST_PATH} tidak ditemukan.")
                    return
                
                with open(EMITEN_LIST_PATH, 'r') as f:
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

            if retry_only:
                original_count = len(emiten_to_process)
                emiten_to_process = [e for e in emiten_to_process if status_data["issuers"].get(e, {}).get("status") != "completed"]
                skipped_count = original_count - len(emiten_to_process)
                if skipped_count > 0:
                    logger.warning(f"[INFO] Filter Retry: Melewati {skipped_count} emiten yang sudah 'completed'. Sisa: {len(emiten_to_process)}")

            if self.on_progress:
                await self.on_progress({
                    "type": "start",
                    "total": len(emiten_to_process),
                    "year": year,
                    "asset_type": type_label
                })

            emiten_stats = {"downloaded": 0, "skipped": 0, "failed": 0, "no_data": 0}
            total_file_stats = {"success": 0, "skipped": 0, "failed": 0}
            
            pbar = tqdm(total=len(emiten_to_process), desc=f"IDX {type_label} {year}")
            
            tasks = [self.process_emiten(client, code, year, emiten_type, type_name, status_data["issuers"].get(code)) for code in emiten_to_process]
            
            processed_count = 0
            for task in asyncio.as_completed(tasks):
                res = await task
                processed_count += 1
                
                emiten_code = res["emiten_code"]
                status_data["issuers"][emiten_code] = res
                self.save_status(year, emiten_type, status_data)

                status = res["status"]
                
                if status in ["completed", "partial_failed", "downloading"]:
                    emiten_stats["downloaded"] += 1
                elif status == "skipped":
                    emiten_stats["skipped"] += 1
                elif status == "no_data" or status == "no_files":
                    emiten_stats["no_data"] += 1
                else:
                    emiten_stats["failed"] += 1
                
                pbar.update(1)

                if self.on_progress:
                    await self.on_progress({
                        "type": "progress",
                        "current": processed_count,
                        "total": len(emiten_to_process),
                        "emiten": res.get("emiten_code", "???"),
                        "status": status,
                        "stats": emiten_stats
                    })

                if processed_count % self.batch_size == 0 and processed_count < len(emiten_to_process):
                    logger.warning(f"[COOLDOWN] Sudah memproses {processed_count} emiten. Istirahat {self.batch_cooldown} detik...")
                    if self.on_progress:
                        await self.on_progress({"type": "status", "message": f"Cooldown {self.batch_cooldown}s...", "mode": "cooldown"})
                    await asyncio.sleep(self.batch_cooldown)
            pbar.close()

            if self.failed_queue:
                recovered = await self.run_recovery(client)
                total_file_stats["success"] += recovered
                total_file_stats["failed"] -= recovered

            logger.warning(f"[SUMMARY] {type_label} {year} Selesai!")
