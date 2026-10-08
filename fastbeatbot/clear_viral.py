import asyncio
from firebase_service import db

async def clear_viral_shorts():
    if not db:
        print("No DB connected.")
        return
        
    try:
        print("Fetching documents in 'viral_shorts'...")
        docs = db.collection('viral_shorts').stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        print(f"Successfully deleted {count} documents from 'viral_shorts'.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(clear_viral_shorts())
