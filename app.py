from fastapi import FastAPI, File, UploadFile, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, Column, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import hashlib
import os
from typing import List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

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

@app.post("/upload/")
async def upload_files(files: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    global upload_progress
    upload_progress["total"] += len(files)
    
    responses = []
    for file in files:
        file_hash = compute_file_hash(file.file)
        existing_file = db.query(FileRecord).filter(FileRecord.hash == file_hash).first()

        if existing_file:
            upload_progress["completed"] += 1
            responses.append({"message": "File already exists", "filename": file.filename})
            continue
        
        file_location = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_location, "wb") as f:
            f.write(file.file.read())

        new_file = FileRecord(hash=file_hash, filename=file.filename)
        db.add(new_file)
        db.commit()

        upload_progress["completed"] += 1
        responses.append({"message": "File uploaded successfully", "filename": file.filename})
    
    return responses

@app.get("/progress/")
async def get_progress():
    return upload_progress

@app.get("/", response_class=HTMLResponse)
async def main():
    with open("templates/index.html", "r", encoding="utf-8") as file:
        return HTMLResponse(content=file.read())
