import asyncio
from core.client import client
from utils.command_tracker import get_command_count

CATEGORIES = [
    "Control y Ayuda",
    "Agrupar / Desagrupar (Álbumes)",
    "Capturas y Sinopsis",
    "JAV (Japonesas)",
    "Actrices",
    "Manga Flow (Original)",
    "Manga Flow (WebP)",
    "Atajos Rápidos",
    "Limpieza y Eliminación"
]

COMMANDS_METADATA = [
    {
        "name": "ping",
        "title": "/ping",
        "usage": "Comprueba si el bot está activo.",
        "category": "Control y Ayuda"
    },
    {
        "name": "f",
        "title": "/f",
        "usage": "Añade #favorito a la descripción de un mensaje.",
        "category": "Atajos Rápidos"
    },
    {
        "name": "menu",
        "title": "/menu",
        "usage": "Muestra el menú rápido.",
        "category": "Control y Ayuda"
    },
    {
        "name": "lista",
        "title": "/lista",
        "usage": "Muestra la lista de comandos.",
        "category": "Control y Ayuda"
    },
    {
        "name": "info",
        "title": "/info",
        "usage": "Información de borrado automático.",
        "category": "Control y Ayuda"
    },
    {
        "name": "vip",
        "title": "/vip",
        "usage": "Comandos exclusivos de este chat.",
        "category": "Control y Ayuda"
    },
    {
        "name": "registro_id",
        "title": "/registro_id",
        "usage": "Registra los IDs reales de los canales.",
        "category": "Control y Ayuda"
    },
    {
        "name": "busqueda",
        "title": "/busqueda [consulta]",
        "usage": "Busca por duración o peso.",
        "category": "Control y Ayuda"
    },
    {
        "name": "busqueda_inversa_bot",
        "title": "/busqueda_inversa_bot",
        "usage": "Búsqueda inversa en el historial.",
        "category": "Control y Ayuda"
    },
    {
        "name": "descargar_video",
        "title": "/descargar_video [cantidad]",
        "usage": "Genera enlaces para descargar videos.",
        "category": "Control y Ayuda"
    },
    {
        "name": "descargar_imagen",
        "title": "/descargar_imagen [cantidad]",
        "usage": "Genera enlaces para descargar imágenes.",
        "category": "Control y Ayuda"
    },
    {
        "name": "zip_imagenes",
        "title": "/zip_imagenes [cantidad]",
        "usage": "Comprime imágenes del canal en ZIP.",
        "category": "Control y Ayuda"
    },
    {
        "name": "prime_video",
        "title": "/prime_video",
        "usage": "Genera el catálogo web de videos.",
        "category": "Control y Ayuda"
    },
    {
        "name": "prime_imagenes",
        "title": "/prime_imagenes",
        "usage": "Genera el catálogo web de escenas.",
        "category": "Control y Ayuda"
    },
    {
        "name": "albun_maker_video",
        "title": "/albun_maker_video",
        "usage": "Agrupa videos en álbumes de 10.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "albun_maker_imagenes",
        "title": "/albun_maker_imagenes",
        "usage": "Agrupa imágenes en álbumes de 10.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "albun_maker",
        "title": "/albun_maker",
        "usage": "Agrupa fotos y videos en álbumes.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "albun_directo_video",
        "title": "/albun_directo_video",
        "usage": "Desagrupa álbumes de video.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "albun_directo_imagenes",
        "title": "/albun_directo_imagenes",
        "usage": "Desagrupa álbumes de fotos.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "renvio_ordenador",
        "title": "/renvio_ordenador",
        "usage": "Reenvía ordenado a @VideoAlbumMakerBot.",
        "category": "Agrupar / Desagrupar (Álbumes)"
    },
    {
        "name": "capturas",
        "title": "/capturas",
        "usage": "Genera capturas de pantalla de videos.",
        "category": "Capturas y Sinopsis"
    },
    {
        "name": "sinopsis",
        "title": "/sinopsis",
        "usage": "Agrega sinopsis a capturas (Hentaila VIP).",
        "exclusive_key": "hentaila_vip",
        "category": "Capturas y Sinopsis"
    },
    {
        "name": "buscar_codigos_jav",
        "title": "/buscar_codigos_jav",
        "usage": "Lista códigos JAV del canal.",
        "exclusive_key": "jav_premium",
        "category": "JAV (Japonesas)"
    },
    {
        "name": "portada_jav",
        "title": "/portada_jav",
        "usage": "Descarga y publica portadas JAV.",
        "exclusive_key": "jav_premium",
        "category": "JAV (Japonesas)"
    },
    {
        "name": "code_duplicado",
        "title": "/code_duplicado",
        "usage": "Reporta códigos JAV duplicados.",
        "category": "JAV (Japonesas)"
    },
    {
        "name": "comparador_de_codigos",
        "title": "/comparador_de_codigos",
        "usage": "Cuadro comparativo de códigos JAV.",
        "category": "JAV (Japonesas)"
    },
    {
        "name": "jav_sin_code",
        "title": "/jav_sin_code",
        "usage": "Lista videos sin código JAV.",
        "exclusive_key": "jav_regular",
        "category": "JAV (Japonesas)"
    },
    {
        "name": "name_actriz",
        "title": "/name_actriz",
        "usage": "Renombra videos con el nombre de actriz.",
        "category": "Actrices"
    },
    {
        "name": "etiquetado_de_actriz",
        "title": "/etiquetado_de_actriz",
        "usage": "Renombra y agrega hashtag de actriz.",
        "category": "Actrices"
    },
    {
        "name": "lista_de_actriz",
        "title": "/lista_de_actriz",
        "usage": "Lista hashtags de actrices sin repetir.",
        "category": "Actrices"
    },
    {
        "name": "v",
        "title": "/v",
        "usage": "Renombra videos en secuencia (Versión X).",
        "category": "Atajos Rápidos"
    },
    {
        "name": "p",
        "title": "/p",
        "usage": "Renombra imágenes en secuencia (Parte X).",
        "category": "Atajos Rápidos"
    },
    {
        "name": "c",
        "title": "/c",
        "usage": "Atajo rápido para captura singular.",
        "category": "Atajos Rápidos"
    },
    {
        "name": "r",
        "title": "/r",
        "usage": "Atajo rápido para reenvío de archivos.",
        "category": "Atajos Rápidos"
    },
    {
        "name": "eliminar_descripcion_video",
        "title": "/eliminar_descripcion_video",
        "usage": "Borra la descripción de los videos.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminar_descripcion_imagen",
        "title": "/eliminar_descripcion_imagen",
        "usage": "Borra la descripción de las imágenes.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminar_descripcion",
        "title": "/eliminar_descripcion",
        "usage": "Borra la descripción de fotos y videos.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminar_etiqueta_de_renvio",
        "title": "/eliminar_etiqueta_de_renvio",
        "usage": "Elimina la etiqueta de reenviado.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "repetidos",
        "title": "/repetidos",
        "usage": "Busca y reporta videos duplicados.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "duplicacion_tiempo",
        "title": "/duplicacion_tiempo",
        "usage": "Busca duplicados por duración exacta.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "elimina_duplicados_tiempo",
        "title": "/elimina_duplicados_tiempo",
        "usage": "Elimina duplicados por duración.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "duplicados_miniatura",
        "title": "/duplicados_miniatura",
        "usage": "Busca duplicados visuales por miniatura.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "elimina_duplicados_miniatura",
        "title": "/elimina_duplicados_miniatura",
        "usage": "Elimina duplicados por miniatura.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "duplicados_modo_avanzado",
        "title": "/duplicados_modo_avanzado",
        "usage": "Busca duplicados comparando fotogramas.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "elimina_duplicados_modo_avanzado",
        "title": "/elimina_duplicados_modo_avanzado",
        "usage": "Elimina duplicados detectados por fotogramas.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminar_mensaje_de_portada",
        "title": "/eliminar_mensaje_de_portada",
        "usage": "Borra avisos de actualización de portada.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "elimina_spam_fijar",
        "title": "/elimina_spam_fijar",
        "usage": "Borra avisos de mensajes fijados.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminador_definitivo",
        "title": "/eliminador_definitivo",
        "usage": "Borra mensajes originales de Twisted.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "eliminador_definitivo_prime",
        "title": "/eliminador_definitivo_prime",
        "usage": "Borra mensajes originales de origen.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "limpiar",
        "title": "/limpiar",
        "usage": "Borra todos los reportes del bot.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "limpiar_catalogo",
        "title": "/limpiar_catalogo",
        "usage": "Vacía el catálogo de videos del canal.",
        "category": "Limpieza y Eliminación"
    },
    {
        "name": "manga_flow",
        "title": "/manga_flow [ID]",
        "usage": "Envía manga en álbum usando enlaces originales.",
        "category": "Manga Flow (Original)"
    },
    {
        "name": "manga_flow_pdf",
        "title": "/manga_flow_pdf [ID]",
        "usage": "Envía manga en PDF usando enlaces originales.",
        "category": "Manga Flow (Original)"
    },
    {
        "name": "manga_flow_zip",
        "title": "/manga_flow_zip [ID]",
        "usage": "Envía manga comprimido en ZIP (originales).",
        "category": "Manga Flow (Original)"
    },
    {
        "name": "manga_flow_webp",
        "title": "/manga_flow_webp [ID]",
        "usage": "Envía manga en álbum usando enlaces WebP.",
        "category": "Manga Flow (WebP)"
    },
    {
        "name": "manga_flow_pdf_webp",
        "title": "/manga_flow_pdf_webp [ID]",
        "usage": "Envía manga en PDF usando enlaces WebP.",
        "category": "Manga Flow (WebP)"
    },
    {
        "name": "manga_flow_zip_webp",
        "title": "/manga_flow_zip_webp [ID]",
        "usage": "Envía manga en ZIP usando enlaces WebP.",
        "category": "Manga Flow (WebP)"
    }
]

