import { db } from '../lib/firebase';
import { doc, getDoc, setDoc, onSnapshot } from 'firebase/firestore';

const SETTINGS_COLLECTION = 'settings';
const ANNOUNCEMENT_DOC = 'announcement';

export interface AnnouncementData {
    text: string;
    updatedAt: string;
    expiresAt: string | null;
}

export async function getAnnouncement(): Promise<AnnouncementData | null> {
    const docRef = doc(db, SETTINGS_COLLECTION, ANNOUNCEMENT_DOC);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
        return docSnap.data() as AnnouncementData;
    }
    return null;
}

export async function saveAnnouncement(text: string, durationMs: number | null): Promise<void> {
    const docRef = doc(db, SETTINGS_COLLECTION, ANNOUNCEMENT_DOC);
    const now = new Date();
    let expiresAt: string | null = null;

    if (durationMs) {
        expiresAt = new Date(now.getTime() + durationMs).toISOString();
    }

    const data: AnnouncementData = {
        text,
        updatedAt: now.toISOString(),
        expiresAt
    };
    await setDoc(docRef, data);
}

export function subscribeToAnnouncement(callback: (data: AnnouncementData | null) => void) {
    const docRef = doc(db, SETTINGS_COLLECTION, ANNOUNCEMENT_DOC);
    return onSnapshot(docRef, (doc) => {
        if (doc.exists()) {
            callback(doc.data() as AnnouncementData);
        } else {
            callback(null);
        }
    });
}
