import img2pdf
import requests
import sys
import json
import os
from concurrent.futures import ThreadPoolExecutor

def download_image(args):
    url, index, total = args
    try:
        response = requests.get(url, timeout=15, headers={'User-Agent': 'Mozilla/5.0'})
        if response.status_code == 200:
            # Imprimimos progreso para Node.js
            print(f"PROGRESS:IMAGE_DONE", flush=True)
            return index, response.content
    except Exception as e:
        print(f"DEBUG: Error en imagen {index}: {e}", flush=True)
    return index, None

def create_pdf(urls, output_name):
    total = len(urls)
    print(f"DEBUG: Iniciando descarga paralela de {total} imágenes...", flush=True)
    
    # Descarga en paralelo (50 hilos a la vez para saturar la conexión)
    # Esto es lo que lo hace igual de rápido que el ZIP
    with ThreadPoolExecutor(max_workers=50) as executor:
        results = list(executor.map(download_image, [(url, i, total) for i, url in enumerate(urls)]))

    # Ordenamos las imágenes por su índice original para que el manga no esté desordenado
    results.sort(key=lambda x: x[0])
    img_data = [data for index, data in results if data is not None]

    if img_data:
        print("DEBUG: Empaquetando PDF...", flush=True)
        with open(output_name, "wb") as f:
            # img2pdf es ultra rápido porque no re-comprime
            f.write(img2pdf.convert(img_data))
        print("STATUS:SUCCESS", flush=True)
    else:
        print("STATUS:ERROR", flush=True)

if __name__ == "__main__":
    try:
        input_data = sys.stdin.read()
        if not input_data:
            sys.exit(1)
        data = json.loads(input_data)
        create_pdf(data['urls'], data['output'])
    except Exception as e:
        print(f"DEBUG: Error crítico: {e}", flush=True)