async def handle_list(event):
    # Organizar comandos por categoría
    category_groups = {cat: [] for cat in CATEGORIES}
    for cmd in COMMANDS_METADATA:
        cat = cmd.get("category", "Otros")
        if cat not in category_groups:
            category_groups[cat] = []
        category_groups[cat].append(cmd)
        
    category_chunks = []
    
    for cat in CATEGORIES:
        cmds_in_cat = category_groups[cat]
        if not cmds_in_cat:
            continue
            
        cat_lines = [f"📂 **{cat}**"]
        
        # Ordenar comandos por cantidad de usos, excepto para las categorías de Manga Flow
        if cat in ["Manga Flow (Original)", "Manga Flow (WebP)"]:
            sorted_cmds = cmds_in_cat
        else:
            sorted_cmds = sorted(cmds_in_cat, key=lambda c: get_command_count(c["name"]))
        
        for cmd in sorted_cmds:
            title_raw = cmd['title']
            parts = title_raw.split(" ", 1)
            cmd_name = parts[0]
            rest_title = f" {parts[1]}" if len(parts) > 1 else ""
            
            # Formatear el comando en monoespaciado
            mono_title = f"`{cmd_name}`{rest_title}"
            cat_lines.append(f"• {mono_title} : {cmd['usage']}")
            
        category_chunks.append("\n".join(cat_lines))
        
    category_chunks.append("🌐 **Guía interactiva detallada:**\nhttps://telegra.ph/comandos-09-01")
    list_text = "\n\n".join(category_chunks)

    # Enviar en partes para evitar MessageTooLongError
    parts = list_text.split("\n\n")
    current_chunk = ""
    replies = []
    
    for part in parts:
        if len(current_chunk) + len(part) + 2 > 4000:
            if current_chunk.strip():
                try:
                    reply = await event.respond(current_chunk.strip(), link_preview=False)
                    replies.append(reply)
                except Exception as e:
                    print(f"Error enviando lista: {e}")
            current_chunk = part + "\n\n"
        else:
            current_chunk += part + "\n\n"
            
    if current_chunk.strip():
        try:
            reply = await event.respond(current_chunk.strip(), link_preview=False)
            replies.append(reply)
        except Exception as e:
            print(f"Error enviando lista: {e}")
        
    me = await client.get_me()
    if event.chat_id != me.id:
        await asyncio.sleep(40)
        to_delete = [event.id] + [r.id for r in replies if r]
        try:
            await client.delete_messages(event.chat_id, to_delete)
        except Exception:
            pass

