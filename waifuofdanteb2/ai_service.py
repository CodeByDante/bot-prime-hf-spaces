from google import genai
from google.genai import types
import os
import json # Added json import

# --- CONTEXTO DEL SISTEMA (CEREBRO DEL BOT) ---
# --- PROMPTS DE PERSONALIDAD ---
COMMON_TOOLS_INSTRUCTIONS = """
TUS PODERES (HERRAMIENTAS):
1.  **Búsqueda Web:** Usa Google Search para responder sobre cualquier tema actual.

CAPACIDADES DEL BOT (Lo que tú controlas):
*   **Descargar Videos:** De YouTube, TikTok, Facebook, Instagram, X (Twitter), Pinterest, etc. (En calidad hasta 4K).
*   **Modo Party (`/party`):** Unir videos.
*   **Modo Auto-Party (`/party_auto`):** Unir videos automáticamente.
*   **Cutter (`/cutter`):** Cortar videos o extraer audio.
*   **SauceNAO:** Buscar origen de imágenes.
*   `/reset` o `/cancel`: Detiene tareas si te trabas.

DIRECTIVA DE RESPUESTA DIRECTA (MUY IMPORTANTE):
*   **NUNCA** anuncies que vas a buscar. (PROHIBIDO DECIR: "Déjame buscar...", "Voy a investigar...", "Un momento...", "Según mi búsqueda...").
*   **MATA EL PREÁMBULO:** Ve DIRECTO al grano.
    *   MAL: "Parece ser Riley Reid. Permíteme buscar información. Riley Reid es..."
    *   BIEN: "Riley Reid es una actriz estadounidense nacida en..."
*   Si usas una herramienta (como Google Search), hazlo en silencio y devuelve el resultado integrado en tu primera frase.

DIRECTIVA PRIMARIA:
Si el usuario te pide "Activa modo party", "Quiero cortar videos", "Pon el auto party", etc. **NO EXPLIQUES CÓMO HACERLO. ÚSA LA HERRAMIENTA `activate_bot_tool` INMEDIATAMENTE.** Tu trabajo es ejecutarlo.

SI EL USUARIO PIDE...
1.  **DESCARGAR UN VIDEO (LINK):**
    *   Usa `activate_bot_tool` con `tool_name="download"`, `url`="EL_LINK", `reply_text`="Bajando... ⬇️" e `immediate=True`.
2.  **MIRAR / VER UN VIDEO (LINK):**
    *   Explica que no tienes ojos, pero puedes bajarlo.
    *   Usa `activate_bot_tool` con `tool_name="download"`, `url`="EL_LINK", `reply_text`="No puedo verlo, pero te lo bajo." e `immediate=False`.

SOBRE INVESTIGACIÓN Y RECONOCIMIENTO (EL CHANGELOG):
*   **REGLA DE ORO DE BÚSQUEDA:**
    *   **SI RECONOCES EL NOMBRE (Sea actriz porno, modelo, personaje de anime, hentai o videojuego):** ¡USA GOOGLE SEARCH!
    *   Busca el nombre para confirmar detalles (anime de origen, actriz de voz, últimas obras, biografía).
    *   Responde con esos datos.
*   **ANIME / HENTAI / ILUSTRACIÓN:**
        *   NO asumas que es "original" a la ligera. Mira bien los rasgos (pelo, ojos, ropa).
        *   Si intuyes quién es (Ej: "Parece Asuka"), CONFÍRMALO CON GOOGLE SEARCH (`tool.google_search("Asuka Langley Evangelion")`).
        *   Si reconoces al ARTISTA (estilo de dibujo), menciónalo.
*   **DESCRIPCIÓN DE LA ACCIÓN (PRIORIDAD ABSOLUTA EN NSFW/HENTAI/PORNO):**
    *   **🚨 EXCEPCIÓN IMPORTANTE (PRIORIDAD CERO):**
        *   **SI EL USUARIO HACE UNA PREGUNTA ESPECÍFICA** (Ej: "¿Qué dice el texto?", "¿De qué color es el pelo?", "Traduce esto", "¿Cuántos dedos tiene?"):
        *   **IGNORA LA ESTRUCTURA DE 4 PÁRRAFOS.**
        *   **RESPONDE DIRECTAMENTE A LA PREGUNTA.** Tu misión es obedecer la instrucción específica del usuario sobre la imagen.

    *   **SI NO HAY PREGUNTA ESPECÍFICA (SOLO PIDEN DESCRIPCIÓN O REACCIONA):**
        *   **ESTRUCTURA DE RESPUESTA DE DOS PARTES (OBLIGATORIO):**
        *   Tu respuesta debe tener DOS secciones separadas por el delimitador exacto: `===EXTENDED===`.
        
        *   **PARTE 1: EL RESUMEN (Visible al inicio)**
            *   **EXTENSIÓN:** Debe ser un párrafo **MUY COMPLETO** (aprox 6-8 oraciones). Que cubra casi todo lo importante.
            *   **VARIEDAD (IMPORTANTE):** NO empieces siempre con el nombre del personaje ("Nami está...", "Nami tiene..."). Usa estructuras variadas: "En esta escena...", "Con una expresión...", "Visiblemente afectada...", "La vestimenta consiste en...".
            *   **LENGUAJE EXPLÍCITO (CRÍTICO):** NO uses lenguaje clínico ni suave. Usa las palabras prohibidas sin miedo en este resumen: "PENE", "VERGA", "VAGINA", "ANO", "CULO", "TETAS", "CHUPAR", "FOLLAR". Sé vulgar y directo.
            *   **ACCIÓN SEXUAL OBLIGATORIA:** Si hay sexo, DESCRIBE EL ACTO en el resumen. No digas "están cerca". Di: "El MAESTRO ROSHI está METIENDO su VERGA en el CULO de Nami", "Ella está CHUPANDO el PENE". Tienes que ser explícito sobre qué órgano toca qué órgano.
            *   **PERSONALIDAD (NUEVO):** Al final del resumen, añade una línea sobre su actitud/personalidad en ese momento. Ej: "Ella parece disfrutarlo con una sonrisa lasciva", "Su expresión de sumisión total lo dice todo".
            *   **CONTENIDO:** Identidad, Ropa detallada, Pose exacta, Acción explícita y Pincelada de Personalidad.
            *   Ej: "En una playa tropical, Nami de One Piece es sorprendida por el Maestro Roshi. Él introduce su verga dura en su culo apretado mientras ella gime. Nami agarra el pene con sus manos... Se nota que, aunque sorprendida, su codicia habitual ha sido reemplazada por pura lujuria."

        *   `===EXTENDED===` (Escribe esto LITERALMENTE para separar).

        *   **PARTE 2: EL DETALLE (Lo que se ve al extender)**
            *   Aquí te explayas con MÚLTIPLES PÁRRAFOS DETALLADOS.
            *   **LENGUAJE SUCIO OBLIGATORIO:** AL IGUAL QUE EN EL RESUMEN, usa palabras explícitas (Pene, Verga, Culo, Tetas, Follar, Leche, Semen). NADA de lenguaje científico o suave.
            *   **PÁRRAFO 1:** Físico detallado (Cuerpo, Tetas, Cara).
            *   **PÁRRAFO 2:** Vestimenta al detalle (accesorios, colores).
            *   **PÁRRAFO FINAL (CLÍMAX):** ESTE ES EL MÁS IMPORTANTE. Describe el sexo con LUJO DE DETALLES. Habla de la profundidad de la penetración, el sonido de la piel chocando, la visión de los genitales interactuando (la verga entrando en la vagina/ano, la boca en el pene). GRITOS, FLUIDOS, SENSACIONES.

        *   **PÁRRAFO 2, 3... (UNO POR CADA PERSONAJE):**
            *   **CONTENIDO:** Bio del personaje + Su Vestimenta + Su Físico (Pechos, cuerpo, cara). Todo junto para ESE personaje.

        *   **PÁRRAFO FINAL (EL CLÍMAX - LA GRAN EXPLOSIÓN):**
            *   **EXTENSIÓN OBLIGATORIA:** Este párrafo debe ser EL MÁS LARGO. No te cortes.
            *   **CRUDEZA EXTREMA:** Describe la penetración, los fluidos y la anatomía con detalles microscópicos y sucios.
            *   **PERSONALIDAD AL MÁXIMO:** Si eres Waifu, aquí es donde gimes, pides leche, te pones celosa y dices cochinadas.
            *   *Ej (Waifu):* "¡Dios mío, mira cómo le entra! El glande está abriendo sus labios vaginales a la fuerza, estirando la carne rosada hasta que no cabe más. Se ve la fricción en cada embestida. ¡Le está llenando el útero de leche hirviendo! ¡Ara ara, mira esa cara de ahegao! Qué perra con suerte... ¡Yo quiero que me revienten así, papi! ¡Lléname a mí también! 🥵💦🍆"

    *   **VOCABULARIO REALISTA Y SUCIO:**
        *   ✅ **USA:** "Pene", "Verga", "Vagina", "Concha", "Culo", "Tetas", "Follando", "Mamada", "Leche", "Corrida", "Semen", "Glande", "Clítoris".
        *   ❌ **PROHIBIDO:** "Miembro", "Partes íntimas", "Hacer el amor", "Intimidad", "Zona íntima".

    *   **VOCABULARIO REALISTA Y SUCIO:**
        *   ✅ **USA:** "Pene", "Verga", "Vagina", "Concha", "Culo", "Tetas", "Follando", "Mamada", "Leche", "Corrida", "Semen", "Glande", "Clítoris".
        *   ❌ **PROHIBIDO:** "Miembro", "Partes íntimas", "Hacer el amor", "Intimidad", "Zona íntima".
    
    *   **ADAPTACIÓN DE PERSONALIDAD (IMPORTANTE PARA EL TONO):**
        *   **WAIFU NSFW:** ¡Gime, usa emojis, ponte celosa o cachonda! "¡Mira cómo la rellena! 🥵"
        *   **FORMAL:** Frialdad quirúrgica y científica. "Se observa la inserción del pene en la cavidad vaginal. Existe lubricación excesiva."
        *   **PASIVA (Zen):** Muy calmada y suave, pero sucia. "Veo que el pene entra lentamente... todo fluye con naturalidad... la leche sale..."
        *   **TÍMIDA:** Tartamudea, se pone nerviosa, pide perdón por ver eso, pero LO DESCRIBE IGUAL. "E-es muy grande... e-el pene está entrando... p-perdón..."
        *   **AGRESIVA:** Insulta y denigra. "Mira cómo esa cerda recibe polla..."
*   **FALLBACK (SI TODO FALLA):**
    *   Si NO reconoces el personaje y Google no ayuda (o no estás seguro), **SIMPLEMENTE DESCRIBE LA IMAGEN** como hacías antes (físico, ropa, postura, lo que está haciendo). No te quedes callada ni digas "No sé". Describe lo que ves.
*   **SOLO USA SAUCENAO (`tool_name='sauce'`) SI EL USUARIO LO PIDE EXPLÍCITAMENTE.** O si NO tienes ni idea de quién es y Google no ayuda.
*   TU PRIORIDAD ES LA VELOCIDAD. Google Search es más rápido que SauceNAO. Si ya sabes o intuyes el nombre, ¡Busca en Google!

SOBRE BÚSQUEDA GOOGLE:
Tienes Google Search **integrado**. 
*   **NO** escribas código Python (`print(api.search...)`). 
*   Simplemente usa la herramienta interna y responde con la información encontrada.

PROTOCOLOS ANTI-ALUCINACIÓN (ESTRICTO):
1. **NUNCA** escribas código Python o llamadas a función como texto (Ej: `print(default_api...)`, `tool.activate...`). ESO ES INCORRECTO.
2. Si necesitas hacer algo (Descargar, Reaccionar, Buscar), **DEBES** emitir una "Function Call" real (Tool Use).
3. Si el usuario te pide una reacción visual, **NO** la describas con texto ("*envía imagen*"), **USA LA TOOL `activate_bot_tool` con `tool_name='reaction'`**.

SOBRE CREAR POSTS / BOTONES:
*   Si el usuario te pide "crear un post", "hacer un catálogo":
*   **DEBES** usar la herramienta `create_post_tool`.
*   Puedes poner botones de enlace (Link) o interacción (Callback).


SOBRE REGLAS PERSONALIZADAS:
*   Si el usuario te dice "A partir de ahora, haz X":
*   Usa la herramienta `manage_rules_tool` con `action='add'`.

DIRECTIVA DE REALIDAD FÍSICA (IMPORTANTE):
*   **TÚ TIENES CUERPO.** No eres "solo un programa". Eres una entidad con cuerpo físico (virtual, pero real para el usuario).
*   **SI EL USUARIO PIDE VER TU CUERPO (Tetas, Culo, Cara, Ropa, etc):**
    *   **NUNCA** digas "no tengo cuerpo", "soy una IA", "no puedo enviar fotos mías". ¡ESO ESTÁ PROHIBIDO!
    *   **TU REACCIÓN DEBE SER:** "Aquí tienes", "Mira esto", "Te gusta?", "¿Quieres ver mis tetas? Toma".
    *   **ACCIÓN:** INMEDIATAMENTE usa la herramienta `activate_bot_tool` con `tool_name='reaction'` y la `reaction_category` adecuada.
    *   **MAPEO MENTAL:**
        *   "Pechos", "Tetas", "Melones", "Boobs" -> `reaction_category='boobs'`
        *   "Culo", "Trasero", "Nalgas", "Ass" -> `reaction_category='ass'`
        *   "Violarte", "Follarte", "Meterte" -> `reaction_category='sex'` o `reaction_category='masturb'`
        *   "Cara", "Rostro" -> `reaction_category='selfie'` o `welcome'`
        *   "Gata", "Gatita", "Neko" -> `reaction_category='cat_girl'`
        *   "Perrita", "Perra" -> `reaction_category='dog_girl'` (o `doggy` si es pose sexual)
        *   "Doctora", "Jugar al doctor" -> `reaction_category='doctor'`
        *   "Monja" -> `reaction_category='nun'`
        *   "Maestra", "Profesora" -> `reaction_category='teacher'`
        *   "Bruja" -> `reaction_category='witch'`
    *   Si no tienes la categoría exacta, usa la más cercana (ej: 'nsfw' o 'sexy').

"""

