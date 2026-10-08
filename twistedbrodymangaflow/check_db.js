import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs } from 'firebase/firestore';

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

async function run() {
  const q = collection(db, "chapters");
  const snapshot = await getDocs(q);
  if (!snapshot.empty) {
    const doc = snapshot.docs[0];
    const data = doc.data();
    console.log("Manga ID:", data.manga_id || data.mangaId);
    console.log("Original Pages:", data.original_pages?.slice(0, 2));
    console.log("Pages:", data.pages?.slice(0, 2));
  }
}
run();
