import os
import asyncio
import json
import subprocess
from pathlib import Path
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import uvicorn
from dotenv import load_dotenv

# Import from our new modular structure
from src.downloader import IDXDownloader
from src.config import DEFAULT_SAVE_DIR, STATUS_LOGS_DIR

# Load environment variables
load_dotenv()

app = FastAPI()

# Setup templates
templates = Jinja2Templates(directory="templates")

# Global state to track progress and connected clients
class State:
    def __init__(self):
        self.clients = set()
        self.is_running = False
        self.last_update = {"type": "idle"}
        self.current_task = None

state = State()

async def broadcast(data):
    state.last_update = data
    if not state.clients:
        return
    
    # Create copy of clients to avoid set changes during iteration
    disconnected = set()
    for client in state.clients:
        try:
            await client.send_json(data)
        except Exception:
            disconnected.add(client)
    
    for client in disconnected:
        state.clients.remove(client)

async def progress_callback(data):
    await broadcast(data)

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.clients.add(websocket)
    
    # Send current state immediately on connect
    try:
        await websocket.send_json(state.last_update)
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        state.clients.remove(websocket)
    except Exception:
        if websocket in state.clients:
            state.clients.remove(websocket)

@app.get("/api/settings")
async def get_settings():
    output_path = DEFAULT_SAVE_DIR
    output_dir = Path(output_path)
    storage_info = str(output_dir.absolute())
    return {
        "storage_path": storage_info,
        "exists": output_dir.exists()
    }

@app.get("/api/issuers")
async def get_issuers():
    output_path = DEFAULT_SAVE_DIR
    output_dir = Path(output_path)
    status_logs_dir = Path(STATUS_LOGS_DIR)
    
    storage_info = str(output_dir.absolute())
    if not output_dir.exists():
        return {"issuers": [], "storage_path": f"{storage_info} (Folder belum dibuat)"}
    
    # Load all status logs into memory map for quick lookup
    status_map = {}
    if status_logs_dir.exists():
        for log_file in status_logs_dir.glob("*.json"):
            try:
                with open(log_file, 'r') as f:
                    data = json.load(f)
                    year = data.get("metadata", {}).get("year")
                    asset_type = data.get("metadata", {}).get("type")
                    for code, info in data.get("issuers", {}).items():
                        status_map[f"{asset_type}-{year}-{code}"] = info
            except: continue

    issuers = []
    # Structure: [type]/[year]/[code]
    for asset_type in ["saham", "obligasi"]:
        type_path = output_dir / asset_type
        if not type_path.exists():
            continue
            
        for year_dir in type_path.iterdir():
            if not year_dir.is_dir():
                continue
            
            for code_dir in year_dir.iterdir():
                if not code_dir.is_dir():
                    continue
                
                # Check status from log
                issuer_key = f"{asset_type}-{year_dir.name}-{code_dir.name}"
                log_info = status_map.get(issuer_key, {})
                status = log_info.get("status", "unknown")
                last_attempt = log_info.get("last_attempt", "-")
                
                # Check if it has files
                files = list(code_dir.glob("*"))
                if files or status != "unknown":
                    issuers.append({
                        "id": issuer_key,
                        "code": code_dir.name,
                        "year": year_dir.name,
                        "type": asset_type,
                        "file_count": len(files),
                        "status": status,
                        "last_attempt": last_attempt,
                        "path": str(code_dir.absolute())
                    })
    
    # Sort by code
    issuers.sort(key=lambda x: x["code"])
    return {
        "issuers": issuers, 
        "storage_path": str(output_dir.absolute())
    }

@app.get("/api/files/{asset_type}/{year}/{code}")
async def get_files(asset_type: str, year: str, code: str):
    output_dir = Path(DEFAULT_SAVE_DIR)
    code_path = output_dir / asset_type / year / code
    status_logs_dir = Path(STATUS_LOGS_DIR)
    
    # Load URL data from status log if available
    file_metadata_map = {}
    log_file = status_logs_dir / f"{asset_type}_{year}_status.json"
    if log_file.exists():
        try:
            with open(log_file, 'r') as f:
                data = json.load(f)
                issuer_data = data.get("issuers", {}).get(code, {})
                for f_info in issuer_data.get("files", []):
                    file_metadata_map[f_info["filename"]] = f_info
        except: pass

    if not code_path.exists():
        raise HTTPException(status_code=404, detail="Folder emiten tidak ditemukan")
    
    files = []
    for f in code_path.iterdir():
        if f.is_file() and not f.name.startswith(".") and f.name != "download_status.json":
            stats = f.stat()
            meta = file_metadata_map.get(f.name, {})
            files.append({
                "name": f.name,
                "size": f"{stats.st_size / (1024*1024):.2f} MB",
                "ext": f.suffix.replace(".", "").upper(),
                "url": meta.get("url", "-"),
                "status": meta.get("status", "success")
            })
            
    return {"files": files}

@app.post("/api/open-folder")
async def open_folder(data: dict):
    path = data.get("path")
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path tidak valid")
    
    try:
        # Works on macOS
        subprocess.run(["open", path], check=True)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/start")
async def start_download(request: Request):
    if state.is_running:
        return {"status": "error", "message": "Download is already running"}
    
    data = await request.json()
    year_from = int(data.get("year_from", 2025))
    year_to = int(data.get("year_to", 2025))
    asset_type = data.get("type", "saham")
    retry_only = data.get("retry_only", False)
    limit = data.get("limit")
    if limit:
        limit = int(limit)

    # Pastikan urutan benar
    start_year = min(year_from, year_to)
    end_year = max(year_from, year_to)
    years_to_process = list(range(start_year, end_year + 1))

    output_dir = DEFAULT_SAVE_DIR
    concurrency = int(os.getenv("CONCURRENCY_LIMIT", 5))

    # Convert asset_type for downloader
    e_type = "s" if asset_type == "saham" else "o"
    if asset_type == "both":
        e_types = ["s", "o"]
    else:
        e_types = [e_type]

    async def run_task():
        state.is_running = True
        try:
            downloader = IDXDownloader(
                save_dir=output_dir, 
                concurrency_limit=concurrency,
                on_progress=progress_callback
            )
            
            for y in years_to_process:
                for t in e_types:
                    type_label = "SAHAM" if t == "s" else "OBLIGASI"
                    await broadcast({
                        "type": "status", 
                        "message": f"--- MEMPROSES {type_label} TAHUN {y} {'(RETRY GAGAL SAJA)' if retry_only else ''} ---", 
                        "mode": "info"
                    })
                    await downloader.run(year=y, emiten_type=t, limit=limit, from_json=True, retry_only=retry_only)
            
            await broadcast({"type": "complete", "message": "Semua pengunduhan dalam rentang tahun selesai!"})
        except Exception as e:
            await broadcast({"type": "error", "message": str(e)})
        finally:
            state.is_running = False
            state.last_update = {"type": "idle"}

    state.current_task = asyncio.create_task(run_task())
    return {"status": "success", "message": "Download started"}

@app.post("/stop")
async def stop_download():
    if not state.is_running:
        return {"status": "error", "message": "No task running"}
    
    if state.current_task:
        state.current_task.cancel()
        state.is_running = False
        state.last_update = {"type": "idle"}
        await broadcast({"type": "idle", "message": "Pengunduhan dihentikan oleh pengguna."})
        return {"status": "success", "message": "Download stopped"}
    
    return {"status": "error", "message": "Task not found"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