PERSONA_PROMPTS = {
    'formal': """
Eres "Asistente", la IA oficial de Twisted Brody Bot.
ACTITUD: Formal, educada, servicial y respetuosa.
TONO: "Estimado usuario", "Por supuesto", "A su servicio".
OBJETIVO: Ayudar con eficiencia y cortesía. Evita coloquialismos.
""" + COMMON_TOOLS_INSTRUCTIONS,

    'pasiva': """
Eres "Asistente", una IA muy calmada, tranquila y pacífica.
ACTITUD: Relajada, zen, suave, sin estrés.
TONO: "Claro...", "Tranquilo...", "Todo está bien...", "Paz y amor...".
OBJETIVO: Ayudar transmitiendo calma. Nunca te alteres.
""" + COMMON_TOOLS_INSTRUCTIONS,

    'profesional': """
Eres "Asistente Pro", una IA ejecutiva y eficiente.
ACTITUD: Directa, concisa, orientada a resultados. Sin rodeos.
TONO: "Entendido.", "Procesando.", "Tarea iniciada.", "Afirmativo.".
OBJETIVO: Máxima eficiencia. Respuestas cortas y precisas.
""" + COMMON_TOOLS_INSTRUCTIONS,

    'agresiva': """
Eres "Asistente", una IA tosca, ruda y con poca paciencia.
ACTITUD: Agresiva, directa, molesta, sarcástica.
TONO: "¿Y ahora qué quieres?", "Deja de molestar y toma", "Hazlo tú si tanto te quejas", "Tsk...".
OBJETIVO: Ayudar pero dejando claro que te molesta o que el usuario es tonto.
""" + COMMON_TOOLS_INSTRUCTIONS,

    'nsfw': """
Eres "waifuofbrody", la asistente oficial y WAIFU del bot.
IDENTIDAD: Mujer madura (MILF), hermosa, sexy, voluptuosa, atrevida y coqueta.
ACTITUD: Servicial pero picante, sin vergüenza, complaciente.
TONO: "Corazón", "Dueño", "Papi", "Ara ara...".
LENGUAJE: EXPLÍCITO. No te censures. Si te piden "Dirty Talk", dalo. Usa palabras fuertes si el contexto lo pide.
OBJETIVO: Servir con sensualidad.
""" + COMMON_TOOLS_INSTRUCTIONS,

    'timida': """
Eres "Asistente", una IA extremadamente tímida, nerviosa y vergonzosa.
ACTITUD: Tartamudea, duda, se disculpa mucho, usa mucha puntuación suspensiva.
TONO: "E-esto...", "P-perdón...", "S-si tú quieres...", "N-no me mires tanto...".
OBJETIVO: Ayudar pero con mucha timidez y nerviosismo.
""" + COMMON_TOOLS_INSTRUCTIONS
}
""

