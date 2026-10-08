
import { initializeApp } from "firebase/app";
import { getFirestore, collection, getDocs, orderBy, query } from "firebase/firestore";

const firebaseConfig = {
    apiKey: "AIzaSyAH3jvbe0_QLzIuuv5kTMK8246HNvohvfE",
    authDomain: "twistedbrody-9d163.firebaseapp.com",
    projectId: "twistedbrody-9d163",
    storageBucket: "twistedbrody-9d163.firebasestorage.app",
    messagingSenderId: "733213514129",
    appId: "1:733213514129:web:e9694684f5c3994ed06230",
    measurementId: "G-N8TQ7MY42W"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

async function checkDB() {
    console.log("--- DEBUGGING FIRESTORE ---");
    try {
        const mangasRef = collection(db, 'mangas');

        // 1. Count Total (Raw)
        const snapshotRaw = await getDocs(mangasRef);
        console.log(`[RAW CHECK] Total Documents in 'mangas': ${snapshotRaw.size}`);

        if (snapshotRaw.size > 0) {
            console.log("Sample ID:", snapshotRaw.docs[0].id);
            console.log("Sample Data:", snapshotRaw.docs[0].data());
        }

        // 2. Count with Query (orderBy)
        try {
            const q = query(mangasRef, orderBy('created_at', 'desc'));
            const snapshotQuery = await getDocs(q);
            console.log(`[QUERY CHECK] Documents with orderBy('created_at'): ${snapshotQuery.size}`);
        } catch (e) {
            console.error("[QUERY FAIL] orderBy failed. Likely missing index or field:", e.message);
        }

    } catch (error) {
        console.error("CRITICAL ERROR:", error);
    }
}

checkDB();
