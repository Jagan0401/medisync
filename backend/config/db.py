import os
from pathlib import Path

import certifi
from dotenv import load_dotenv
from pymongo import MongoClient

# Ensure .env is loaded even if db.py is imported before settings.py
load_dotenv(Path(__file__).resolve().parent.parent / '.env')

MONGO_URI = os.environ.get('MONGO_URI', '')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'medisync_db')

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client[MONGO_DB_NAME]