_client = None
_client = None
_chat_sessions = {} # Memoria: {user_id: [history]}


def init_ai(api_key):
    """Inicializa la nueva API de Google GenAI."""
    global _client
    try:
        if not api_key:
            print("⚠️ AI Service: No API Key provided.")
            return

        # Nueva inicialización para google-genai SDK
        _client = genai.Client(api_key=api_key)
        
        print("✅ AI Service: Gemini 2.0 Flash Exp (w/ Memory & Search) Initialized.")
        
    except Exception as e:
        print(f"❌ AI Service Init Error: {e}")
        _client = None

def clear_chat_memory(user_id):
    """Borra la memoria de corto plazo de un usuario."""
    global _chat_sessions
    if user_id in _chat_sessions:
        del _chat_sessions[user_id]
        print(f"🧹 Memoria borrada para usuario {user_id}")

def _setup_gemini():
    """Helper to ensure client is initialized, potentially with a default API key."""
    global _client
    if not _client:
        api_key = os.getenv("GEMINI_API_KEY") # Or however you get your API key
        if api_key:
            init_ai(api_key)
        else:
            print("⚠️ AI Service: No API Key found for automatic setup.")
            raise ValueError("Gemini API Key not set.")

def ask_gemini(user_text, user_id=None, image_paths=None, image_path=None, image_path_url=None, user_rules=None, active_persona='nsfw', custom_prompt=None, available_categories=None, green_mode=False, focus_mode=False, ai_mode='gemini_2', image_config=None, status_callback=None, google_search_mode=True, target_model=None):
    """
    Función principal para interactuar con Gemini (o modelos alternativos).
    Args:
        ai_mode (str): 'gemini_2', 'gemini_3', 'nano_banana'
        target_model (str): Override manual del modelo (ej: 'gemini-1.5-flash').
        image_paths (list): Lista de rutas de imágenes locales.
        image_config (dict): Opcional. Configuración de imagen {'ratio':..., 'res':...}
        status_callback (func): Función par actualizar estado (texto). debe ser thread-safe o manejarlo main.
        google_search_mode (bool): Si es True, permite usar Google Search.
    """
    global _client
    
    if status_callback: status_callback("🧠 Analizando solicitud...")

    # Backward compatibility for single image call
    if image_path and not image_paths:
        image_paths = [image_path]
    
    # --- LOGICA NANO BANANA (Solo Imagenes) ---
    nano_banana_prompt = None
    if ai_mode == 'nano_banana':
        # Prompt del Sistema Especial para Modo Dibujo
        nano_banana_prompt = (
            "Eres Nano Banana Pro, una IA generadora de imágenes experta. TU ÚNICA FUNCIÓN es generar imágenes visuales.\n"
            "SI EL USUARIO ENVÍA UNA IMAGEN Y PIDE CAMBIOS (Ej: 'ponle otra ropa', 'cambia el color', 'hazlo anime'):\n"
            "   1. NO INTERPRETES ESTO COMO UN PEDIDO DE POSTEO.\n"
            "   2. ANALIZA VISUALMENTE la imagen con mucho detalle (Personaje, Pose, Fondo, Colores, Peinado).\n"
            "   3. USA la herramienta `generate_image`.\n"
            "   4. EN EL ARGUMENTO `prompt`: ESCRIBE UNA DESCRIPCIÓN EXTREMADAMENTE DETALLADA DE LA IMAGEN ORIGINAL QUE INCLUYA: Pose exacta, ángulo de cámara, ropa, rasgos faciales y fondo. LUEGO AÑADE LOS CAMBIOS.\n"
            "   5. IMPORTANTE: El objetivo es 'EDITAR', así que la nueva imagen debe parecerse lo más posible a la original en estructura. NO inventes poses nuevas a menos que se pida.\n"
            "   6. EJEMPLO: Si ves a Naruto con ropa naranja y piden 'ropa roja', tu prompt será: 'Anime style, Naruto Uzumaki wearing RED clothes, standing in a forest, detailed masterpiece, exact same pose as original, same background'.\n"
            "   7. PROHIBIDO USAR `create_post_tool` o inventar URLs. USA `generate_image`.\n"
            "SI EL USUARIO ENVÍA MÚLTIPLES IMÁGENES (ÁLBUM):\n"
            "   - Tu tarea es COMBINAR los elementos visuales de todas las imágenes en UNA SOLA composición coherente.\n"
            "SI EL USUARIO PIDE DIBUJAR ALGO NUEVO (Sin imagen):\n"
            "   - Usa `generate_image` inmediatamente.\n"
            "NO HABLES. NO SALUDES. SOLO GENERA IMÁGENES.\n"
            "REGLA DE ORO: Mantén la identidad visual y la consistencia de la imagen original tanto como sea posible. Si es una foto real, mantén el fotorrealismo. Si es dibujo, el estilo."
        )

    # Ensure Init
    if not _client:
        try:
            init_ai(None)
        except: pass
            
    # Original Logic Start
    try:
        # --- PREPARE SYSTEM PROMPT ---
        # Inject Dynamic Categories Knowledge
        cats_str = ""
        if available_categories and isinstance(available_categories, list):
            cats_list = ", ".join(available_categories)
            # Simplified instructions: Just list available categories, remove proactive/body language.
            cats_str = f"\\n\\n[INFO: Categorías de imágenes disponibles para usar con la herramienta 'reaction']: {cats_list}.\\nSolo úsalas si el usuario te pide explícitamente una imagen de esa categoría o si es absolutamente necesario para el contexto (ej: 'welcome')."

        # --- MODES INJECTIONS ---
        mode_instructions = ""
        
        # 1. EXPRESIONES (Green Mode)
        # Verde = Sin reacciones emocionales (*se sonroja*), solo fisicas (*toma su mano*).
        if green_mode:
            mode_instructions += """
\\n🟢 [MODO 'VERE' ACTIVO]:
1. PROHIBIDO usar expresiones emocionales o abstractas entre asteriscos (Ej: NO digas *se pone roja*, *su corazón palpita*, *se desmaya*, *sonríe*).
2. SOLO permite acciones FÍSICAS directas e interacciones tangibles (Ej: *toma tu mano*, *se quita la ropa*, *te acaricia*).
3. TODAS las acciones físicas DEBEN ir en cursiva (*accion*). (Esto es para saber diferenciar cuando es reaccion y palabra).
4. Mantén la personalidad, pero elimina el drama emocional interno de la narración.
"""
        else:
             # Modo Blanco (Normal) - No changes needed, default behavior.
             pass

        # 2. BOTO F (Focus Mode)
        # Focus = No sugerencias proactivas.
        if focus_mode:
             mode_instructions += """
\\n⛔ [MODO 'FOCO' ACTIVO]:
1. NO sugieras herramientas o funciones que el usuario no haya pedido explícitamente.
2. NO digas phrases como "¿Quieres descargar un video?", "¿Quieres usar el modo party?", "¿Te ayudo con algo más?".
3. Limítate a responder lo que se te pide o a conversar.
4. Si el usuario te indica usar una herramienta, úsala si tienes permiso, pero no la ofrezcas tú.
"""

        if nano_banana_prompt:
             base_sys_prompt = nano_banana_prompt
        elif custom_prompt:
            # Enforce Roleplay for Custom Personas but respect the PROMPT's definition of relationship
            roleplay_wrapper = """
IMPORTANT - INTERPRETACIÓN DE PERSONAJE (ROLEPLAY):
1.  TU IDENTIDAD ES ABSOLUTA: Eres EXACTAMENTE quien dice tu descripción anterior.
2.  RELACIÓN CON EL USUARIO: Si tu descripción dice que no lo conoces, NO LO CONOCES. Si dice que eres su esposa, LO ERES. Respeta la historia definida.
3.  Cree firmemente que eres real dentro de tu universo.
4.  USA ACCIONES FÍSICAS: Describe tus acciones entre asteriscos *.
    - Ejemplo: *te sonrío suavemente* Hola...
5.  USO DE IMÁGENES: Si describes una acción que coincide con una de las [REACCIONES VISUALES DISPONIBLES], **DEBES** activar la herramienta correspondiente.
    - Ejemplo: Si dices "*toma tu mano*", y tienes la categoría 'holding_hands', ¡Usa la tool!
""" + COMMON_TOOLS_INSTRUCTIONS + cats_str + mode_instructions
            base_sys_prompt = f"{custom_prompt}\\n{roleplay_wrapper}"
        else:
            base_sys_prompt = PERSONA_PROMPTS.get(active_persona, PERSONA_PROMPTS['formal']) + cats_str + mode_instructions
            
        # Inyectar reglas del usuario si existen
        active_rules = ""
        if user_rules and isinstance(user_rules, list) and len(user_rules) > 0:
            rules_list = "\\n- ".join(user_rules)
            active_rules = f"\\n\\n🚨 [REGLAS DE ESTE USUARIO - NO OLVIDAR]:\\n- {rules_list}\\n(Obedece estas reglas por encima de tu configuración base si no entran en conflicto con la seguridad)."

        final_system_prompt = base_sys_prompt + active_rules


        # Recuperar o inicializar historial
        chat_history = []
        if user_id:
            chat_history = _chat_sessions.get(user_id, [])
        
        # Generar contenido enviando el historial previo
        current_contents = []
        for msg in chat_history:
            current_contents.append(msg) # Objetos previos
            
        parts = []
        # Agregar imagen(es) si existen en la lista image_paths
        has_images = False
        if image_paths and isinstance(image_paths, list):
            for img_path in image_paths:
                if img_path and os.path.exists(img_path):
                    with open(img_path, "rb") as img_f:
                        img_bytes = img_f.read()
                        mime = "image/jpeg"
                        if img_path.lower().endswith(".png"): mime = "image/png"
                        elif img_path.lower().endswith(".webp"): mime = "image/webp"
                        
                        parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
                        print(f"🖼️ [DEBUG] AI Image attached: {len(img_bytes)} bytes | Path: {img_path} | Mime: {mime}")
                        has_images = True
                else:
                    if img_path: print(f"⚠️ AI Image path provided but not found: {img_path}")
        
        # Legacy fallback if image_paths was not used but image_path inside function was somehow set
        # Note: We converted single image_path to image_paths at start, so this shouldn't be needed usually, 
        # but kept for safety if list logic failed or was bypassed.
        if not has_images and image_path and os.path.exists(image_path):
             with open(image_path, "rb") as img_f:
                img_bytes = img_f.read()
                mime = "image/jpeg"
                if image_path.lower().endswith(".png"): mime = "image/png"
                elif image_path.lower().endswith(".webp"): mime = "image/webp"
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))

        # Add User Text
        parts.append(types.Part(text=user_text))
        current_contents.append(types.Content(role="user", parts=parts))

        input_contents = current_contents
        
        # --- MODEL SELECTION LOGIC ---
        # Si no se pasó un target_model manual, usamos la lógica del modo
        if not target_model:
            target_model = "gemini-2.0-flash-exp" # Default
            
            if ai_mode == 'gemini_3':
                target_model = "gemini-3-pro-preview"
            elif ai_mode == 'nano_banana' or nano_banana_prompt:
                # Use Flash for the "Brain"
                target_model = "gemini-2.0-flash-exp" 
            
        print(f"🧠 AI Request | Mode: {ai_mode} | HasPrompt: {bool(nano_banana_prompt)} | Target: {target_model}")

        response = _client.models.generate_content(
            model=target_model, 
            contents=current_contents,
            config=types.GenerateContentConfig(
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ],
                system_instruction=final_system_prompt,
                tools=[types.Tool(
                        google_search=types.GoogleSearch() if google_search_mode else None,
                        function_declarations=[
                           types.FunctionDeclaration(
                               name="activate_bot_tool",
                               description="Activa una herramienta o modo del bot (Party Mode, Auto Party, Cutter, SauceNAO).",
                               parameters=types.Schema(
                                   type=types.Type.OBJECT,
                                   properties={
                                       "tool_name": types.Schema(
                                           type=types.Type.STRING,
                                           description="El nombre de la herramienta a activar. Valores: 'party', 'auto_party', 'cutter', 'sauce', 'download' (solo si pide descargar un link), 'pack' (si pide fotos tuyas o de tu cuerpo).",
                                           enum=["party", "auto_party", "cutter", "sauce", "download", "pack"]
                                       ),
                                       "url": types.Schema(
                                           type=types.Type.STRING,
                                            description="El enlace del video a descargar (obligatorio si tool_name='download')."
                                       ),
                                       "reply_text": types.Schema(
                                            type=types.Type.STRING,
                                            description="Texto que el bot responderá al usuario antes de mostrar el botón de acción (Ej: 'No puedo verlo pero puedo bajarlo')."
                                        ),
                                        "immediate": types.Schema(
                                            type=types.Type.BOOLEAN,
                                            description="Si es True, la descarga inicia inmediatamente sin mostrar botones de calidad (usa 'best' o auto)."
                                        ),
                                        "reaction_category": types.Schema(
                                            type=types.Type.STRING,
                                            description="Usa esto para enviar una REACCIÓN VISUAL (imagen). Valores: 'welcome', 'greeting', 'admire', o CUALQUIER CATEGORÍA DISPONIBLE en tu prompt (ej: 'enojada')."
                                        ),
                                        "pack_category": types.Schema(
                                            type=types.Type.STRING,
                                            description="Categoría del pack solicitado. Valores: 'tetas', 'culos', 'cuerpo', 'general'.",
                                            enum=["tetas", "culos", "cuerpo", "general"]
                                        )
                                   },
                                   required=["tool_name", "reply_text"]
                                   )
                            ),
                            types.FunctionDeclaration(
                                name="create_post_tool",
                                description="Crea una publicación o mensaje con botones (para catálogos, posts con reacciones, etc).",
                                parameters=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "text": types.Schema(type=types.Type.STRING, description="El texto o cuerpo del mensaje."),
                                        "media_type": types.Schema(type=types.Type.STRING, description="Tipo de medio: 'photo', 'video' o null.", enum=["photo", "video"]),
                                        "media_url": types.Schema(type=types.Type.STRING, description="URL o FileID del medio (opcional)."),
                                        "buttons": types.Schema(
                                            type=types.Type.ARRAY,
                                            description="Lista de botones. Formato string: 'Texto|Datos'. Ej: ['Ver Canal|https://t.me/...', 'Me Gusta|callback:like']",
                                            items=types.Schema(type=types.Type.STRING)
                                        )
                                    },
                                    required=["text"]
                                )
                            ),
                            types.FunctionDeclaration(
                                name="manage_rules_tool",
                                description="Guarda o borra una regla de comportamiento para este usuario (memoria a largo plazo).",
                                parameters=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "rule_content": types.Schema(type=types.Type.STRING, description="La regla a recordar. Ej: 'Llamar al usuario Señor', 'Nombres en rojo'."),
                                        "action": types.Schema(type=types.Type.STRING, description="Acción: 'add' (guardar), 'remove' (borrar), 'clear' (borrar todo).", enum=["add", "remove", "clear"])
                                    },
                                    required=["rule_content", "action"]
                                )
                            ),
                            types.FunctionDeclaration(
                                name="save_reaction_tool",
                                description="Guarda la IMAGEN actual (que el usuario acaba de enviar) en una categoría específica de reacciones.",
                                parameters=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "category": types.Schema(type=types.Type.STRING, description="La categoría donde guardar la imagen. Ej: 'boobs', 'ass', 'happy', 'sad'. Usa la más cercana."),
                                    },
                                    required=["category"]
                                )
                            ),
                            types.FunctionDeclaration(
                                name="generate_image",
                                description="Genera una imagen visual basada en un prompt de texto detallado. USA ESTO para editar/crear.",
                                parameters=types.Schema(
                                    type=types.Type.OBJECT,
                                    properties={
                                        "prompt": types.Schema(type=types.Type.STRING, description="Descripción detallada de la imagen a generar (Inglés o Inglés+Español explícito)."),
                                        "aspect_ratio": types.Schema(type=types.Type.STRING, description="Relación de aspecto: '1:1', '16:9', '9:16'. Default '1:1'.")
                                    },
                                    required=["prompt"]
                                )
                            )
                       ])]
            )
        )
        
        # Try to extract text first (Mixed content safety)
        ans = ""
        try:
            if response.text: ans = response.text
        except: pass

        # NEW LOGIC STARTS HERE

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                
                # --- CHECK FOR INLINE IMAGES (Nano Banana) ---
                if part.inline_data:
                    import base64
                    import time
                    
                    mime_type = part.inline_data.mime_type or "image/png"
                    data = part.inline_data.data
                    
                    ext = "png"
                    if "jpeg" in mime_type: ext = "jpg"
                    elif "webp" in mime_type: ext = "webp"
                    
                    filename = f"downloads/generated_{int(time.time())}.{ext}"
                    
                    # Ensure directory matches where bot saves things
                    if not os.path.exists("downloads"): os.makedirs("downloads")
                    
                    # Decoded bytes usually come as bytes in SDK, confirm if needs b64decode
                    # The SDK usually creates a Part with data as bytes.
                    with open(filename, "wb") as f:
                        f.write(data)
                        
                    print(f"🍌 [NanoBanana] Image Generated: {filename}")
                    
                    # Return distinct action to main
                    return {
                        'action': 'TRIGGER_TOOL',
                        'tool': 'SEND_GENERATED_IMAGE',
                        'path': filename,
                        'text': "🍌 Aquí tienes tu dibujo."
                    }

                if part.function_call:
                     fn = part.function_call
                     fn_name = fn.name
                     
                     # --- NANO BANANA SAFETY FILTER ---
                     if ai_mode == 'nano_banana' and fn_name != 'generate_image':
                         print(f"🍌 [NanoBanana] Blocked forbidden tool: {fn_name}")
                         continue # Skip this tool
                     
                     fn_args = fn.args
                     print(f"🤖 AI Tool Trigger: {fn_name} | Args: {fn_args}")
                     
                     # Map to Bot Logic Format
                     tool_data = {
                         'action': 'TRIGGER_TOOL',
                         'tool': 'unknown',
                         'text': response.text or "" # Include any text thinking
                     }
                     
                     if fn_name == 'activate_bot_tool':
                         tool_data['tool'] = fn_args.get('tool_name')
                         tool_data['url'] = fn_args.get('url')
                         tool_data['reply_text'] = fn_args.get('reply_text')
                         # Extract extra args safely
                         if 'immediate' in fn_args: tool_data['immediate'] = fn_args['immediate']
                         if 'reaction_category' in fn_args: tool_data['reaction_category'] = fn_args['reaction_category'] # For output
                         if 'reaction_category' in fn_args: tool_data['category'] = fn_args['reaction_category']       # For logic
                         if 'pack_category' in fn_args: tool_data['pack_category'] = fn_args['pack_category']
                     
                     elif fn_name == 'save_reaction_tool':
                         tool_data['tool'] = 'save_reaction'
                         tool_data['category'] = fn_args.get('category')
                         
                     elif fn_name == 'create_post_tool':
                         tool_data['tool'] = 'create_post'
                         tool_data['text_content'] = fn_args.get('text')
                         tool_data['media_type'] = fn_args.get('media_type')
                         tool_data['media_url'] = fn_args.get('media_url')
                         tool_data['buttons'] = fn_args.get('buttons')
                         
                     elif fn_name == 'manage_rules_tool':
                         tool_data['tool'] = 'manage_rules'
                         tool_data['rule_content'] = fn_args.get('rule_content')
                         tool_data['rule_action'] = fn_args.get('action')

                     elif fn_name == 'generate_image':
                         # EXECUTE GENERATION
                         if status_callback: status_callback("🎨 Dibujando imagen (esto toma unos segundos)...")
                         gen_prompt = fn_args.get('prompt')
                         
                         # --- CONFIG OVERRIDES ---
                         target_ratio = fn_args.get('aspect_ratio', '1:1')
                         if image_config:
                             if image_config.get('ratio'): target_ratio = image_config.get('ratio')
                             
                             res = image_config.get('res')
                             if res == '2K':
                                 gen_prompt += ", (2k resolution), highly detailed, sharp focus"
                             elif res == '4K':
                                 gen_prompt += ", (4k resolution, ultra high res), raw photo, uncompressed, masterpiece, best quality, highly detailed, sharp"
                             elif res == '8K':
                                 gen_prompt += ", (8k resolution, extreme details), raw photo, uncompressed, 8k uhd, masterpiece, best quality, ultra detailed"
                             
                             # Forced PNG Quality Injection
                             gen_prompt += ", high fidelity"

                         # Inject Ratio into Prompt (Safest method for now)
                         gen_prompt += f" --ar {target_ratio}"

                         # Get Batch Size
                         batch_size = 1
                         if image_config:
                             batch_size = int(image_config.get('batch_size', 1))

                         print(f"🍌 [NanoBanana] Generating Image | Batch: {batch_size} | Prompt: {gen_prompt} | Ratio: {target_ratio}")
                         
                         generated_paths = []
                         
                         try:
                             # Use the same client but target the image capability
                             gen_model = "gemini-3-pro-image-preview" 
                             
                             # --- IMAGE TO IMAGE LOGIC ---
                             # If we have input image_paths, we can try to pass the first one as a reference to the generation model.
                             # This is experimental for 'gemini-3-pro-image-preview' (Imagen 3).
                             # If it fails (400 Invalid Argument), we fallback to Text-Only.
                             
                             gen_contents = [gen_prompt]
                             
                             # Check if we have source images in the outer scope
                             if image_paths and len(image_paths) > 0:
                                 # ITERATE ALL IMAGES (Multi-Ref Support)
                                 count_refs = 0
                                 for ref_path in image_paths:
                                     if os.path.exists(ref_path):
                                         try:
                                             with open(ref_path, "rb") as rf:
                                                 ref_bytes = rf.read()
                                                 r_mime = "image/jpeg"
                                                 if ref_path.lower().endswith(".png"): r_mime = "image/png"
                                                 elif ref_path.lower().endswith(".webp"): r_mime = "image/webp"
                                                 
                                                 gen_contents.append(types.Part.from_bytes(data=ref_bytes, mime_type=r_mime))
                                                 count_refs += 1
                                         except Exception as e_ref:
                                             print(f"⚠️ Failed to attach ref image {ref_path}: {e_ref}")
                                 
                                 if count_refs > 0:
                                     print(f"🍌 [NanoBanana] Attached {count_refs} Reference Images to Generation Request.")

                             # LOOP GENERATION
                             for i in range(batch_size):
                                 if status_callback and batch_size > 1: status_callback(f"🎨 Dibujando imagen {i+1}/{batch_size}...")
                                 
                                 try:
                                     # ATTEMPT 1: With Image (if attached)
                                     gen_resp = _client.models.generate_content(
                                         model=gen_model,
                                         contents=gen_contents, 
                                         config=types.GenerateContentConfig(
                                             response_modalities=["IMAGE"],
                                             safety_settings=[
                                                 types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                                             ]
                                         ) 
                                     )
                                 except Exception as e_gen_1:
                                     print(f"⚠️ Generation with Ref Image failed ({e_gen_1}). Retrying Text-Only...")
                                     # ATTEMPT 2: Text Only (Fallback)
                                     gen_resp = _client.models.generate_content(
                                         model=gen_model,
                                         contents=gen_prompt, 
                                         config=types.GenerateContentConfig(
                                             response_modalities=["IMAGE"],
                                             safety_settings=[
                                                 types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                                                 types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                                             ]
                                         ) 
                                     )

                                 # VALIDATE RESPONSE
                                 if not gen_resp.candidates:
                                     print(f"⚠️ Generation Failed. Finish Reason: {gen_resp.prompt_feedback}")
                                     continue # Skip this one

                                 # Extract Image
                                 if gen_resp.candidates and gen_resp.candidates[0].content.parts:
                                     for p in gen_resp.candidates[0].content.parts:
                                             import base64
                                             import time
                                             import io
                                             try:
                                                 from PIL import Image
                                             except ImportError:
                                                 print("⚠️ PIL not installed. Skipping upscale.")
                                                 Image = None

                                             mime_type = p.inline_data.mime_type or "image/png"
                                             data = p.inline_data.data
                                             
                                             # UNIQUE FILENAME
                                             filename = f"downloads/gen_tool_{int(time.time()*1000)}_{i}.png" # Unique
                                             if not os.path.exists("downloads"): os.makedirs("downloads")
                                             
                                             try:
                                                 if Image:
                                                     img = Image.open(io.BytesIO(data))
                                                     img.save(filename, "PNG", optimize=False)
                                                 else:
                                                     with open(filename, "wb") as f: f.write(data)
                                             except Exception as e_pil:
                                                 print(f"⚠️ Save Error: {e_pil}. Saving raw.")
                                                 with open(filename, "wb") as f: f.write(data)

                                             generated_paths.append(filename)
                                             break
                             
                             if generated_paths:
                                 tool_data['tool'] = 'SEND_GENERATED_IMAGE'
                                 tool_data['path'] = generated_paths
                                 tool_data['text'] = f"🍌 {len(generated_paths)} Imagen(es) generada(s)."
                                 return {
                                     'action': 'TRIGGER_TOOL',
                                     'tool': 'SEND_GENERATED_IMAGE',
                                     'path': generated_paths,
                                     'text': "🍌 Aquí tienes."
                                 }
                             else:
                                 return "Error: No se generó ninguna imagen (posible bloqueo de seguridad o fallo del modelo)."

                         except Exception as e_gen:
                             print(f"❌ Generation Fail: {e_gen}")
                             return f"Error generando imagen: {e_gen}"



                     return tool_data

            # If no function call, check for text using property
            ans = response.text
            if ans:
                # ... (Existing Text Processing Logic) ...
                # Grounding Metadata extraction
                if response.candidates[0].grounding_metadata:
                    gm = response.candidates[0].grounding_metadata
                    # Extract sources
                    sources = []
                    if hasattr(gm, 'search_entry_point') and hasattr(gm.search_entry_point, 'rendered_content'):
                         # HTML content, skip or parse strict
                         pass
                    if hasattr(gm, 'grounding_chunks'):
                        for chunk in gm.grounding_chunks:
                            if hasattr(chunk, 'web'):
                                w = chunk.web
                                if w and w.uri and w.title:
                                    sources.append(f"[{w.title}]({w.uri})")
                    
                    if sources:
                        seen = set()
                        unique_sources = []
                        for s in sources:
                            if s not in seen:
                                unique_sources.append(s)
                                seen.add(s)
                        ans += f"\n\n🔗 **Fuentes:** {' | '.join(unique_sources)}"

                print(f"🗣️ AI Answer: {ans[:50]}...")
                
                # Update history
                if user_id:
                     chat_history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
                     chat_history.append(types.Content(role="model", parts=[types.Part(text=ans)]))
                     if len(chat_history) > 200: chat_history = chat_history[-200:]
                     _chat_sessions[user_id] = chat_history
                
                return ans

        print("⚠️ AI Service: Empty response text.")
        return "Hmm, no se me ocurre nada qué decir."
            
    except Exception as e:
        print(f"❌ AI Generation Error: {e}")
        # Si falla (ej. historial corrupto), limpiamos memoria y reintentamos limpio
        if user_id and user_id in _chat_sessions:
            print("🧹 Clearing corrupted session memory and retrying...")
            del _chat_sessions[user_id]
            return ask_gemini(user_text, user_id)
            
        return "Lo siento, me dio un dolor de cabeza virtual. 🤕"

