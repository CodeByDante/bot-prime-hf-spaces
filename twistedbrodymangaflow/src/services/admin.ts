import { db } from '../lib/firebase';
import { doc, getDoc, setDoc, updateDoc, arrayUnion, arrayRemove } from 'firebase/firestore';

const ADMIN_SETTINGS_ID = 'general';
const ADMIN_COLLECTION = 'admin_settings';

// Initial hardcoded owners
const OWNERS = [
    'gonzalosalvadorloyolahuarauya@gmail.com',
    'loyolahuarauyagonzalosalvador@gmail.com',
    'brody.loyola@gmail.com'
];

export interface AdminSettings {
    allowed_emails: string[];
}

export async function isUserAdmin(email: string): Promise<boolean> {
    if (!email) return false;

    // Check if owner
    if (OWNERS.includes(email)) return true;

    try {
        const docRef = doc(db, ADMIN_COLLECTION, ADMIN_SETTINGS_ID);
        const docSnap = await getDoc(docRef);

        if (docSnap.exists()) {
            const data = docSnap.data() as AdminSettings;
            return data.allowed_emails.includes(email);
        }
        return false;
    } catch (error) {
        console.error('Error checking admin status:', error);
        return false;
    }
}

export async function getAllowedEmails(): Promise<string[]> {
    try {
        const docRef = doc(db, ADMIN_COLLECTION, ADMIN_SETTINGS_ID);
        const docSnap = await getDoc(docRef);

        if (docSnap.exists()) {
            const data = docSnap.data() as AdminSettings;
            // Combine owners and allowed emails, removing duplicates
            return Array.from(new Set([...OWNERS, ...data.allowed_emails]));
        }
        return [...OWNERS];
    } catch (error) {
        console.error('Error getting allowed emails:', error);
        return [...OWNERS];
    }
}

export async function addAdminEmail(email: string): Promise<void> {
    const docRef = doc(db, ADMIN_COLLECTION, ADMIN_SETTINGS_ID);

    try {
        await updateDoc(docRef, {
            allowed_emails: arrayUnion(email)
        });
    } catch (error: any) {
        // If document doesn't exist, create it
        if (error.code === 'not-found' || error.message.includes('No document to update')) {
            await setDoc(docRef, {
                allowed_emails: [email]
            });
        } else {
            throw error;
        }
    }
}

export async function removeAdminEmail(email: string): Promise<void> {
    if (OWNERS.includes(email)) {
        throw new Error('No puedes eliminar a un propietario.');
    }

    const docRef = doc(db, ADMIN_COLLECTION, ADMIN_SETTINGS_ID);
    await updateDoc(docRef, {
        allowed_emails: arrayRemove(email)
    });
}
