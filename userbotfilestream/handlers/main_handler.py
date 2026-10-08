from core.client import client
from telethon import events
import asyncio

from handlers.ping import handle_ping, handle_help
from handlers.list import handle_list, handle_info, handle_vip
from handlers.capturas import procesar_comando_capturas
from handlers.sinopsis import procesar_comando_sinopsis
from handlers.repetidos import (
    procesar_comando_repetidos,
    borrar_copia_por_id,
    procesar_comando_limpiar,
    procesar_comando_eliminar_duplicados,
    eliminar_mensaje_de_portada,
    elimina_spam_fijar
)
from handlers.renvio_ordenador import procesar_comando_renvio_ordenador
from handlers.quitar_etiqueta_de_renvio import procesar_quitar_etiqueta_de_renvio
from handlers.buscar_codigos_jav import procesar_comando_buscar_codigos_jav
from handlers.portada_jav import procesar_comando_portada_jav
from handlers.code_duplicado import procesar_comando_code_duplicado
from handlers.jav_sin_code import procesar_comando_jav_sin_code
from handlers.name_actriz import procesar_comando_name_actriz
from handlers.etiquetado_de_actriz import procesar_comando_etiquetado_actriz
from handlers.lista_de_actriz import procesar_comando_lista_de_actriz
from handlers.album_maker import procesar_comando_album_maker_video, procesar_comando_album_maker_imagenes, procesar_comando_album_maker
from handlers.album_directo import procesar_comando_album_directo_video, procesar_comando_album_directo_imagenes
from handlers.quitar_descripcion import procesar_quitar_descripcion_video, procesar_quitar_descripcion_imagen, procesar_quitar_descripcion
from handlers.eliminador_definitivo import procesar_eliminador_definitivo, procesar_eliminador_definitivo_prime
from handlers.registro_id import procesar_registro_id
from handlers.comparador_de_codigos import procesar_comando_comparador_de_codigos
from handlers.duplicados_miniatura import procesar_comando_duplicados_miniatura, procesar_comando_elimina_duplicados_miniatura, procesar_comando_elimina_duplicados_especial_miniatura
from handlers.duplicados_modo_avanzado import procesar_comando_duplicados_modo_avanzado, procesar_comando_elimina_duplicados_modo_avanzado
from handlers.busqueda import procesar_comando_busqueda
from handlers.busqueda_inversa_bot import procesar_comando_busqueda_inversa_bot
from handlers.duplicados_tiempo import (
    procesar_comando_duplicados_tiempo,
    procesar_comando_elimina_duplicados_tiempo
)
from handlers.descargar import procesar_comando_descargar
from handlers.prime_video import procesar_comando_prime_video, procesar_comando_limpiar_catalogo, procesar_comando_prime_imagenes
from handlers.zip_imagenes import procesar_comando_zip_imagenes
from handlers.manga_flow import (
    handle_manga_flow,
    handle_manga_flow_pdf,
    handle_manga_flow_zip,
    handle_manga_flow_webp,
    handle_manga_flow_pdf_webp,
    handle_manga_flow_zip_webp
)
from handlers.renvio_r import procesar_comando_r
from handlers.renombrar_v import procesar_comando_v
from handlers.renombrar_p import procesar_comando_p
from handlers.captura_single_c import procesar_comando_c
from handlers.favorito import procesar_comando_f