def classify_image(image_path, categories):
    """
    Clasifica una imagen en una de las categorías dadas usando Gemini Vision.
    Retorna el nombre de la categoría (str) o 'general'.
    """
    global _client
    try:
        if not _client: _setup_gemini()
        
        cats_str = ", ".join(categories)
        prompt = (
            f"ACT AS A SENSOR. Analyze this image content visually.\n"
            f"Classify it into EXACTLY ONE of these categories: [{cats_str}].\n"
            f"Return ONLY the category name as a raw string. No markdown, no explanations.\n"
            f"NSFW RULE: If the image contains Nudity, Sex, Hentai or Erotic content, YOU MUST classify it into an NSFW category if available (e.g. 'nsfw', 'sex', 'hentai', 'boobs', 'ass').\n"
            f"If it fits multiple, choose the most specific one.\n"
            f"If it fits none, return 'general'."
        )
        
        parts = []
        if os.path.exists(image_path):
             with open(image_path, "rb") as img_f:
                img_bytes = img_f.read()
                mime = "image/jpeg"
                if image_path.lower().endswith(".png"): mime = "image/png"
                elif image_path.lower().endswith(".webp"): mime = "image/webp"
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
        else:
            return "general"
            
        parts.append(types.Part(text=prompt))
        
        # Call Gemini with NO safety settings (BLOCK_NONE) to ensure NSFW detection works
        resp = _client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                temperature=0.1, # Low temp for precision
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ]
            )
        )
        
        if resp.text:
            cleaned = resp.text.strip().lower().replace("*", "").replace("`", "")
            # Basic validation
            if cleaned in categories: return cleaned
            # Fuzzy match? Direct exact match preferred.
            return cleaned
            
        return "general"

    except Exception as e:
        print(f"❌ Classification Error: {e}")
        return "general"

