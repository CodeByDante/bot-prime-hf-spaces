import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase-credentials.json")
if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
db = firestore.client()

print("--- BOT SETTINGS ---")
docs = db.collection('bot_settings').get()
for doc in docs:
    print(f"ID: {doc.id} => {doc.to_dict()}")

print("\n--- BOT DATA ---")
docs = db.collection('bot_data').get()
for doc in docs:
    print(f"ID: {doc.id} => {doc.to_dict()}")
