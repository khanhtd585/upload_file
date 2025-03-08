mkdir -p /mnt/ssd/upload_file/asset
cd /mnt/ssd/upload_file
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py