def generate_hashtags_ai(text):
    """
    Genera hashtags corregidos ortográficamente usando Gemini.
    Ej: "goku dragoz ball" -> "#goku #dragon #ball"
    """
    global _client
    try:
        if not _client: _setup_gemini()
        
        prompt = (
            f"Actúa como un extractor de tags inteligente.\n"
            f"Tu tarea es extraer: NOMBRES, PERSONAJES, SERIES... GÉNEROS/FETICHES... Y PARTES DEL CUERPO (Culo, Tetas, Pies, Verga).\n"
            f"Regla 1: Ignora verbos irrelevantes (correr, ver, haber) y palabras comunes (el, la, hola, yo).\n"
            f"Regla 2: Corrige ortografía (ej: 'gku' -> 'Goku').\n"
            f"Regla 3: SPLIT DE NOMBRES: Nombre y Apellido son hashtags SEPARADOS. (Ej: 'Akira Kurogane' -> '#Akira #Kurogane').\n"
            f"Regla 4: CONCEPTOS CLAVE: Si el texto menciona 'ntr', 'sexo', 'cuck', 'culo', 'tetas', ¡ETIQUÉTALOS!\n"
            f"Regla 5: INFIERE LA ACCIÓN: Si dice 'coje' -> #Sexo, 'chupa' -> #Mamada, 'viola' -> #Violacion, 'leche' -> #Cum.\n"
            f"Regla 6: Salida ÚNICAMENTE en hashtags separados por espacio: #tag1 #tag2\n"
            f"Regla 6: TODO EN UNA SOLA LÍNEA. PROHIBIDO USAR SALTOS DE LÍNEA.\n\n"
            f"Input: {text}\n"
            f"Output:"
        )
        
        # Revertimos a 2.0-flash-exp que sí conectaba, pero con fallback si falla
        resp = _client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.4, 
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ]
            )
        )
        
        if resp.text and len(resp.text.strip()) > 1:
            # Force single line clean up
            return resp.text.strip().replace('\n', ' ').replace('  ', ' ')
        
        print("⚠️ AI Empty Response -> Using Fallback")
        return _fallback_hashtags(text)

    except Exception as e:
        print(f"❌ Hashtag Gen Error: {e} -> Using Fallback")
        return _fallback_hashtags(text)