async def handle_info(event):
    info_text = (
        "🤖 **Información de Mensajes y Desaparición (Bot Prime)** 🚀\n\n"
        "1. **El comando /lista**\n"
        "• **Tiempo para desaparecer:** 40 segundos.\n"
        "• **Comportamiento:** A los 40 segundos, el bot elimina tanto tu mensaje de comando (/lista) como el listado detallado que envió.\n"
        "• **Excepción:** Si envías /lista en tu chat de Mensajes Guardados (Saved Messages), el bot NO lo eliminará; allí se queda guardado para siempre para que puedas consultarlo o copiarlo cuando quieras.\n\n"
        "2. **Comandos y mensajes de estado que SÍ desaparecen automáticamente**\n"
        "Para mantener los canales limpios, los mensajes de estado (los mensajes iniciales de \"Buscando...\", \"Procesando...\") y el comando que tú escribiste se eliminan solos tras finalizar el proceso:\n"
        "• `/ping`: Desaparece a los 5 segundos (junto con la respuesta del bot).\n"
        "• `/menu` / `/ayuda` / `/help`: Desaparecen a los 15 segundos (junto con el menú de ayuda).\n"
        "• `/eliminar_mensaje_de_portada` / `/elimina_spam_fijar`: Desaparecen a los 5 segundos.\n"
        "• `/registro_id`: Desaparece a los 8 segundos.\n"
        "• `/eliminar_descripcion_video` / `/eliminar_descripcion_imagen` / `/eliminar_descripcion`: Desaparecen a los 8 segundos.\n"
        "• `/albun_maker` / `/albun_maker_video` / `/albun_maker_imagenes`: Desaparecen a los 8 segundos (después de agrupar y reenviar).\n"
        "• `/albun_directo_video` / `/albun_directo_imagenes`: Desaparecen a los 8 segundos (después de desagrupar).\n"
        "• `/eliminar_etiqueta_de_renvio` / `/renvio_ordenador`: Desaparecen a los 10 segundos.\n"
        "• `/eliminador_definitivo` / `/eliminador_definitivo_prime`: Desaparecen a los 15 segundos (después de mostrar el reporte de videos eliminados en el origen).\n"
        "• `/sinopsis`: Desaparece a los 5 segundos tras completarse (10 segundos si ocurre algún error).\n"
        "• `/capturas`: Desaparece a los 20 segundos tras completarse (10 segundos si ocurre algún error y 5 segundos si no se encuentra ningún video nuevo para procesar).\n"
        "• `/portada_jav`: Desaparece a los 20 segundos tras completarse (6-10 segundos en caso de error o si no hay videos).\n\n"
        "3. **Mensajes y reportes que NO desaparecen automáticamente**\n"
        "Hay comandos que generan listados, reportes o información útil que necesitas leer con calma. Por lo tanto, estos reportes y listas no se borran solos:\n"
        "• Los reportes de `/repetidos` (o `/duplicados`).\n"
        "• Los reportes de `/duplicados_miniatura` y `/duplicados_modo_avanzado`.\n"
        "• Las listas de `/buscar_codigos_jav`.\n"
        "• El listado de `/code_duplicado`.\n"
        "• La lista de `/jav_sin_code`.\n"
        "• La lista de actrices de `/lista_de_actriz`.\n"
        "• Los resultados de `/busqueda`.\n\n"
        "🧹 **¿Cómo eliminarlos cuando ya no los necesites?**\n"
        "Todos estos reportes persistentes llevan una marca invisible (\\u200b). Cuando quieras limpiar el canal de todos estos reportes acumulados, simplemente envía el comando:\n"
        "• `/limpiar` (o `/clean` / `/clear`)\n"
        "El bot buscará en el chat todos los reportes que tengan esa marca y los eliminará al instante, dejando el canal completamente limpio. El comando `/limpiar` y su confirmación se borrarán automáticamente a los 5 segundos."
    )
    # Enviar en partes para evitar MessageTooLongError
    parts = info_text.split("\n\n")
    current_chunk = ""
    replies = []
    
    for part in parts:
        if len(current_chunk) + len(part) + 2 > 4000:
            if current_chunk.strip():
                reply = await event.reply(current_chunk.strip())
                replies.append(reply)
            current_chunk = part + "\n\n"
        else:
            current_chunk += part + "\n\n"
            
    if current_chunk.strip():
        reply = await event.reply(current_chunk.strip())
        replies.append(reply)
        
    me = await client.get_me()
    if event.chat_id != me.id:
        await asyncio.sleep(40)
        to_delete = [event.id] + [r.id for r in replies]
        await client.delete_messages(event.chat_id, to_delete)

