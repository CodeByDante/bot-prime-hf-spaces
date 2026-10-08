import { initializeApp } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';
import { getStorage } from 'firebase/storage';

const firebaseConfig = {
  apiKey: "AIzaSyAH3jvbe0_QLzIuuv5kTMK8246HNvohvfE",
  authDomain: "twistedbrody-9d163.firebaseapp.com",
  projectId: "twistedbrody-9d163",
  storageBucket: "twistedbrody-9d163.firebasestorage.app",
  messagingSenderId: "733213514129",
  appId: "1:733213514129:web:e9694684f5c3994ed06230",
  measurementId: "G-N8TQ7MY42W"
};

import { getAuth, GoogleAuthProvider } from 'firebase/auth';

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
export const storage = getStorage(app);
export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
