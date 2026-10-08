import os
import sys
import asyncio
from aiohttp import web
import bot

# Puerto de la aplicación configurado para Hugging Face (por defecto 7080)
PORT = int(os.environ.get("PORT", 7080))

async def handle_home(request):
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Bot Unidor de Videos - Estado</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap" rel="stylesheet">
        <style>
            :root {
                --bg-gradient: linear-gradient(135deg, #07050f 0%, #0d0a21 50%, #030206 100%);
                --card-bg: rgba(255, 255, 255, 0.03);
                --card-border: rgba(255, 255, 255, 0.08);
                --text-primary: #ffffff;
                --text-secondary: #a0aec0;
                --accent: #3b82f6;
                --accent-glow: rgba(59, 130, 246, 0.4);
                --success: #10b981;
                --success-glow: rgba(16, 185, 129, 0.4);
            }
            * {
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }
            body {
                font-family: 'Outfit', sans-serif;
                background: var(--bg-gradient);
                color: var(--text-primary);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                overflow-x: hidden;
            }
            .container {
                width: 90%;
                max-width: 600px;
                padding: 40px;
                background: var(--card-bg);
                border: 1px solid var(--card-border);
                border-radius: 24px;
                backdrop-filter: blur(20px);
                box-shadow: 0 20px 50px rgba(0, 0, 0, 0.5);
                text-align: center;
                position: relative;
            }
            .container::before {
                content: '';
                position: absolute;
                top: -2px;
                left: -2px;
                right: -2px;
                bottom: -2px;
                background: linear-gradient(45deg, var(--accent), #6366f1, #10b981);
                border-radius: 26px;
                z-index: -1;
                opacity: 0.15;
            }
            h1 {
                font-size: 2.3rem;
                font-weight: 800;
                margin-bottom: 10px;
                background: linear-gradient(to right, #60a5fa, #818cf8, #34d399);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .status-badge {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                padding: 8px 20px;
                background: rgba(16, 185, 129, 0.08);
                border: 1px solid var(--success);
                color: #34d399;
                border-radius: 9999px;
                font-weight: 600;
                font-size: 0.95rem;
                margin-top: 15px;
                margin-bottom: 30px;
                box-shadow: 0 0 15px var(--success-glow);
                animation: pulse 2.5s infinite;
            }
            @keyframes pulse {
                0% { box-shadow: 0 0 5px var(--success-glow); }
                50% { box-shadow: 0 0 20px var(--success-glow); }
                100% { box-shadow: 0 0 5px var(--success-glow); }
            }
            p.description {
                color: var(--text-secondary);
                font-size: 1.05rem;
                line-height: 1.6;
                margin-bottom: 30px;
            }
            .commands-card {
                background: rgba(0, 0, 0, 0.35);
                border: 1px solid var(--card-border);
                border-radius: 16px;
                padding: 20px;
                text-align: left;
            }
            .commands-card h3 {
                font-size: 1.15rem;
                margin-bottom: 15px;
                color: #818cf8;
            }
            ul {
                list-style: none;
            }
            li {
                margin-bottom: 12px;
                font-size: 0.95rem;
                display: flex;
                align-items: center;
                gap: 10px;
            }
            li code {
                background: rgba(255, 255, 255, 0.08);
                padding: 3px 8px;
                border-radius: 6px;
                color: #e2e8f0;
                font-family: monospace;
                font-size: 0.9rem;
                border: 1px solid rgba(255, 255, 255, 0.05);
            }
            li span {
                color: var(--text-secondary);
            }
            footer {
                margin-top: 30px;
                font-size: 0.8rem;
                color: #4a5568;
            }
            .btn-danger {
                display: inline-flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                width: 100%;
                padding: 14px 20px;
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.3) 100%);
                border: 1px solid rgba(239, 68, 68, 0.35);
                color: #fca5a5;
                font-family: 'Outfit', sans-serif;
                font-size: 1rem;
                font-weight: 600;
                border-radius: 12px;
                cursor: pointer;
                transition: all 0.3s ease;
                margin-top: 24px;
                box-shadow: 0 4px 15px rgba(220, 38, 38, 0.05);
            }
            .btn-danger:hover {
                background: linear-gradient(135deg, rgba(239, 68, 68, 0.25) 0%, rgba(220, 38, 38, 0.5) 100%);
                border-color: rgba(239, 68, 68, 0.7);
                color: #ffffff;
                box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
                transform: translateY(-2.5px);
            }
            .btn-danger:active {
                transform: translateY(0.5px);
            }
            .btn-danger:disabled {
                opacity: 0.6;
                cursor: not-allowed;
                transform: none;
                box-shadow: none;
            }
            @keyframes spin {
                to { transform: rotate(360deg); }
            }
            .spinner {
                display: inline-block;
                width: 16px;
                height: 16px;
                border: 2px solid currentColor;
                border-top-color: transparent;
                border-radius: 50%;
                animation: spin 0.8s linear infinite;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Bot Unidor de Videos</h1>
            <div class="status-badge">
                <span style="width: 8px; height: 8px; background: #10b981; border-radius: 50%;"></span>
                Online & Activo en Hugging Face
            </div>
            <p class="description">
                Tu bot de Telegram está ejecutándose correctamente en segundo plano y expuesto en el puerto 7080.
            </p>
            <div class="commands-card">
                <h3>Comandos Disponibles:</h3>
                <ul>
                    <li><code>/sesion</code> o <code>/start</code> <span>- Iniciar bot y ver estado de la cola</span></li>
                    <li><code>/unir</code> <span>- Forzar descarga y unión de videos en cola</span></li>
                    <li><code>/limpiar</code> <span>- Vaciar videos de la cola actual</span></li>
                    <li><code>/cancelar</code> <span>- Abortar unión activa y reiniciar el bot</span></li>
                </ul>
            </div>
            
            <button class="btn-danger" id="btn-restart" onclick="triggerRestart()">
                <svg style="width: 18px; height: 18px; fill: currentColor;" viewBox="0 0 24 24">
                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm4-11H8v6h8V9z"/>
                </svg>
                Cancelar Unión y Reiniciar Bot
            </button>
            
            <footer>
                Powered by Antigravity AI & Hugging Face Spaces
            </footer>
        </div>
        
        <script>
            async function triggerRestart() {
                if (confirm('¿Estás seguro de que deseas cancelar cualquier unión activa y reiniciar el bot?')) {
                    const btn = document.getElementById('btn-restart');
                    btn.disabled = true;
                    btn.innerHTML = '<span class="spinner"></span> Reiniciando el bot...';
                    
                    try {
                        const response = await fetch('/restart', { method: 'POST' });
                        if (response.ok) {
                            setTimeout(() => {
                                alert('El bot se está reiniciando. La página se recargará automáticamente.');
                                window.location.reload();
                            }, 3500);
                        } else {
                            alert('Error al intentar reiniciar el bot.');
                            btn.disabled = false;
                            btn.innerHTML = `
                                <svg style="width: 18px; height: 18px; fill: currentColor;" viewBox="0 0 24 24">
                                    <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm4-11H8v6h8V9z"/>
                                </svg>
                                Cancelar Unión y Reiniciar Bot
                            `;
                        }
                    } catch (e) {
                        setTimeout(() => {
                            window.location.reload();
                        }, 4500);
                    }
                }
            }
        </script>
    </body>
    </html>
    """
    return web.Response(text=html_content, content_type="text/html")

web_runner = None

async def handle_restart(request):
    print("\033[91m[Web Server] Recibida solicitud de reinicio desde el panel web...\033[0m")
    asyncio.create_task(perform_restart())
    return web.Response(text="Reiniciando el bot...", content_type="text/plain")

async def perform_restart():
    await asyncio.sleep(0.5)
    print("\033[93m[Reinicio] Ejecutando cancelaciones de tareas y limpieza...\033[0m")
    try:
        await bot.cancel_all_processing()
    except Exception as e:
        print(f"[Error de Limpieza en Reinicio] {e}")
        
    try:
        await bot.client.disconnect()
    except Exception as e:
        print(f"[Error de Desconexión en Reinicio] {e}")
        
    global web_runner
    if web_runner:
        print("[Reinicio] Deteniendo servidor web...")
        try:
            await web_runner.cleanup()
        except Exception as e:
            print(f"[Error de Apagado de Web Server] {e}")
            
    print("\033[95m[Reinicio] Re-ejecutando script python...\033[0m")
    os.execv(sys.executable, [sys.executable] + sys.argv)

async def start_web_server():
    global web_runner
    app = web.Application()
    app.router.add_get("/", handle_home)
    app.router.add_post("/restart", handle_restart)
    web_runner = web.AppRunner(app)
    await web_runner.setup()
    site = web.TCPSite(web_runner, "0.0.0.0", PORT)
    await site.start()
    print(f"\033[92m[Web Server] Ejecutándose y escuchando en el puerto {PORT}\033[0m")

async def main():
    # Iniciar servidor web de estado
    await start_web_server()
    # Iniciar el bot de Telegram (se ejecutará indefinidamente)
    await bot.main()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
