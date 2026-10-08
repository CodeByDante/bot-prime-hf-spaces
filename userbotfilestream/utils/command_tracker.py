import os
import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USAGE_FILE = os.path.join(BASE_DIR, "command_usage.json")

# Mapeo de alias a nombres canónicos de comandos
CMD_MAPPING = {
    "ping": "ping",
    "info": "info",
    "help": "menu",
    "ayuda": "menu",
    "menu": "menu",
    "lista": "lista",
    "start": "lista",
    "capturas": "capturas",
    "capture": "capturas",
    "captura": "capturas",
    "sinopsis": "sinopsis",
    "repetidos": "repetidos",
    "duplicados": "repetidos",
    "duplicado": "repetidos",
    "similares": "repetidos",
    "limpiar": "limpiar",
    "clean": "limpiar",
    "clear": "limpiar",
    "elimina_duplicados": "elimina_duplicados",
    "borrar_duplicados": "elimina_duplicados",
    "eliminar_mensaje_de_portada": "eliminar_mensaje_de_portada",
    "elimina_spam_fijar": "elimina_spam_fijar",
    "renvio_ordenador": "renvio_ordenador",
    "reenvio_ordenador": "renvio_ordenador",
    "eliminar_etiqueta_de_renvio": "eliminar_etiqueta_de_renvio",
    "quitar_etiqueta_de_renvio": "eliminar_etiqueta_de_renvio",
    "buscar_codigos_jav": "buscar_codigos_jav",
    "portada_jav": "portada_jav",
    "code_duplicado": "code_duplicado",
    "jav_sin_code": "jav_sin_code",
    "name_actriz": "name_actriz",
    "etiquetado_de_actriz": "etiquetado_de_actriz",
    "etiquetado_actriz": "etiquetado_de_actriz",
    "lista_de_actriz": "lista_de_actriz",
    "lista_actriz": "lista_de_actriz",
    "albun_maker_video": "albun_maker_video",
    "album_maker_video": "albun_maker_video",
    "albun_maker_imagenes": "albun_maker_imagenes",
    "album_maker_imagenes": "albun_maker_imagenes",
    "albun_maker": "albun_maker",
    "album_maker": "albun_maker",
    "albun_directo_video": "albun_directo_video",
    "album_directo_video": "albun_directo_video",
    "albun_directo_imagenes": "albun_directo_imagenes",
    "album_directo_imagenes": "albun_directo_imagenes",
    "albun_directo_imagen": "albun_directo_imagenes",
    "album_directo_imagen": "albun_directo_imagenes",
    "eliminar_descripcion_video": "eliminar_descripcion_video",
    "quitar_descripcion_video": "eliminar_descripcion_video",
    "eliminar_descripcion_imagen": "eliminar_descripcion_imagen",
    "quitar_descripcion_imagen": "eliminar_descripcion_imagen",
    "eliminar_descripcion": "eliminar_descripcion",
    "quitar_descripcion": "eliminar_descripcion",
    "eliminador_definitivo": "eliminador_definitivo",
    "eliminador_definitivo_prime": "eliminador_definitivo_prime",
    "registro_id": "registro_id",
    "comparador_de_codigos": "comparador_de_codigos",
    "vip": "vip",
    "restaurar_actriz": "restaurar_actriz",
    "respaldo": "respaldo"
}

def load_usage():
    if os.path.exists(USAGE_FILE):
        try:
            with open(USAGE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Tracker] Error cargando command_usage.json: {e}")
    return {}

def save_usage(data):
    try:
        with open(USAGE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"[Tracker] Error guardando command_usage.json: {e}")

def get_canonical_name(cmd_raw):
    cmd_clean = cmd_raw.lower().strip()
    # Para comandos dinámicos como borrar_copia_12345
    if cmd_clean.startswith("eliminar_copia_") or cmd_clean.startswith("borrar_copia_") or cmd_clean.startswith("del_copy_"):
        return "repetidos" # Asociarlo al módulo de repetidos
    return CMD_MAPPING.get(cmd_clean, cmd_clean)

def increment_command_usage(cmd_raw):
    canonical = get_canonical_name(cmd_raw)
    if canonical in ["lista", "vip"]:
        return
    data = load_usage()
    data[canonical] = data.get(canonical, 0) + 1
    save_usage(data)
    print(f"[Tracker] Uso incrementado para '{canonical}': {data[canonical]}")

def get_command_count(cmd_raw):
    canonical = get_canonical_name(cmd_raw)
    data = load_usage()
    return data.get(canonical, 0)
