import os

from pymongo import MongoClient

MONGO_URI = os.environ.get('MONGO_URI', '')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'medisync_db')

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]