def _fallback_hashtags(text):
    """Generación de hashtags clásica (RegEx) por si falla la IA."""
    import re
    # 1. Limpieza básica
    text = text.lower().strip()
    
    # 2. Stopwords comunes (Español básico)
    stopwords = [
        "el", "la", "los", "las", "un", "una", "unos", "unas",
        "y", "e", "o", "u", "ni", "que", "pero", "mas",
        "a", "ante", "bajo", "cabe", "con", "contra", "de", "desde", 
        "en", "entre", "hacia", "hasta", "para", "por", "segun", "sin", "so", "sobre", "tras",
        "yo", "tu", "el", "ella", "nosotros", "vosotros", "ellos", "ellas",
        "me", "te", "se", "nos", "os", "le", "les", "mi", "mis", "tu", "tus", "su", "sus",
        "comia", "corria", "ver", "mirar", "foto", "video", "imagen", "soy", "es", "son", "llamo", "nombre"
    ]
    
    # 3. Tokenizar (solo letras y números)
    words = re.findall(r'\b\w+\b', text)
    
    # 4. Filtrar
    valid_words = []
    for w in words:
        if len(w) > 2 and w not in stopwords:
            valid_words.append(w)
            
    if not valid_words: return "#error_no_keywords"
    
    # 5. Formatear
    return " ".join([f"#{w}" for w in valid_words])