@client.on(events.NewMessage(pattern=r'^/(f|c|p|v|r|ping|info|vip|capturas?|capture|sinopsis|help|ayuda|menu|lista|start|repetidos|duplicados_modo_avanzado|duplicados_miniatura|duplicados?|similares|eliminar_copia_\d+|borrar_copia_\d+|del_copy_\d+|limpiar|clean|clear|elimina_duplicados_modo_avanzado|elimina_duplicados_especial_miniatura|elimina_duplicados_miniatura|elimina_duplicados|borrar_duplicados|eliminar_mensaje_de_portada|elimina_spam_fijar|renvio_ordenador|reenvio_ordenador|eliminar_etiqueta_de_renvio|quitar_etiqueta_de_renvio|buscar_codigos_jav|portada_jav|code_duplicado|jav_sin_code|name_actriz|etiquetado_de_actriz|etiquetado_actriz|lista_de_actriz|lista_actriz|albun_maker_video|album_maker_video|albun_maker_imagenes|album_maker_imagenes|albun_maker|album_maker|albun_directo_video|album_directo_video|albun_directo_imagenes|album_directo_imagenes|albun_directo_imagen|album_directo_imagen|eliminar_descripcion_video|quitar_descripcion_video|eliminar_descripcion_imagen|quitar_descripcion_imagen|eliminar_descripcion|quitar_descripcion|eliminador_definitivo|eliminador_definitivo_prime|registro_id|comparador_de_codigos|busqueda|duplicacion_tiempo|duplicacion_tempo|duplicados_tiempo|duplicado_tiempo|duplicacion|elimina_duplicados_tiempo|eliminar_duplicados_tiempo|elimina_duplicados_tempo|eliminar_duplicados_tempo|descargar_video|descargar_imagen|zip_imagenes?|zip_photos?|descargar_zip_imagenes|prime_video|prime_imagenes|limpiar_catalogo|manga_flow|manga_flow_pdf|manga_flow_zip|manga_flow_webp|manga_flow_zip_webp|manga_flow_pdf_webp)(?:@\w+)?(?:\s+.*)?$', incoming=False))
async def command_dispatcher(event):
    if event.is_private:
        me = await client.get_me()
        if event.chat_id != me.id:
            return
        
    cmd = event.pattern_match.group(1).lower()
    
    # Registrar uso del comando
    try:
        from utils.command_tracker import increment_command_usage
        increment_command_usage(cmd)
    except Exception as e:
        print(f"[Tracker Error] No se pudo registrar el uso del comando {cmd}: {e}")
    
    if cmd == "r":
        asyncio.create_task(procesar_comando_r(event))
        
    elif cmd == "c":
        asyncio.create_task(procesar_comando_c(event))
        
    elif cmd == "v":
        asyncio.create_task(procesar_comando_v(event))
        
    elif cmd == "p":
        asyncio.create_task(procesar_comando_p(event))
        
    elif cmd == "f":
        asyncio.create_task(procesar_comando_f(event))

        
    elif cmd == "ping":
        await handle_ping(event)
        
    elif cmd == "info":
        await handle_info(event)
        
    elif cmd in ["help", "ayuda", "menu"]:
        await handle_help(event)
        
    elif cmd in ["capturas", "capture", "captura"]:
        # Ejecutar en segundo plano para no bloquear el loop del cliente
        asyncio.create_task(procesar_comando_capturas(event))
        
    elif cmd == "sinopsis":
        # Ejecutar en segundo plano
        asyncio.create_task(procesar_comando_sinopsis(event))
        
    elif cmd in ["lista", "start"]:
        await handle_list(event)
        
    elif cmd == "vip":
        await handle_vip(event)
        
    elif cmd == "busqueda":
        asyncio.create_task(procesar_comando_busqueda(event))
        
    elif cmd in ["repetidos", "duplicados", "duplicado", "similares"] :
        # Ejecutar en segundo plano
        asyncio.create_task(procesar_comando_repetidos(event))
        
    elif cmd == "duplicados_miniatura":
        asyncio.create_task(procesar_comando_duplicados_miniatura(event))
        
    elif cmd == "duplicados_modo_avanzado":
        asyncio.create_task(procesar_comando_duplicados_modo_avanzado(event))
        
    elif cmd in ["duplicacion_tiempo", "duplicacion_tempo", "duplicados_tiempo", "duplicado_tiempo", "duplicacion"]:
        asyncio.create_task(procesar_comando_duplicados_tiempo(event))
        
    elif cmd in ["elimina_duplicados_tiempo", "eliminar_duplicados_tiempo", "elimina_duplicados_tempo", "eliminar_duplicados_tempo"]:
        asyncio.create_task(procesar_comando_elimina_duplicados_tiempo(event))

        
    elif cmd.startswith("eliminar_copia_") or cmd.startswith("borrar_copia_") or cmd.startswith("del_copy_"):
        # Extraer el ID del mensaje
        try:
            msg_id = int(cmd.split("_")[-1])
            asyncio.create_task(borrar_copia_por_id(event, msg_id))
        except ValueError:
            pass
            
    elif cmd in ["limpiar", "clean", "clear"]:
        asyncio.create_task(procesar_comando_limpiar(event))
        
    elif cmd == "limpiar_catalogo":
        asyncio.create_task(procesar_comando_limpiar_catalogo(event))
        
    elif cmd in ["elimina_duplicados", "borrar_duplicados"]:
        asyncio.create_task(procesar_comando_eliminar_duplicados(event))
        
    elif cmd == "elimina_duplicados_miniatura":
        asyncio.create_task(procesar_comando_elimina_duplicados_miniatura(event))
        
    elif cmd == "elimina_duplicados_especial_miniatura":
        asyncio.create_task(procesar_comando_elimina_duplicados_especial_miniatura(event))
        
    elif cmd == "elimina_duplicados_modo_avanzado":
        asyncio.create_task(procesar_comando_elimina_duplicados_modo_avanzado(event))

        
    elif cmd == "eliminar_mensaje_de_portada":
        asyncio.create_task(eliminar_mensaje_de_portada(event))
        
    elif cmd == "elimina_spam_fijar":
        asyncio.create_task(elimina_spam_fijar(event))

    elif cmd in ["renvio_ordenador", "reenvio_ordenador"]:
        asyncio.create_task(procesar_comando_renvio_ordenador(event))

    elif cmd in ["eliminar_etiqueta_de_renvio", "quitar_etiqueta_de_renvio"]:
        asyncio.create_task(procesar_quitar_etiqueta_de_renvio(event))

    elif cmd == "buscar_codigos_jav":
        asyncio.create_task(procesar_comando_buscar_codigos_jav(event))

    elif cmd == "portada_jav":
        asyncio.create_task(procesar_comando_portada_jav(event))

    elif cmd == "code_duplicado":
        asyncio.create_task(procesar_comando_code_duplicado(event))

    elif cmd == "jav_sin_code":
        asyncio.create_task(procesar_comando_jav_sin_code(event))

    elif cmd == "name_actriz":
        asyncio.create_task(procesar_comando_name_actriz(event))

    elif cmd in ["etiquetado_de_actriz", "etiquetado_actriz"]:
        asyncio.create_task(procesar_comando_etiquetado_actriz(event))

    elif cmd in ["lista_de_actriz", "lista_actriz"]:
        asyncio.create_task(procesar_comando_lista_de_actriz(event))

    elif cmd in ["albun_maker_video", "album_maker_video"]:
        asyncio.create_task(procesar_comando_album_maker_video(event))

    elif cmd in ["albun_maker_imagenes", "album_maker_imagenes"]:
        asyncio.create_task(procesar_comando_album_maker_imagenes(event))

    elif cmd in ["albun_maker", "album_maker"]:
        asyncio.create_task(procesar_comando_album_maker(event))

    elif cmd in ["albun_directo_video", "album_directo_video"]:
        asyncio.create_task(procesar_comando_album_directo_video(event))

    elif cmd in ["albun_directo_imagenes", "album_directo_imagenes", "albun_directo_imagen", "album_directo_imagen"]:
        asyncio.create_task(procesar_comando_album_directo_imagenes(event))

    elif cmd in ["eliminar_descripcion_video", "quitar_descripcion_video"]:
        asyncio.create_task(procesar_quitar_descripcion_video(event))

    elif cmd in ["eliminar_descripcion_imagen", "quitar_descripcion_imagen"]:
        asyncio.create_task(procesar_quitar_descripcion_imagen(event))

    elif cmd in ["eliminar_descripcion", "quitar_descripcion"]:
        asyncio.create_task(procesar_quitar_descripcion(event))

    elif cmd == "eliminador_definitivo":
        asyncio.create_task(procesar_eliminador_definitivo(event))

    elif cmd == "eliminador_definitivo_prime":
        asyncio.create_task(procesar_eliminador_definitivo_prime(event))

    elif cmd == "registro_id":
        asyncio.create_task(procesar_registro_id(event))

    elif cmd == "comparador_de_codigos":
        asyncio.create_task(procesar_comando_comparador_de_codigos(event))

    elif cmd == "descargar_video":
        asyncio.create_task(procesar_comando_descargar(event, "video"))

    elif cmd == "descargar_imagen":
        asyncio.create_task(procesar_comando_descargar(event, "image"))

    elif cmd in ["zip_imagenes", "zip_imagen", "zip_photos", "zip_photo", "descargar_zip_imagenes"]:
        asyncio.create_task(procesar_comando_zip_imagenes(event))

    elif cmd == "prime_video":
        asyncio.create_task(procesar_comando_prime_video(event))

    elif cmd == "prime_imagenes":
        asyncio.create_task(procesar_comando_prime_imagenes(event))

    elif cmd == "manga_flow":
        asyncio.create_task(handle_manga_flow(event))
    elif cmd == "manga_flow_pdf":
        asyncio.create_task(handle_manga_flow_pdf(event))
    elif cmd == "manga_flow_zip":
        asyncio.create_task(handle_manga_flow_zip(event))
    elif cmd == "manga_flow_webp":
        asyncio.create_task(handle_manga_flow_webp(event))
    elif cmd == "manga_flow_pdf_webp":
        asyncio.create_task(handle_manga_flow_pdf_webp(event))
    elif cmd == "manga_flow_zip_webp":
        asyncio.create_task(handle_manga_flow_zip_webp(event))


# Despachador dedicado para búsqueda inversa en cualquier parte del texto (mensajes nuevos y editados)
@client.on(events.NewMessage(pattern=r'(?i)/busqueda_inversa_bot', incoming=False))
@client.on(events.MessageEdited(pattern=r'(?i)/busqueda_inversa_bot', incoming=False))
async def dispatcher_busqueda_inversa(event):
    try:
        from utils.command_tracker import increment_command_usage
        increment_command_usage("busqueda_inversa_bot")
    except Exception as e:
        print(f"[Tracker Error] No se pudo registrar el uso del comando busqueda_inversa_bot: {e}")
    asyncio.create_task(procesar_comando_busqueda_inversa_bot(event))


# Importar sincronización en tiempo real para activar sus event listeners globales
import handlers.realtime_sync



