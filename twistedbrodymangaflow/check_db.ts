import { initializeApp } from 'firebase/app';
import { getFirestore, collection, getDocs, query, orderBy, limit } from 'firebase/firestore';

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

async function check() {
  console.log("Fetching mangas from DB...");
  const q = query(collection(db, 'mangas'), orderBy('created_at', 'desc'), limit(3));
  const snap = await getDocs(q);
  
  if (snap.empty) {
    console.log("NO MANGAS IN DB!");
  } else {
    snap.forEach(doc => {
      console.log(`Manga ${doc.id}: ${doc.data().title}`);
      console.log(JSON.stringify(doc.data(), null, 2));
    });
  }

  console.log("\nFetching chapters...");
  const q2 = query(collection(db, 'chapters'), orderBy('created_at', 'desc'), limit(3));
  const snap2 = await getDocs(q2);
  if (snap2.empty) {
    console.log("NO CHAPTERS IN DB!");
  } else {
    snap2.forEach(doc => {
      console.log(`Chapter ${doc.id}: ${doc.data().title}`);
      console.log(JSON.stringify(doc.data(), null, 2));
    });
  }
}

check().catch(console.error).finally(() => process.exit(0));
