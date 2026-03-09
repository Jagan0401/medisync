from config.db import db

print("Connected to MongoDB")

collections = db.list_collection_names()
print(collections)