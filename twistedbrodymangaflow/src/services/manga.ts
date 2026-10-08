import { db } from '../lib/firebase';
import {
  collection,
  getDocs,
  doc,
  getDoc,
  addDoc,
  updateDoc,
  deleteDoc,
  increment,
  query,
  orderBy,
  where,
  Timestamp,
  onSnapshot,
  Unsubscribe,
  writeBatch,
  deleteField
} from 'firebase/firestore';
import { Manga, Category, Chapter } from '../types/manga';

function cleanUndefinedDeep(obj: any): any {
  if (obj === null || obj === undefined) {
    return undefined;
  }

  if (Array.isArray(obj)) {
    const cleaned = obj
      .map(item => cleanUndefinedDeep(item))
      .filter(item => item !== undefined && item !== null && item !== '');
    return cleaned.length > 0 ? cleaned : undefined;
  }

  if (typeof obj === 'object' && !(obj instanceof Timestamp)) {
    const cleaned: any = {};
    for (const key in obj) {
      if (obj.hasOwnProperty(key)) {
        const value = cleanUndefinedDeep(obj[key]);
        if (value !== undefined && value !== null) {
          cleaned[key] = value;
        }
      }
    }
    return Object.keys(cleaned).length > 0 ? cleaned : undefined;
  }

  return obj;
}

// Helper functions for localStorage
const STORAGE_KEYS = {
  ALL_MANGAS: 'mangalib_all_v2',
  MANGA_PREFIX: 'mangalib_detail_v2_',
};

function saveLocal(key: string, data: any): void {
  try {
    localStorage.setItem(key, JSON.stringify(data));
  } catch (error) {
    console.warn(`Error saving ${key} to localStorage`, error);
  }
}

