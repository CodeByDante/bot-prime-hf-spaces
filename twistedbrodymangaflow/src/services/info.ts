import { db } from '../lib/firebase';
import { doc, getDoc, setDoc, onSnapshot } from 'firebase/firestore';

const SETTINGS_COLLECTION = 'settings';
const INFO_DOC = 'info';

export interface InfoData {
    content: string;
    updatedAt: string;
}

const DEFAULT_CONTENT = `# Bienvenid@ a Twisted Brody MangaFlow
¡Tu plataforma definitiva para la gestión y lectura de mangas!

Este proyecto nació con la misión de ofrecer una experiencia de lectura fluida, moderna y sin interrupciones, diseñada por fans para fans.

## 🌟 Características Principales

*   **⚡ Lectura sin límites:** Disfruta de una interfaz optimizada, rápida y responsiva.
*   **📥 Descargas Flexibles:** Baja tus capítulos favoritos en formato **ZIP** o **PDF** para leer offline.
*   **🔄 Conversión Inteligente:** Nuestro servidor procesa las imágenes para darte la mejor calidad y compatibilidad.

## 🤝 Comunidad y Apoyo

Este es un proyecto **sin fines de lucro**, desarrollado por pura pasión.

Sin embargo, si valoras mi trabajo y quieres apoyarme para mantener el proyecto vivo, puedes suscribirte a mi **Patreon**. ¡Tu apoyo significa mucho!

*   [**💜 Apóyame en Patreon**](https://www.patreon.com/cw/Twistedbrody)

### 💡 ¿Tienes nuevas ideas?
¡Quiero escucharlas! Si tienes sugerencias, feedback o ideas locas, háblame directamente:

*   **Telegram:** [@twistedbrodyoficial](https://t.me/twistedbrodyoficial)

También puedes unirte a nuestros canales:
*   [Canal Principal](https://t.me/twistedbrody)
*   [Canal Hub](https://t.me/+CmmZFHM9hpViYzMx)
*   [X (Twitter)](https://x.com/TwistedBrody)

---
> **Disclaimer:** Todo el contenido es propiedad de sus respectivos autores. Apoya el material original siempre que sea posible.


`;


export async function getInfo(): Promise<InfoData | null> {
    const docRef = doc(db, SETTINGS_COLLECTION, INFO_DOC);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
        return docSnap.data() as InfoData;
    }
    return null;
}

export async function saveInfo(content: string): Promise<void> {
    const docRef = doc(db, SETTINGS_COLLECTION, INFO_DOC);
    const data: InfoData = {
        content,
        updatedAt: new Date().toISOString()
    };
    await setDoc(docRef, data);
}

export function subscribeToInfo(callback: (data: InfoData | null) => void) {
    const docRef = doc(db, SETTINGS_COLLECTION, INFO_DOC);
    return onSnapshot(docRef, (doc) => {
        if (doc.exists()) {
            callback(doc.data() as InfoData);
        } else {
            callback({ content: DEFAULT_CONTENT, updatedAt: new Date().toISOString() });
        }
    });
}
