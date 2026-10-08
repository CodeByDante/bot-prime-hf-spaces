import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase-credentials.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

print("--- ALL VIDEOS ---")
docs = db.collection('videos').get()
for doc in docs:
    d = doc.to_dict()
    print(f"ID: {doc.id} | Title: {d.get('title')} | Section: {d.get('section')} | Fields: {list(d.keys())}")