export async function updateMangaTitles(updates: { id: string, title: string }[]): Promise<void> {
  const now = Timestamp.now();
  const promises = updates.map(async (update) => {
    const docRef = doc(db, 'mangas', update.id);
    await updateDoc(docRef, { title: update.title, updated_at: now });
    
    const cached = mangaCache.get(update.id);
    if (cached) {
      cached.title = update.title;
      cached.updated_at = now.toDate().toISOString();
      mangaCache.set(update.id, cached);
      saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${update.id}`, cached);
    }
  });
  await Promise.all(promises);
}

function removeLocal(key: string): void {
  try {
    localStorage.removeItem(key);
  } catch (error) {
    console.warn(`Error removing ${key} from localStorage`, error);
  }
}

export async function getAllMangas(): Promise<Manga[]> {
  // SYNC FIX: Always fetch from Firebase to ensure data consistency across devices.
  // Disabled local cache check.

  const q = query(collection(db, 'mangas'), orderBy('created_at', 'desc'));
  const querySnapshot = await getDocs(q);

  // Fetch all categories once
  const categoriesSnapshot = await getDocs(collection(db, 'categories'));
  const allCategories = categoriesSnapshot.docs.reduce((acc, doc) => {
    acc[doc.id] = { id: doc.id, ...doc.data() } as Category;
    return acc;
  }, {} as Record<string, Category>);

  const mangas = await Promise.all(
    querySnapshot.docs.map(async (mangaDoc) => {
      try {
        const mangaData = mangaDoc.data();

        // FAIL-SAFE: Check if created_at is valid timestamp
        let createdAtIso = new Date().toISOString();
        if (mangaData.created_at?.toDate) {
          createdAtIso = mangaData.created_at.toDate().toISOString();
        } else if (mangaData.created_at) {
          // Handle legacy string dates or other formats if necessary
          createdAtIso = new Date(mangaData.created_at).toISOString();
        }

        let updatedAtIso = createdAtIso;
        if (mangaData.updated_at?.toDate) {
          updatedAtIso = mangaData.updated_at.toDate().toISOString();
        }

        const chaptersQuery = query(
          collection(db, 'chapters'),
          where('manga_id', '==', mangaDoc.id)
        );
        const chaptersSnapshot = await getDocs(chaptersQuery);
        const chapters = chaptersSnapshot.docs
          .map(chapterDoc => {
            const chapterData = chapterDoc.data();
            // Fail-safe for chapter dates too
            const chCreatedAt = chapterData.created_at?.toDate ? chapterData.created_at.toDate().toISOString() : new Date().toISOString();
            const chUpdatedAt = chapterData.updated_at?.toDate ? chapterData.updated_at.toDate().toISOString() : new Date().toISOString();

            return {
              id: chapterDoc.id,
              manga_id: chapterData.manga_id,
              number: chapterData.number,
              title: chapterData.title,
              pages: chapterData.pages || [],
              page_formats: chapterData.page_formats || [],
              original_pages: chapterData.original_pages || [],
              created_at: chCreatedAt,
              updated_at: chUpdatedAt,
            } as Chapter;
          })
          .sort((a, b) => a.number - b.number);

        // Map category IDs to full category objects
        const categoryIds = (mangaData.categories as string[]) || [];
        const populatedCategories = categoryIds
          .map(id => allCategories[id])
          .filter(c => c !== undefined);

        return {
          id: mangaDoc.id,
          ...mangaData,
          created_at: createdAtIso,
          updated_at: updatedAtIso,
          categories: populatedCategories,
          chapters,
        } as Manga;
      } catch (e) {
        console.error(`[DATA ERROR] Skipping corrupt manga ${mangaDoc.id}:`, e);
        return null;
      }
    })
  );

  const validMangas = mangas.filter(m => m !== null) as Manga[];
  console.log(`[DATA] Loaded ${validMangas.length} mangas (Skipped ${mangas.length - validMangas.length} corrupt)`);

  return validMangas;
}

const mangaCache = new Map<string, Manga>();

export async function getMangaById(id: string): Promise<Manga | null> {
  // SYNC FIX: Always fetch fresh data.
  // if (mangaCache.has(id)) { return mangaCache.get(id)!; }
  // const localData = getLocal<Manga>(`${STORAGE_KEYS.MANGA_PREFIX}${id}`); ...

  const docRef = doc(db, 'mangas', id);
  const docSnap = await getDoc(docRef);

  if (!docSnap.exists()) return null;

  const data = docSnap.data();

  const chaptersQuery = query(collection(db, 'chapters'), where('manga_id', '==', id));
  const chaptersSnapshot = await getDocs(chaptersQuery);
  const chapters = chaptersSnapshot.docs
    .map(doc => {
      const chapterData = doc.data();
      return {
        id: doc.id,
        manga_id: chapterData.manga_id,
        number: chapterData.number,
        title: chapterData.title,
        pages: chapterData.pages || [],
        page_formats: chapterData.page_formats || [],
        original_pages: chapterData.original_pages || [],
        created_at: (chapterData.created_at as Timestamp).toDate().toISOString(),
        updated_at: (chapterData.updated_at as Timestamp).toDate().toISOString(),
      } as Chapter;
    })
    .sort((a, b) => a.number - b.number);

  const categoryIds = data.categories || [];
  const categories: Category[] = [];

  for (const categoryId of categoryIds) {
    const catDocRef = doc(db, 'categories', categoryId);
    const catDocSnap = await getDoc(catDocRef);
    if (catDocSnap.exists()) {
      categories.push({
        id: catDocSnap.id,
        ...catDocSnap.data(),
        created_at: catDocSnap.data().created_at?.toDate?.().toISOString() || new Date().toISOString(),
      } as Category);
    }
  }

  const mangaData = {
    id: docSnap.id,
    ...data,
    created_at: (data.created_at as Timestamp).toDate().toISOString(),
    categories,
    chapters,
    updated_at: data.updated_at ? (data.updated_at as Timestamp).toDate().toISOString() : (data.created_at as Timestamp).toDate().toISOString(),
  } as Manga;

  // Save to cache
  mangaCache.set(id, mangaData);
  saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${id}`, mangaData);

  return mangaData;
}

export function subscribeToManga(id: string, callback: (manga: Manga | null) => void): Unsubscribe {
  const docRef = doc(db, 'mangas', id);

  return onSnapshot(docRef, async (docSnap) => {
    if (!docSnap.exists()) {
      callback(null);
      return;
    }

    const data = docSnap.data();

    // We also need chapters and categories
    // Note: This inside a snapshot might be expensive if chapters change often, 
    // but for views increment only the manga doc changes, so this is fine.
    // However, fast view updates might trigger this often.

    // To avoid refetching sub-collections on every view increment if not needed,
    // we could optimize, but for now we follow the pattern to ensure data consistency.
    // Actually, `getDocs` inside a snapshot callback for every view increment is bad practice (Read accumulation).
    // The view count is on the main doc. The chapters/categories usually don't change.
    // We can rely on a mix: get the cached chapters/categories or fetch them if missing.
    // But since the user wants real-time, let's assume fully fresh data is safer.
    // Or better: Use the cache for heavy stuff and update the fields from the docSnap.

    // Let's reuse getMangaById logic but with the new data from snapshot.
    // Actually, passing the snapshot data to a helper would be better.
    // For simplicity and preventing "infinite reads" loop if not careful:

    // Strategy: Just update the fields present in the manga document (like views)
    // and assume chapters/categories are relatively static or handled separately.
    // But `manga` object needs chapters/categories to render `ComicDetail`.

    // Let's grab the existing cache if available to fill in the gaps (chapters), 
    // effectively only updating the 'manga' doc fields (views, title, etc).

    let cached = mangaCache.get(id);
    let chapters = cached?.chapters || [];
    let categories = cached?.categories || [];

    // If not in cache, we MUST fetch chapters/categories at least once.
    if (!cached) {
      // Fallback to fetch data once
      // But doing async work in snapshot callback is tricky if we want to return immediately.
      // We will do the fetch.
      const chaptersQuery = query(collection(db, 'chapters'), where('manga_id', '==', id));
      const chaptersSnapshot = await getDocs(chaptersQuery);
      chapters = chaptersSnapshot.docs
        .map(c => ({
          id: c.id,
          ...c.data(),
          created_at: (c.data().created_at as Timestamp).toDate().toISOString(),
          updated_at: (c.data().updated_at as Timestamp).toDate().toISOString(),
        } as any))
        .sort((a: any, b: any) => a.number - b.number);

      const categoryIds = data.categories || [];
      categories = []; // We would verify categories here, but skipping for brevity/perf to avoid N+1 reads loop in high frequency.
      // Ideally categories are embedded or we trust the component to handle.
      // Let's stick to the current architecture.
      // Fetch categories
      for (const catId of categoryIds) {
        const catDoc = await getDoc(doc(db, 'categories', catId));
        if (catDoc.exists()) categories.push({ id: catDoc.id, ...catDoc.data() } as any);
      }
    }

    const updatedManga: Manga = {
      id: docSnap.id,
      ...data,
      chapters,
      categories,
      created_at: (data.created_at as Timestamp).toDate().toISOString(),
      updated_at: data.updated_at ? (data.updated_at as Timestamp).toDate().toISOString() : (data.created_at as Timestamp).toDate().toISOString(),
    } as Manga;

    // Update cache
    mangaCache.set(id, updatedManga);
    saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${id}`, updatedManga);

    callback(updatedManga);
  });
}

export async function createManga(manga: {
  title: string;
  author: string;
  description?: string;
  thumbnail_url?: string;
  cover_url?: string;
  status?: string;
  categoryIds?: string[];
  is_decensored?: boolean;
  is_bn?: boolean;
  is_color?: boolean;
  section?: 'flow' | 'patreon';
}): Promise<Manga> {
  const now = Timestamp.now();

  const mangaData: any = {
    title: manga.title,
    author: manga.author,
    description: manga.description || '',
    status: manga.status || 'En curso',
    categories: manga.categoryIds || [],
    views: 0,
    rating: 0,
    created_at: now,
    updated_at: now,
    ...(manga.is_decensored !== undefined && { is_decensored: manga.is_decensored }),
    ...(manga.is_bn !== undefined && { is_bn: manga.is_bn }),
    ...(manga.is_color !== undefined && { is_color: manga.is_color }),
    section: manga.section || 'flow',
  };

  if (manga.thumbnail_url) {
    mangaData.thumbnail_url = manga.thumbnail_url;
  }

  if (manga.cover_url) {
    mangaData.cover_url = manga.cover_url;
  }

  const docRef = await addDoc(collection(db, 'mangas'), mangaData);

  const nowISO = new Date().toISOString();
  const data: any = {
    id: docRef.id,
    title: manga.title,
    author: manga.author,
    description: manga.description || '',
    status: manga.status || 'En curso',
    categories: manga.categoryIds || [],
    chapters: [],
    views: 0,
    rating: 0,
    created_at: nowISO,
    updated_at: nowISO,
    is_decensored: !!manga.is_decensored,
    is_bn: !!manga.is_bn,
    is_color: !!manga.is_color,
    section: manga.section || 'flow',
  };

  if (manga.thumbnail_url) {
    data.thumbnail_url = manga.thumbnail_url;
  }

  if (manga.cover_url) {
    data.cover_url = manga.cover_url;
  }

  // Use the new data to update individual cache
  mangaCache.set(data.id, data as Manga);
  saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${data.id}`, data);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);

  return data as Manga;
}

export async function getAllCategories(): Promise<Category[]> {
  const querySnapshot = await getDocs(collection(db, 'categories'));
  return querySnapshot.docs.map(doc => ({
    id: doc.id,
    ...doc.data(),
  } as Category));
}

export async function createCategory(name: string, type: 'character' | 'series' | 'genre' | 'tag' | 'other' = 'genre'): Promise<Category> {
  const docRef = await addDoc(collection(db, 'categories'), { name, type });
  const docSnap = await getDoc(docRef);

  return {
    id: docSnap.id,
    ...docSnap.data(),
  } as Category;
}

export async function deleteAllCategories(): Promise<void> {
  const categories = await getAllCategories();

  // Delete all category documents
  const deletePromises = categories.map(cat => deleteDoc(doc(db, 'categories', cat.id)));
  await Promise.all(deletePromises);

  // Update all mangas to remove category associations
  const mangas = await getAllMangas();
  const updatePromises = mangas.map(manga => {
    if (manga.categories && manga.categories.length > 0) {
      return updateDoc(doc(db, 'mangas', manga.id), { categories: [] });
    }
    return Promise.resolve();
  });
  await Promise.all(updatePromises);
}

export async function deleteCategory(categoryId: string): Promise<void> {
  const categoryRef = doc(db, 'categories', categoryId);
  await deleteDoc(categoryRef);

  // Remove from all mangas that have this category
  // Since we can't easily query array-contains for multiple mangas and update in one go without fetching,
  // we'll fetch all mangas (or use a cloud function in a real app, but here client-side):
  // Optimization: Query only mangas that MIGHT have it.
  // actually 'array-contains' is supported.
  const q = query(collection(db, 'mangas'), where('categories', 'array-contains', categoryId));
  const querySnapshot = await getDocs(q);

  const updatePromises = querySnapshot.docs.map(docSnap => {
    const mangaData = docSnap.data();
    const currentCategories = mangaData.categories as string[] || [];
    const newCategories = currentCategories.filter(id => id !== categoryId);
    return updateDoc(doc(db, 'mangas', docSnap.id), { categories: newCategories });
  });

  await Promise.all(updatePromises);
}

export async function regenerateAllMangaCategories(): Promise<{ updated: number, errors: number }> {
  try {
    const mangas = await getAllMangas();
    const categories = await getAllCategories();
    let updatedCount = 0;
    let errorCount = 0;

    // Helper to get or create category
    const getCallback = async (name: string): Promise<string> => {
      const existing = categories.find(c => c.name.toLowerCase() === name.toLowerCase());
      if (existing) return existing.id;

      try {
        const newCat = await createCategory(name);
        categories.push(newCat);
        return newCat.id;
      } catch (e) {
        console.error(`Error creating category ${name}`, e);
        return '';
      }
    };

    const delimiters = /[|()[\]{}]/g;

    for (const manga of mangas) {
      try {
        const chunks: string[] = [];

        // Parse Title
        const titleParts = manga.title.split(delimiters);
        chunks.push(...titleParts);

        // Parse Author
        if (manga.author && manga.author !== 'Anónimo') {
          const authorParts = manga.author.split(/[,&]/);
          chunks.push(...authorParts);
        }

        // Clean up
        const potentialNames = chunks
          .map(s => s.trim())
          .filter(s => s.length > 1)
          .filter(s => !['-', '_', '.', ','].includes(s));

        if (potentialNames.length === 0) continue;

        const newCategoryIds: string[] = [];

        for (const name of potentialNames) {
          const id = await getCallback(name);
          if (id && !newCategoryIds.includes(id)) {
            newCategoryIds.push(id);
          }
        }

        // Update manga if categories changed (or if it had none)
        // Even if it has some, we might be adding new ones or replacing old bad ones if we wiped them.
        // The user wiped them, so currently they should be empty.
        if (newCategoryIds.length > 0) {
          await updateDoc(doc(db, 'mangas', manga.id), { categories: newCategoryIds });
          updatedCount++;
        }

      } catch (err) {
        console.error(`Error processing manga ${manga.id}`, err);
        errorCount++;
      }
    }

    return { updated: updatedCount, errors: errorCount };
  } catch (error) {
    console.error('Error in bulk regeneration:', error);
    throw error;
  }
}

export async function createChapter(chapter: {
  manga_id: string;
  number: number;
  title: string;
  pages: string[];
  page_formats?: string[];
  original_pages?: string[];
}): Promise<Chapter> {
  const now = Timestamp.now();
  const docRef = await addDoc(collection(db, 'chapters'), {
    manga_id: chapter.manga_id,
    number: chapter.number,
    title: chapter.title,
    pages: chapter.pages,
    page_formats: chapter.page_formats || [],
    original_pages: chapter.original_pages || [],
    created_at: now,
    updated_at: now,
  });

  const docSnap = await getDoc(docRef);
  const data = docSnap.data();

  return {
    id: docSnap.id,
    manga_id: data!.manga_id,
    number: data!.number,
    title: data!.title,
    pages: data!.pages || [],
    page_formats: data!.page_formats || [],
    original_pages: data!.original_pages || [],
    created_at: (data!.created_at as Timestamp).toDate().toISOString(),
    updated_at: (data!.updated_at as Timestamp).toDate().toISOString(),
  } as Chapter;
}

export async function resetAllMangaViews(): Promise<void> {
  const mangas = await getAllMangas();
  const updatePromises = mangas.map(manga => {
    const docRef = doc(db, 'mangas', manga.id);
    return updateDoc(docRef, { views: 0 });
  });
  await Promise.all(updatePromises);
}

export async function incrementMangaViews(mangaId: string): Promise<void> {
  const docRef = doc(db, 'mangas', mangaId);
  await updateDoc(docRef, {
    views: increment(1),
  });
}

export async function updateManga(mangaId: string, manga: {
  title: string;
  author: string;
  description?: string;
  thumbnail_url?: string;
  cover_url?: string;
  status?: string;
  categoryIds?: string[];
  is_decensored?: boolean;
  is_bn?: boolean;
  is_color?: boolean;
  section?: 'flow' | 'patreon';
}): Promise<Manga> {
  const docRef = doc(db, 'mangas', mangaId);
  const now = Timestamp.now();

  const updateData: any = {
    title: manga.title,
    author: manga.author,
    categories: manga.categoryIds || [],
    updated_at: now,
    is_decensored: !!manga.is_decensored,
    is_bn: !!manga.is_bn,
    is_color: !!manga.is_color,
  };

  if (manga.section) {
    updateData.section = manga.section;
  }

  if (manga.status) {
    updateData.status = manga.status;
  }

  if (manga.description !== undefined && manga.description !== null) {
    updateData.description = manga.description;
  }

  if (manga.thumbnail_url) {
    updateData.thumbnail_url = manga.thumbnail_url;
  }

  if (manga.cover_url) {
    updateData.cover_url = manga.cover_url;
  }

  const cleanData = cleanUndefinedDeep(updateData);
  await updateDoc(docRef, cleanData);

  const docSnap = await getDoc(docRef);
  if (!docSnap.exists()) {
    throw new Error('Manga no encontrado');
  }

  const data = docSnap.data();
  const chaptersQuery = query(collection(db, 'chapters'), where('manga_id', '==', mangaId));
  const chaptersSnapshot = await getDocs(chaptersQuery);
  const chapters = chaptersSnapshot.docs
    .map(chapterDoc => {
      const chapterData = chapterDoc.data();
      return {
        id: chapterDoc.id,
        manga_id: chapterData.manga_id,
        number: chapterData.number,
        title: chapterData.title,
        pages: chapterData.pages || [],
        page_formats: chapterData.page_formats || [],
        original_pages: chapterData.original_pages || [],
        created_at: (chapterData.created_at as Timestamp).toDate().toISOString(),
        updated_at: (chapterData.updated_at as Timestamp).toDate().toISOString(),
      } as Chapter;
    })
    .sort((a, b) => a.number - b.number);

  const categoryIds = data.categories || [];
  const categories: Category[] = [];

  for (const categoryId of categoryIds) {
    const catDocRef = doc(db, 'categories', categoryId);
    const catDocSnap = await getDoc(catDocRef);
    if (catDocSnap.exists()) {
      categories.push({
        id: catDocSnap.id,
        ...catDocSnap.data(),
        created_at: catDocSnap.data().created_at?.toDate?.().toISOString() || new Date().toISOString(),
      } as Category);
    }
  }

  const updatedManga = {
    id: docSnap.id,
    ...data,
    created_at: (data.created_at as Timestamp).toDate().toISOString(),
    categories,
    chapters,
    updated_at: (data.updated_at as Timestamp).toDate().toISOString(),
  } as Manga;

  // Update individual cache
  mangaCache.set(updatedManga.id, updatedManga);
  saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${updatedManga.id}`, updatedManga);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);

  return updatedManga;
}

async function recursiveUpdateDeleted(mangaId: string, isDeleted: boolean, nowISO: string): Promise<void> {
  const mangaRef = doc(db, 'mangas', mangaId);
  await updateDoc(mangaRef, { is_deleted: isDeleted, updated_at: Timestamp.now() });

  const cached = mangaCache.get(mangaId);
  if (cached) {
    cached.is_deleted = isDeleted;
    cached.updated_at = nowISO;
    mangaCache.set(mangaId, cached);
    saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${mangaId}`, cached);
  }

  // Recursively update children
  const childrenQuery = query(collection(db, 'mangas'), where('folder_id', '==', mangaId));
  const childrenSnapshot = await getDocs(childrenQuery);
  for (const childDoc of childrenSnapshot.docs) {
    await recursiveUpdateDeleted(childDoc.id, isDeleted, nowISO);
  }
}

