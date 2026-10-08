import os

BOT_PATH = r"c:\Users\Gonzalo\Desktop\bot compelte stramger\bot.py"

with open(BOT_PATH, "r", encoding="utf-8") as f:
    code = f.read()

old_resend = """                        else:
                            await conv.send_message("❌ Tipo de documento no reconocido.")
                            
                        # Resend the main menu immediately so they can input something else
                        msg = await conv.send_message(
                            "🛠️ **Modo Editor Activado**\\n\\n¿Qué más deseas gestionar?",
                            buttons=[
                                [Button.inline("🎬 Gestionar Películas", b"ed_mov")],
                                [Button.inline("📺 Gestionar Series", b"ed_ser")],
                                [Button.inline("❌ Salir del Editor", b"ed_exit")]
                            ]
                        )
                    else:"""

new_resend = """                        else:
                            await conv.send_message("❌ Tipo de documento no reconocido.")
                    else:"""

code = code.replace(old_resend, new_resend)

with open(BOT_PATH, "w", encoding="utf-8") as f:
    f.write(code)

print("Removed main menu resend.")
