mkdir -p /mnt/ssd/uploads_service/statics/uploads
cd /mnt/ssd/uploads_service/upload_file
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py