export async function deleteManga(mangaId: string): Promise<void> {
  // Soft Delete
  const nowISO = new Date().toISOString();
  await recursiveUpdateDeleted(mangaId, true, nowISO);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

export async function restoreManga(mangaId: string): Promise<void> {
  // Restore Soft Delete
  const nowISO = new Date().toISOString();
  await recursiveUpdateDeleted(mangaId, false, nowISO);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

async function recursivePermanentDelete(mangaId: string): Promise<void> {
  const mangaRef = doc(db, 'mangas', mangaId);

  // Recursive delete for children
  const childrenQuery = query(collection(db, 'mangas'), where('folder_id', '==', mangaId));
  const childrenSnapshot = await getDocs(childrenQuery);
  for (const childDoc of childrenSnapshot.docs) {
    await recursivePermanentDelete(childDoc.id);
  }

  // Delete chapters associated with this manga/folder
  const chaptersQuery = query(collection(db, 'chapters'), where('manga_id', '==', mangaId));
  const chaptersSnapshot = await getDocs(chaptersQuery);
  for (const chapterDoc of chaptersSnapshot.docs) {
    await deleteDoc(chapterDoc.ref);
  }

  // Delete the doc itself
  await deleteDoc(mangaRef);

  // Clean cache
  mangaCache.delete(mangaId);
  removeLocal(`${STORAGE_KEYS.MANGA_PREFIX}${mangaId}`);
}

export async function permanentDeleteManga(mangaId: string): Promise<void> {
  await recursivePermanentDelete(mangaId);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

export async function addExternalLink(mangaId: string, link: { name: string; url: string }): Promise<void> {
  const docRef = doc(db, 'mangas', mangaId);
  const docSnap = await getDoc(docRef);

  if (!docSnap.exists()) {
    throw new Error('Manga no encontrado');
  }

  const currentLinks = docSnap.data().external_links || [];
  const updateData = {
    external_links: [...currentLinks, link],
  };
  const cleanData = cleanUndefinedDeep(updateData);
  await updateDoc(docRef, cleanData);
}

export async function removeExternalLink(mangaId: string, index: number): Promise<void> {
  const docRef = doc(db, 'mangas', mangaId);
  const docSnap = await getDoc(docRef);

  if (!docSnap.exists()) {
    throw new Error('Manga no encontrado');
  }

  const currentLinks = docSnap.data().external_links || [];
  const updateData = {
    external_links: currentLinks.filter((_: any, i: number) => i !== index),
  };
  const cleanData = cleanUndefinedDeep(updateData);
  await updateDoc(docRef, cleanData);
}

function parseTitleInfo(title: string): { baseTitle: string; number: number | null } {
  const match = title.match(/^(.*?)(?:\s*(?:-|_|#|vol\.?|volume|part|cap\.?|capitulo)?\s*(\d+(?:\.\d+)?))$/i);
  if (match) {
    return {
      baseTitle: match[1].trim().toLowerCase(),
      number: parseFloat(match[2])
    };
  }
  return {
    baseTitle: title.trim().toLowerCase(),
    number: null
  };
}

export async function getRecommendations(currentMangaId: string, categoryIds: string[], title: string, limit?: number): Promise<Manga[]> {
  const allMangas = await getAllMangas();

  const currentManga = allMangas.find(m => m.id === currentMangaId);
  const currentSection = currentManga?.section || 'flow';

  const currentInfo = parseTitleInfo(title);
  
  const siblings: { manga: Manga, num: number }[] = [];
  const otherMangas: Manga[] = [];
  
  allMangas.forEach(manga => {
    if (manga.id === currentMangaId || manga.is_folder) return;
    if ((manga.section || 'flow') !== currentSection) return;
    
    const info = parseTitleInfo(manga.title);
    if (info.baseTitle === currentInfo.baseTitle && info.baseTitle.length > 0 && info.number !== null) {
      siblings.push({ manga, num: info.number });
    } else {
      otherMangas.push(manga);
    }
  });

  siblings.sort((a, b) => a.num - b.num);
  
  let orderedSiblings: Manga[] = [];
  if (currentInfo.number !== null) {
    const greater = siblings.filter(s => s.num > currentInfo.number!).map(s => s.manga);
    const smaller = siblings.filter(s => s.num < currentInfo.number!).map(s => s.manga);
    orderedSiblings = [...greater, ...smaller];
  } else {
    orderedSiblings = siblings.map(s => s.manga);
  }

  const recommendations = otherMangas
    .map(manga => {
      let score = 0;

      const mangaCategoryIds = manga.categories?.map(cat => cat.id) || [];
      const sharedCategories = categoryIds.filter(catId => mangaCategoryIds.includes(catId));
      score += sharedCategories.length * 10;

      const currentTitleWords = title.toLowerCase().split(/\s+/).filter(w => w.length > 2);
      const mangaTitleWords = manga.title.toLowerCase().split(/\s+/).filter(w => w.length > 2);
      const sharedWords = currentTitleWords.filter(word => mangaTitleWords.includes(word));
      score += sharedWords.length * 5;

      const currentAuthorWords = manga.author?.toLowerCase().split(/\s+/).filter(w => w.length > 2) || [];
      const sharedAuthorWords = currentTitleWords.filter(word => currentAuthorWords.includes(word));
      score += sharedAuthorWords.length * 3;

      return { manga, score };
    })
    .filter(item => item.score > 0)
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      const titleA = a.manga.title.toLowerCase();
      const titleB = b.manga.title.toLowerCase();
      return titleA.localeCompare(titleB);
    })
    .map(item => item.manga);

  const finalRecs = [...orderedSiblings, ...recommendations];

  return limit ? finalRecs.slice(0, limit) : finalRecs;
}

export async function deleteAuthorByName(authorName: string): Promise<void> {
  const q = query(collection(db, 'mangas'), where('author', '==', authorName));
  const querySnapshot = await getDocs(q);

  const updatePromises = querySnapshot.docs.map(docSnap => {
    return updateDoc(doc(db, 'mangas', docSnap.id), { author: '' });
  });

  await Promise.all(updatePromises);
}

export async function getAllAuthors(): Promise<string[]> {
  const q = query(collection(db, 'mangas'));
  const querySnapshot = await getDocs(q);

  const authors = new Set<string>();
  querySnapshot.forEach((doc) => {
    const data = doc.data();
    if (data && data.author && typeof data.author === 'string' && data.author.trim() !== '') {
      authors.add(data.author.trim());
    }
  });

  return Array.from(authors).sort();
}

export async function createFolderAndMove(folderName: string, selectedMangaIds: string[], parentFolderId?: string | null, section: 'flow' | 'patreon' | 'onlyfans' | 'grok' = 'flow'): Promise<Manga> {
  const now = Timestamp.now();
  const folderData: any = {
    title: folderName,
    author: 'Carpeta',
    description: '',
    status: 'Carpeta',
    categories: [],
    views: 0,
    rating: 0,
    created_at: now,
    updated_at: now,
    is_folder: true,
    section: section,
  };

  if (parentFolderId) {
    folderData.folder_id = parentFolderId;
  }

  const docRef = await addDoc(collection(db, 'mangas'), folderData);
  const folderId = docRef.id;

  if (selectedMangaIds.length > 0) {
    await moveToFolder(selectedMangaIds, folderId);
  }

  const nowISO = new Date().toISOString();
  const newFolder = {
    id: folderId,
    ...folderData,
    created_at: nowISO,
    updated_at: nowISO,
    chapters: [],
    categories: [],
  } as unknown as Manga;

  mangaCache.set(folderId, newFolder);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);

  return newFolder;
}

export async function moveToFolder(mangaIds: string[], folderId: string | null): Promise<void> {
  const now = Timestamp.now();
  const promises = mangaIds.map(async (mangaId) => {
    const docRef = doc(db, 'mangas', mangaId);
    await updateDoc(docRef, { folder_id: folderId, updated_at: now });

    const cached = mangaCache.get(mangaId);
    if (cached) {
      if (folderId) {
        cached.folder_id = folderId;
      } else {
        delete cached.folder_id;
      }
      cached.updated_at = now.toDate().toISOString();
      mangaCache.set(mangaId, cached);
      saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${mangaId}`, cached);
    }
  });

  await Promise.all(promises);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

export async function moveMangasToSection(mangaIds: string[], targetSection: 'flow' | 'patreon' | 'onlyfans' | 'grok'): Promise<void> {
  const now = Timestamp.now();
  const chunkedIds = [];
  for (let i = 0; i < mangaIds.length; i += 30) {
    chunkedIds.push(mangaIds.slice(i, i + 30));
  }

  const idsSet = new Set(mangaIds);

  for (const chunk of chunkedIds) {
    if (chunk.length === 0) continue;
    
    const batchOps = writeBatch(db);
    
    const q = query(collection(db, 'mangas'), where('__name__', 'in', chunk));
    const snapshot = await getDocs(q);

    snapshot.forEach(docSnap => {
      const data = docSnap.data();
      const folderId = data.folder_id;
      
      const shouldKeepFolderId = folderId && idsSet.has(folderId);

      const updateData: any = { section: targetSection, updated_at: now };
      if (!shouldKeepFolderId) {
        updateData.folder_id = deleteField();
      }

      batchOps.update(docSnap.ref, updateData);
      
      const cached = mangaCache.get(docSnap.id);
      if (cached) {
        cached.section = targetSection;
        if (!shouldKeepFolderId) {
          delete cached.folder_id;
        }
        cached.updated_at = now.toDate().toISOString();
        mangaCache.set(docSnap.id, cached);
        saveLocal(`${STORAGE_KEYS.MANGA_PREFIX}${docSnap.id}`, cached);
      }
    });

    await batchOps.commit();
  }
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

export async function mergeMangas(mangaIds: string[]): Promise<void> {
  if (mangaIds.length < 2) return;

  const mangasToMerge: Manga[] = [];
  for (const id of mangaIds) {
    const m = await getMangaById(id);
    if (m) mangasToMerge.push(m);
  }

  if (mangasToMerge.length < 2) return;

  const newTitle = mangasToMerge.map(m => m.title).join(' - ');
  const newSection = mangasToMerge[0].section || 'flow';
  const newFolderId = mangasToMerge[0].folder_id;

  const categoryIdsSet = new Set<string>();
  mangasToMerge.forEach(m => {
    m.categories?.forEach(cat => categoryIdsSet.add(cat.id));
  });

  const now = Timestamp.now();
  const newMangaData: any = {
    title: newTitle,
    author: mangasToMerge[0].author,
    description: mangasToMerge.map(m => m.description).filter(Boolean).join('\n\n'),
    status: 'En curso',
    categories: Array.from(categoryIdsSet),
    views: 0,
    rating: 0,
    created_at: now,
    updated_at: now,
    section: newSection,
    is_decensored: mangasToMerge.some(m => m.is_decensored),
    is_bn: mangasToMerge.some(m => m.is_bn),
    is_color: mangasToMerge.some(m => m.is_color),
  };

  if (mangasToMerge[0].thumbnail_url) newMangaData.thumbnail_url = mangasToMerge[0].thumbnail_url;
  if (mangasToMerge[0].cover_url) newMangaData.cover_url = mangasToMerge[0].cover_url;
  if (newFolderId) newMangaData.folder_id = newFolderId;

  const newMangaRef = await addDoc(collection(db, 'mangas'), newMangaData);
  const newMangaId = newMangaRef.id;

  let allPages: string[] = [];
  let allOriginalPages: string[] = [];
  let allPageFormats: string[] = [];

  mangasToMerge.forEach(m => {
    m.chapters?.forEach(ch => {
      if (ch.pages) allPages = allPages.concat(ch.pages);
      if (ch.original_pages) allOriginalPages = allOriginalPages.concat(ch.original_pages);
      if (ch.page_formats) allPageFormats = allPageFormats.concat(ch.page_formats);
    });
  });

  if (allPageFormats.length > 0 && allPageFormats.length !== allPages.length) {
    allPageFormats = allPages.map((_, i) => allPageFormats[i] || 'webp');
  }

  if (allPages.length > 0) {
    await createChapter({
      manga_id: newMangaId,
      number: 1,
      title: 'Capítulo 1',
      pages: allPages,
      page_formats: allPageFormats,
      original_pages: allOriginalPages
    });
  }

  for (const id of mangaIds) {
    await deleteManga(id);
  }

  removeLocal(STORAGE_KEYS.ALL_MANGAS);
}

export async function swapMangaPages(mangaAId: string, mangaBId: string, mangaA_newPages: string[], mangaB_newPages: string[]): Promise<void> {
  // We'll replace all existing chapters with a single chapter containing the new selected pages
  // For Manga A
  const chaptersQueryA = query(collection(db, 'chapters'), where('manga_id', '==', mangaAId));
  const chaptersSnapshotA = await getDocs(chaptersQueryA);
  for (const chapterDoc of chaptersSnapshotA.docs) {
    await deleteDoc(chapterDoc.ref);
  }
  
  if (mangaA_newPages.length > 0) {
    await createChapter({
      manga_id: mangaAId,
      number: 1,
      title: 'Capítulo 1',
      pages: mangaA_newPages
    });
  }

  // For Manga B
  const chaptersQueryB = query(collection(db, 'chapters'), where('manga_id', '==', mangaBId));
  const chaptersSnapshotB = await getDocs(chaptersQueryB);
  for (const chapterDoc of chaptersSnapshotB.docs) {
    await deleteDoc(chapterDoc.ref);
  }
  
  if (mangaB_newPages.length > 0) {
    await createChapter({
      manga_id: mangaBId,
      number: 1,
      title: 'Capítulo 1',
      pages: mangaB_newPages
    });
  }

  // Update timestamps and clear cache
  const now = Timestamp.now();
  
  const updateDataA: any = { updated_at: now };
  if (mangaA_newPages.length > 0) {
    updateDataA.cover_url = mangaA_newPages[0];
    updateDataA.thumbnail_url = mangaA_newPages[0];
  } else {
    updateDataA.cover_url = deleteField();
    updateDataA.thumbnail_url = deleteField();
  }

  const updateDataB: any = { updated_at: now };
  if (mangaB_newPages.length > 0) {
    updateDataB.cover_url = mangaB_newPages[0];
    updateDataB.thumbnail_url = mangaB_newPages[0];
  } else {
    updateDataB.cover_url = deleteField();
    updateDataB.thumbnail_url = deleteField();
  }

  await updateDoc(doc(db, 'mangas', mangaAId), updateDataA);
  await updateDoc(doc(db, 'mangas', mangaBId), updateDataB);

  removeLocal(`${STORAGE_KEYS.MANGA_PREFIX}${mangaAId}`);
  removeLocal(`${STORAGE_KEYS.MANGA_PREFIX}${mangaBId}`);
  removeLocal(STORAGE_KEYS.ALL_MANGAS);
  mangaCache.delete(mangaAId);
  mangaCache.delete(mangaBId);
}
