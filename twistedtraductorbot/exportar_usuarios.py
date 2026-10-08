import asyncio
from firebase_service import load_all_user_configs

async def main():
    print("Obteniendo usuarios desde Firebase...")
    users = await load_all_user_configs()
    
    with open('lista_usuarios.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total de usuarios registrados: {len(users)}\n")
        f.write("-" * 50 + "\n")
        
        for uid, data in users.items():
            first_name = data.get('first_name', 'Desconocido')
            username = data.get('username', 'Sin_username')
            f.write(f"ID: {uid} | Nombre: {first_name} | Username: @{username}\n")
            
    print(f"¡Listo! Se ha guardado la lista de {len(users)} usuarios en el archivo 'lista_usuarios.txt'.")

if __name__ == '__main__':
    asyncio.run(main())
