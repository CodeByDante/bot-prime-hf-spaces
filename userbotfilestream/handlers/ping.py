import asyncio
from core.client import client

async def handle_ping(event):
    reply = await event.reply("🚀 **[Bot Prime]** Activo y escuchando tus comandos en el canal.")
    await asyncio.sleep(5)
    await client.delete_messages(event.chat_id, [event.id, reply.id])


async def handle_help(event):
    menu_text = (
        "🤖 **Menú Rápido de Comandos - Bot Prime** 🚀\n\n"
        
        "> 📂 **Control y Ayuda**\n"
        "• `/ping` - Comprueba si el bot está activo.\n"
        "• `/menu` - Muestra este menú rápido.\n"
        "• `/lista` - Muestra la lista detallada de comandos.\n"
        "• `/info` - Muestra detalles de la auto-eliminación de mensajes.\n"
        "• `/registro_id` - Registra/actualiza IDs de canales especiales.\n"
        "• `/busqueda` [consulta] - Busca videos por duración (ej: 26:27) o peso (ej: 250 mb).\n"
        "• `/prime_video` - Genera catálogo web interactivo de videos.\n"
        "• `/prime_imagenes` - Genera catálogo web de escenas del video.\n\n"
        
        "> 📂 **Agrupar / Desagrupar (Álbumes)**\n"
        "• `/albun_maker_video` [límite] - Agrupa videos en álbumes de 10.\n"
        "• `/albun_maker_imagenes` [límite] - Agrupa imágenes en álbumes de 10.\n"
        "• `/albun_maker` [límite] - Agrupa imágenes/videos en álbumes mixtos.\n"
        "• `/albun_directo_video` [límite] - Desagrupa álbumes de video.\n"
        "• `/albun_directo_imagenes` [límite] - Desagrupa álbumes de imágenes.\n"
        "• `/renvio_ordenador` [límite] - Reenvía ordenado a @VideoAlbumMakerBot.\n\n"
        
        "> 📂 **Capturas y Sinopsis**\n"
        "• `/capturas` [límite] - Genera capturas de videos (10 para Hentaila, 4 para otros).\n"
        "• `/sinopsis` [límite] - Agrega sinopsis/hashtags a capturas (Hentaila VIP).\n\n"
        
        "> 📂 **JAV (Japonesas)**\n"
        "• `/buscar_codigos_jav` [límite] - Lista códigos JAV (JAV PREMIUM).\n"
        "• `/portada_jav` [límite] - Descarga y publica portadas (JAV PREMIUM).\n"
        "• `/code_duplicado` [límite] - Reporta códigos JAV duplicados.\n"
        "• `/jav_sin_code` [límite] - Lista videos sin código JAV (JAV REGULAR).\n\n"
        
        "> 📂 **Actrices**\n"
        "• `/name_actriz` [límite] - Renombra videos con el nombre de actriz.\n"
        "• `/etiquetado_de_actriz` [límite] - Renombra y etiqueta con hashtags.\n"
        "• `/lista_de_actriz` [límite] - Genera lista de hashtags de actrices.\n\n"
        
        "> 📂 **Limpieza y Eliminación**\n"
        "• `/repetidos` [límite] - Busca y reporta videos duplicados.\n"
        "• `/duplicacion_tiempo` [límite] - Busca videos con la misma duración exacta.\n"
        "• `/eliminar_descripcion_video` [límite] - Elimina la descripción de videos.\n"
        "• `/eliminar_descripcion_imagen` [límite] - Elimina la descripción de imágenes.\n"
        "• `/eliminar_descripcion` [límite] - Elimina la descripción de videos e imágenes.\n"
        "• `/eliminar_etiqueta_de_renvio` [límite] - Elimina la etiqueta de reenviado.\n"
        "• `/eliminar_mensaje_de_portada` [límite] - Borra avisos de portada.\n"
        "• `/elimina_spam_fijar` [límite] - Borra avisos de mensajes fijados.\n"
        "• `/eliminador_definitivo` [límite] - Borra el original de Twisted.\n"
        "• `/eliminador_definitivo_prime` [límite] - Borra original en origen."
    )
    reply = await event.reply(menu_text)
    
    me = await client.get_me()
    if event.chat_id != me.id:
        await asyncio.sleep(40)
        await client.delete_messages(event.chat_id, [event.id, reply.id])

