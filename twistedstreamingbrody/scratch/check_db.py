import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase-credentials.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

print("--- COLLECTIONS ---")
collections = db.collections()
for col in collections:
    print(f"Collection: {col.id}")

print("\n--- SAMPLE FROM 'videos' ---")
docs = db.collection('videos').limit(5).get()
for doc in docs:
    print(f"ID: {doc.id} => {doc.to_dict()}")

print("\n--- SAMPLE FROM 'categories' ---")
docs = db.collection('categories').limit(5).get()
for doc in docs:
    print(f"ID: {doc.id} => {doc.to_dict()}")
