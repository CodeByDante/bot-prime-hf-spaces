import os
import cv2
import urllib.request

def score_frame(frame, face_cascade, anime_face_cascade, fullbody_cascade, upperbody_cascade):
    if frame is None:
        return -2000.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = gray.mean()
    if mean_brightness < 40 or mean_brightness > 225:
        return -1000.0
    variance = gray.var()
    if variance < 150:
        return -500.0
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    score = sharpness / 100.0
    
    h, w = gray.shape[:2]
    scale = 400.0 / w if w > 400 else 1.0
    if w > 400:
        gray_small = cv2.resize(gray, (400, int(h * scale)))
    else:
        gray_small = gray
        
    if not fullbody_cascade.empty():
        min_w, min_h = max(10, int(40 * scale)), max(10, int(100 * scale))
        full_bodies = fullbody_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=1, minSize=(min_w, min_h))
        score += len(full_bodies) * 300.0
        
    if not upperbody_cascade.empty():
        min_w, min_h = max(10, int(40 * scale)), max(10, int(80 * scale))
        upper_bodies = upperbody_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=1, minSize=(min_w, min_h))
        score += len(upper_bodies) * 100.0
        
    if anime_face_cascade and not anime_face_cascade.empty():
        min_sz = max(10, int(30 * scale))
        anime_faces = anime_face_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=2, minSize=(min_sz, min_sz))
        score += len(anime_faces) * 150.0
        
    if not face_cascade.empty():
        min_sz = max(10, int(30 * scale))
        human_faces = face_cascade.detectMultiScale(gray_small, scaleFactor=1.1, minNeighbors=2, minSize=(min_sz, min_sz))
        score += len(human_faces) * 50.0
        
    return score


def capture_frames_from_stream(stream_url, timestamps):
    # Resolver la ruta del archivo XML en el directorio base del proyecto
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ANIME_CASCADE_PATH = os.path.join(BASE_DIR, 'lbpcascade_animeface.xml')
    
    if not os.path.exists(ANIME_CASCADE_PATH):
        print("   • Descargando lbpcascade_animeface.xml para detección de personajes anime...")
        try:
            url = 'https://raw.githubusercontent.com/nagadomi/lbpcascade_animeface/master/lbpcascade_animeface.xml'
            urllib.request.urlretrieve(url, ANIME_CASCADE_PATH)
        except Exception as e:
            print(f"   • [Error] No se pudo descargar el cascade de anime: {e}")
            
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    fullbody_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_fullbody.xml')
    upperbody_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_upperbody.xml')
    anime_face_cascade = cv2.CascadeClassifier(ANIME_CASCADE_PATH) if os.path.exists(ANIME_CASCADE_PATH) else None

    cap = cv2.VideoCapture(stream_url)
    if not cap.isOpened():
        print("\033[91m[Error] OpenCV no pudo abrir la URL del streaming.\033[0m")
        return []

    captures = []
    for idx, ts in enumerate(timestamps):
        print(f"   • Obteniendo captura {idx+1}/{len(timestamps)} alrededor de {ts:.2f}s...")
        
        # 1. Intentar el timestamp exacto primero
        cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000.0)
        ret, frame = cap.read()
        score = -999999.0
        
        if ret:
            score = score_frame(frame, face_cascade, anime_face_cascade, fullbody_cascade, upperbody_cascade)
            # Si el frame pasa los filtros básicos (no es negro ni borroso), lo tomamos de inmediato
            if score > -500.0:
                captures.append((ts, frame))
                print(f"     ✓ Elegido frame exacto a los {ts:.2f}s (Score: {score:.1f})")
                continue
        
        # 2. Si falló el filtro básico o no se pudo leer, buscamos candidatos alternativos
        print(f"     ⚠ Frame exacto a los {ts:.2f}s es de baja calidad (Score: {score if ret else 'N/A'}). Buscando alternativa...")
        best_frame = frame if ret else None
        best_score = score if ret else -999999.0
        best_ts = ts
        
        for offset in [-2.0, 2.0]:
            c_ts = max(0.0, ts + offset)
            cap.set(cv2.CAP_PROP_POS_MSEC, c_ts * 1000.0)
            ret_c, frame_c = cap.read()
            if ret_c:
                score_c = score_frame(frame_c, face_cascade, anime_face_cascade, fullbody_cascade, upperbody_cascade)
                if score_c > best_score:
                    best_score = score_c
                    best_frame = frame_c
                    best_ts = c_ts
                    
        if best_frame is not None:
            captures.append((best_ts, best_frame))
            print(f"     ✓ Elegido frame alternativo a los {best_ts:.2f}s (Score: {best_score:.1f})")
        else:
            if ret:
                captures.append((ts, frame))
                print(f"     ⚠ Fallback al frame original a los {ts:.2f}s")
                
    cap.release()
    return captures