async def handle_vip(event):
    from utils.channel_resolver import matches_channel
    
    # Obtener el chat actual
    chat = await event.get_chat()
    chat_title = getattr(chat, "title", "")
    
    # Encontrar qué llaves de canal coinciden con este chat
    matched_keys = []
    for key in ["hentaila_vip", "jav_premium", "jav_regular", "twisted_short"]:
        if matches_channel(event.chat_id, chat_title, key):
            matched_keys.append(key)
            
    # Filtrar comandos exclusivos que corresponden a este canal/grupo
    exclusive_commands = []
    if matched_keys:
        for cmd in COMMANDS_METADATA:
            ekey = cmd.get("exclusive_key")
            if ekey and ekey in matched_keys:
                exclusive_commands.append(cmd)
                
    if not exclusive_commands:
        reply = await event.reply("⚠️ Este canal o grupo no tiene comandos VIP/exclusivos registrados.")
        me = await client.get_me()
        if event.chat_id != me.id:
            await asyncio.sleep(15)
            await client.delete_messages(event.chat_id, [event.id, reply.id])
        return

    # Ordenar por uso de menor a mayor
    sorted_commands = sorted(exclusive_commands, key=lambda c: get_command_count(c["name"]))
    
    header = (
        "🤖 **Comandos VIP/Exclusivos de este Canal** 🚀\n"
        "💡 *Nota: Estos comandos son exclusivos y solo funcionan en este chat.*\n"
        "📈 *Rotación dinámica: Los comandos se ordenan por uso.*\n\n"
    )
    
    cmd_strings = []
    for cmd in sorted_commands:
        usage_count = get_command_count(cmd["name"])
        count_label = f" (Usos: {usage_count})" if usage_count > 0 else " (Sin usar)"
        
        cmd_str = (
            f"📂 {cmd['title']}{count_label}\n"
            f"• **Uso:** {cmd['usage']}"
        )
        cmd_strings.append(cmd_str)
        
    list_text = header + "\n\n".join(cmd_strings)

    reply = await event.reply(list_text.strip())
    
    me = await client.get_me()
    if event.chat_id != me.id:
        await asyncio.sleep(40)
        await client.delete_messages(event.chat_id, [event.id, reply.id])