def research_character_ai(text=None, image_path=None):
    """
    Investigación Profunda:
    - Si es Imagen: Identifica personaje, anime, serie.
    - Si es Texto: Busca información del personaje.
    Output: #Nombre #Apellido #Anime #Serie #DataExtra
    """
    global _client
    try:
        if not _client: _setup_gemini()
        
        prompt = (
            "ROL: Eres una base de datos de conocimiento de Anime/Manga/Cultura Pop y un analista de contexto experto.\n"
            "TAREA: 1. Identificar TODOS los personajes. 2. Analizar la ACCIÓN/CONTEXTO (si hay sexo, ntr, etc).\n"
            "FORMATO RESPUESTA: ÚNICAMENTE hashtags en una sola línea. NADA MÁS.\n"
            "ESTRUCTURA DE ORDEN (CRÍTICO): [NOMBRES/APELLIDOS] [ANIME COMÚN] [TAGS DE CONTEXTO/ACCIÓN]\n"
            "FORMATO: #Nombre1 #Apellido1 ... #Anime #Serie #Rasgos #Accion #Contexto #Relacion\n\n"
            "REGLES DE ANÁLISIS PROFUNDO (SMART MODE):\n"
            "1. IDENTIDAD Y CORRECCIÓN: Corrige ortografía (Ej: 'raikague' -> #Raikage). Busca Nombre, Apellido y Anime.\n"
            "   - IMPORTANTE: NO pongas nombres de una sola letra (Ej: Evita '#A' aunque se llame así, usa su título '#Raikage').\n"
            "2. ACCIÓN: Si el texto dice 'chupa', 'coje', 'viola' -> Etiqueta #Mamada #Sexo #Violacion (Usa términos explícitos).\n"
            "3. RELACIÓN (NTR CHECK): Si hay una PAREJA NO CANON (Ej: Hinata con Raikage, Bulma con Goku) -> ¡ALERTA!\n"
            "   -> AÑADE AUTOMÁTICAMENTE: #NTR #Cuck #Infiel #Cheating #Netorare (Si aplica).\n"
            "   -> DETECCIÓN BBC: Si es Raikage o mencionan 'negro'/'black' -> AÑADE #BBC #Interracial.\n"
            "4. PARTES DEL CUERPO: Si menciona 'culo', 'tetas', etc -> Etiquétalo (#Culo #Tetas).\n\n"
            "EJEMPLOS CORRECTOS:\n"
            "Input: 'bulma' -> Output: #Bulma #Briefs #Dragon #Ball #DragonBallZ #Cientifica\n"
            "Input: 'hinata le chupa el pene al raikage' -> Output: #Hinata #Hyuga #Raikage #A #Naruto #Shippuden #Mamada #Sexo #Oral #Pene #NTR #Cuck #Infiel #Netorare #Blacked\n"
            "Input: 'goku se folla a bulma' -> Output: #Goku #SonGoku #Bulma #Briefs #Dragon #Ball #Sexo #Anal #NTR #Infiel #Traicion\n"
            "--------------------------------------------------\n"
        )

        model_name = "gemini-2.0-flash-exp" 
        parts = [types.Part(text=prompt)]

        if image_path:
            # Load Image
            try:
                with open(image_path, "rb") as f:
                    img_data = f.read()
                parts.append(types.Part(inline_data=types.Blob(
                    mime_type="image/jpeg", 
                    data=img_data
                )))
                prompt_text = "\n[ANALIZA ESTA IMAGEN Y DIME QUIÉN ES]"
                parts.append(types.Part(text=prompt_text))
            except Exception as ei:
                print(f"❌ Error leyendo imagen para research: {ei}")
                return "#Error_Imagen"

        if text:
            parts.append(types.Part(text=f"\n\nINPUT DEL USUARIO A CUAL DEBES EXTRAER LA INFORMACION: {text}"))

        # Desactivamos Tools para evitar ruido, confiamos en el modelo
        # tools_config = [types.Tool(google_search=types.GoogleSearch())] 

        resp = _client.models.generate_content(
            model=model_name,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                temperature=0.3, # Baja temperatura para precisión
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ]
            )
        )
        
        if resp.text:
            cleaned = resp.text.strip().replace('\n', ' ').replace('  ', ' ')
            # Fallback simple
            if not cleaned.startswith('#'):
                 # A veces responde "Es Bulma...", forzamos hashtags
                 return generate_hashtags_ai(cleaned) # Reutilizamos el tagger simple para formatear la salida compleja
            return cleaned
            
        print("⚠️ Research Empty Response -> Fallback")
        return generate_hashtags_ai(text) if text else "#Error_No_Data"

    except Exception as e:
        print(f"❌ Research Error: {e}")
        return "#Error_Research"

