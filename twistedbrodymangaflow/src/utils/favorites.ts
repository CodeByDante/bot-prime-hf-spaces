import { db } from '../lib/firebase';
import { collection, doc, setDoc, deleteDoc, onSnapshot } from 'firebase/firestore';

export interface FavoriteImage {
  id: string; // unique ID for the favorite
  mangaId: string;
  mangaTitle: string;
  pageUrl: string;
  pageIndex: number;
  addedAt: number;
}

const FAVORITES_KEY = 'twistedbrody_favorites';

let memCache: FavoriteImage[] = [];
try {
  const data = localStorage.getItem(FAVORITES_KEY);
  if (data) memCache = JSON.parse(data);
} catch (e) {}

let listeners: (() => void)[] = [];

export function subscribeFavorites(callback: () => void) {
  listeners.push(callback);
  return () => {
    listeners = listeners.filter(l => l !== callback);
  };
}

function notify() {
  listeners.forEach(l => l());
}

// Firebase sync
try {
  onSnapshot(collection(db, 'favorites'), (snapshot) => {
    const newFavs: FavoriteImage[] = [];
    snapshot.forEach(docSnap => {
      newFavs.push(docSnap.data() as FavoriteImage);
    });
    memCache = newFavs;
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(memCache));
    } catch (e) {}
    notify();
  });
} catch (error) {
  console.error("Error setting up Firebase favorites sync", error);
}

export function getFavorites(): FavoriteImage[] {
  return memCache;
}

export async function addFavorite(favorite: Omit<FavoriteImage, 'id' | 'addedAt'>) {
  const newFav: FavoriteImage = {
    ...favorite,
    id: `${favorite.mangaId}_${favorite.pageIndex}`,
    addedAt: Date.now()
  };
  
  // Prevent duplicates
  if (!memCache.some(f => f.id === newFav.id)) {
    // Optimistic update
    memCache.push(newFav);
    notify();
    try {
      await setDoc(doc(db, 'favorites', newFav.id), newFav);
    } catch (error) {
      console.error("Error saving favorite to Firebase", error);
    }
  }
  return newFav;
}

export async function removeFavorite(id: string) {
  // Optimistic update
  memCache = memCache.filter(f => f.id !== id);
  notify();
  try {
    await deleteDoc(doc(db, 'favorites', id));
  } catch (error) {
    console.error("Error removing favorite from Firebase", error);
  }
}

export function isFavorite(mangaId: string, pageIndex: number): boolean {
  const id = `${mangaId}_${pageIndex}`;
  return memCache.some(f => f.id === id);
}
