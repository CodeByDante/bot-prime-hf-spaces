import os
import sys
import json
import asyncio
import re

# Ensure standard output can print Unicode characters on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)

from utils.database import DB, db_firestore

def extract_actress_and_hashtag(title):
    if not title:
        return None, None
        
    # Match pattern like: "actriz: Nana Taipei - #Nana_Taipei"
    match = re.search(r'actriz:\s*([^-\n#]+)(?:-\s*(#\w+))?', title, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        hashtag = match.group(2)
        if hashtag:
            hashtag = hashtag.strip()
        else:
            # Generate hashtag if missing
            hashtag = "#" + name.replace(" ", "_")
        return name, hashtag
        
    # Fallback to finding any hashtag in the title
    hashtags = re.findall(r'#(\w+)', title)
    if hashtags:
        # Take the first one as actress name
        name = hashtags[0].replace("_", " ")
        hashtag = "#" + hashtags[0]
        return name, hashtag
        
    return None, None

async def main():
    print("🤖 Conectando a la base de datos...")
    
    if db_firestore is None:
        print("⚠️ Firebase no está activo. Leyendo cache local...")
        cache_file = os.path.join(PROJECT_DIR, "videos_cache.json")
        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            print("❌ No se encontró videos_cache.json local.")
            return
    else:
        print("🔥 Conectando a Firebase Firestore...")
        try:
            loop = asyncio.get_event_loop()
            def fetch_firebase():
                docs = db_firestore.collection("channels").stream()
                channels = {}
                for doc in docs:
                    channels[doc.id] = doc.to_dict()
                return {"channels": channels}
            data = await asyncio.wait_for(loop.run_in_executor(None, fetch_firebase), timeout=15.0)
        except Exception as e:
            print(f"❌ Error al conectar a Firebase: {e}. Usando cache local...")
            cache_file = os.path.join(PROJECT_DIR, "videos_cache.json")
            if os.path.exists(cache_file):
                with open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            else:
                print("❌ No se encontró videos_cache.json local.")
                return

    all_actresses = {}
    channel_list = []
    
    for chat_id, ch_data in data.get("channels", {}).items():
        channel_title = ch_data.get("channel_title", "Canal Privado")
        videos = ch_data.get("videos", [])
        
        channel_list.append({
            "id": chat_id,
            "title": channel_title,
            "count": len(videos)
        })
        
        for v in videos:
            title = v.get("title", "")
            name, hashtag = extract_actress_and_hashtag(title)
            if name and hashtag:
                key = hashtag.lower()
                if key not in all_actresses:
                    all_actresses[key] = {
                        "name": name,
                        "hashtag": hashtag,
                        "channels": set()
                    }
                all_actresses[key]["channels"].add(channel_title)
                
    # Format and save
    actress_list = sorted(all_actresses.values(), key=lambda x: x["name"])
    
    # Save as JSON
    json_path = os.path.join(PROJECT_DIR, "actrices_exportadas.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump([
            {
                "name": item["name"],
                "hashtag": item["hashtag"],
                "channels": list(item["channels"])
            }
            for item in actress_list
        ], f, ensure_ascii=False, indent=4)
        
    # Save as TXT list of hashtags
    txt_path = os.path.join(PROJECT_DIR, "hashtags_actrices.txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for item in actress_list:
            f.write(f"{item['hashtag']} ({item['name']}) - Canales: {', '.join(item['channels'])}\n")
            
    # Save as a simple hashtag list
    txt_simple_path = os.path.join(PROJECT_DIR, "hashtags_simple.txt")
    with open(txt_simple_path, "w", encoding="utf-8") as f:
        for item in actress_list:
            f.write(f"{item['hashtag']}\n")
            
    print("\n========================================================")
    print("📈 RESUMEN DE LA BASE DE DATOS:")
    print("========================================================")
    print(f"Canales escaneados: {len(channel_list)}")
    for ch in channel_list:
        print(f"  • {ch['title']} (ID: {ch['id']}) - {ch['count']} videos")
    print(f"Total de actrices únicas encontradas: {len(actress_list)}")
    print("========================================================")
    print(f"✅ Archivos generados con éxito:")
    print(f"  1. JSON con detalles: {json_path}")
    print(f"  2. TXT descriptivo: {txt_path}")
    print(f"  3. TXT simple (solo hashtags): {txt_simple_path}")
    print("========================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