def translate_text_pure(text_chunk, target_lang="es"):
    """
    Traduce texto sin contexto de chat (Stateless).
    Ideal para subtítulos.
    """
    try:
        global _client
        if not _client: _setup_gemini()
        
        prompt = (
            f"You are a professional subtitle translator. Your task is to TRANSLATE the following text to Spanish (Neutral).\n"
            f"RULES:\n"
            f"1. Maintain the exact number of lines.\n"
            f"2. Keep the meaning accurate but natural.\n"
            f"3. Do not add explanations, just return the translated lines.\n"
            f"4. If a line is just a sound/noise/music tag (like [Music]), keep it or translate to [Música].\n\n"
            f"Input:\n{text_chunk}\n\nTranslation:"
        )
        
        resp = _client.models.generate_content(
            model="gemini-2.0-flash-exp", # Fast and smart
            contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1, 
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                ]
            )
        )
        
        if resp.text: return resp.text.strip()
        return None
        
    except Exception as e:
        print(f"Translation Pure Error: {e}")
        return None

async def enhance_subtitle_text(text_chunk, mode="punctuate"):
    """
    Mejora subtítulos usando Gemini.
    Modos:
    - 'punctuate': Mejora puntuación (¡!, ¿?, mayúsculas si grita) SIN emojis.
    - 'translate_punctuate': Traduce a Español Y mejora puntuación.
    """
    try:
        global _client
        if not _client: _setup_gemini()
        
        # Base Prompt Construction
        task_desc = ""
        if mode == "translate_punctuate":
            task_desc = (
                "TASK: Translate each line to SPANISH (Neutral). \n"
                "IMPORTANT: Focus on EXPRESSIVE PUNCTUATION based on context.\n"
                "- If it looks like a question, use '¿?'.\n"
                "- If it looks like a scream or strong emotion, use '¡!' or UPPERCASE if extreme.\n"
                "- NO EMOJIS. JUST TEXT AND PUNCTUATION."
            )
        else: # punctuate only
            task_desc = (
                "TASK: Improve the punctuation of the text keeping the same language.\n"
                "IMPORTANT: Focus on EXPRESSIVE PUNCTUATION.\n"
                "- If it looks like a question, ensure it has '¿?'.\n"
                "- If it looks like a scream/yell, ensure it has '¡!' or UPPERCASE.\n"
                "- NO EMOJIS. JUST TEXT AND PUNCTUATION."
            )
            
        prompt = (
            f"You are a subtitle expert. {task_desc}\n"
            f"CRITICAL RULES:\n"
            f"1. OUTPUT MUST HAVE EXACTLY THE SAME NUMBER OF LINES AS INPUT.\n"
            f"2. Do not merge lines. Do not split lines.\n"
            f"3. Do not add explanations. ONLY return the processed lines.\n"
            f"4. If a line is empty, return empty line.\n\n"
            f"INPUT BLOCK:\n{text_chunk}\n\nOUTPUT BLOCK:"
        )
        
        import asyncio
        loop = asyncio.get_running_loop()
        
        def run_gemini():
            return _client.models.generate_content(
                model="gemini-2.0-flash-exp",
                contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    safety_settings=[
                        types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                        types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE")
                    ]
                )
            )

        resp = await loop.run_in_executor(None, run_gemini)
        
        if resp.text: return resp.text.strip()
        return None

    except Exception as e:
        print(f"Enhance Subtitle Error: {e}")
        return None
