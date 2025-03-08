from fastapi import FastAPI, File, UploadFile, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import hashlib
import os
from typing import List
import asyncio

app = FastAPI()
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Cấu hình database
DATABASE_URL = "sqlite:///./files.db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class FileRecord(Base):
    __tablename__ = "files"
    hash = Column(String, primary_key=True)
    filename = Column(String, unique=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def compute_file_hash(file):
    """Tính hash SHA-256 của file theo stream."""
    hasher = hashlib.sha256()
    while chunk := file.read(8192):
        hasher.update(chunk)
    file.seek(0)  # Reset file pointer
    return hasher.hexdigest()

upload_progress = {"total": 0, "completed": 0}
active_websockets = []

async def notify_progress():
    for websocket in active_websockets:
        await websocket.send_json(upload_progress)

async def process_files(files: List[UploadFile], db: Session):
    global upload_progress
    upload_progress["total"] = len(files)
    upload_progress["completed"] = 0
    await notify_progress()
    
    for i in range(0, len(files), 5):  # Xử lý 5 file một lần
        batch = files[i:i + 5]
        tasks = []
        for file in batch:
            tasks.append(handle_file(file, db))
        await asyncio.gather(*tasks)
        upload_progress["completed"] += len(batch)
        await notify_progress()

async def handle_file(file: UploadFile, db: Session):
    file_hash = compute_file_hash(file.file)
    existing_file = db.query(FileRecord).filter(FileRecord.hash == file_hash).first()
    
    if existing_file:
        return  # Bỏ qua file trùng
    
    file_location = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_location, "wb") as f:
        f.write(file.file.read())
    
    new_file = FileRecord(hash=file_hash, filename=file.filename)
    db.add(new_file)
    db.commit()

@app.post("/upload/")
async def upload_files(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    background_tasks.add_task(process_files, files, db)
    return {"message": "Upload started in background"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_websockets.remove(websocket)

@app.get("/", response_class=HTMLResponse)
async def main():
    return """
    <html>
        <body>
            <h2>Upload Files</h2>
            <form id="uploadForm" action="/upload/" method="post" enctype="multipart/form-data">
                <input type="file" name="files" multiple>
                <button type="submit">Upload</button>
            </form>
            <div id="progress">Progress: 0 / 0</div>
            <script>
                let socket = new WebSocket("ws://" + window.location.host + "/ws");
                socket.onmessage = function(event) {
                    let data = JSON.parse(event.data);
                    document.getElementById('progress').innerText = `Progress: ${data.completed} / ${data.total}`;
                };
            </script>
        </body>
    </html>
    """
