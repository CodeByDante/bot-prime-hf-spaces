import { initializeApp } from 'firebase/app';
import {
  getFirestore,
  collection,
  addDoc,
  updateDoc,
  deleteDoc,
  doc,
  onSnapshot,
  query,
  orderBy,
  serverTimestamp
} from 'firebase/firestore';
import { DataItem } from '../types';

// Configuration for project code-by-dante
const firebaseConfig = {
  apiKey: "AIzaSyBv55pNiZ_3zXkulC_qWzzbzuenql570gM",
  authDomain: "code-by-dante.firebaseapp.com",
  projectId: "code-by-dante",
  storageBucket: "code-by-dante.firebasestorage.app",
  messagingSenderId: "752222250917",
  appId: "1:752222250917:web:6f7eb8b4abba2efc2daa4c"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);

/**
 * Helper function to remove fields with 'undefined' values from an object.
 * Firestore throws an error if a field is set to undefined.
 */
const cleanData = (data: any) => {
  const cleaned: any = {};
  Object.keys(data).forEach(key => {
    if (data[key] !== undefined) {
      cleaned[key] = data[key];
    }
  });
  return cleaned;
};

export const subscribeToItems = (callback: (items: DataItem[]) => void) => {
  let foldersData: DataItem[] = [];
  let voicesData: DataItem[] = [];

  const updateAll = () => {
    const combinedMap = new Map<string, DataItem>();
    foldersData.forEach(item => combinedMap.set(item.id, item));
    voicesData.forEach(item => combinedMap.set(item.id, item));
    callback(Array.from(combinedMap.values()));
  };

  // Subscribe to folders in code-by-dante
  const unsubFolders = onSnapshot(collection(db, 'folders'), (snapshot) => {
    foldersData = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        title: data.name || data.title || 'Carpeta',
        summary: 'Carpeta',
        content: '',
        isFolder: true,
        parentId: data.parentId || null,
        tags: [],
        categories: [],
        createdAt: data.createdAt?.toMillis ? data.createdAt.toMillis() : Date.now(),
      } as DataItem;
    });
    updateAll();
  }, (err) => console.error("Error reading folders:", err));

  // Subscribe to voices in code-by-dante
  const unsubVoices = onSnapshot(collection(db, 'voices'), (snapshot) => {
    voicesData = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        title: data.title || 'Voz',
        summary: '',
        content: '',
        visitUrl: data.url || data.visitUrl || '',
        downloadUrl: data.downloadUrl || '',
        isFolder: false,
        parentId: data.folderId || data.parentId || null,
        tags: data.tags || [],
        categories: data.categories || [],
        linkGroups: data.linkGroups || [],
        createdAt: data.createdAt?.toMillis ? data.createdAt.toMillis() : Date.now(),
      } as DataItem;
    });
    updateAll();
  }, (err) => console.error("Error reading voices:", err));

  return () => {
    unsubFolders();
    unsubVoices();
  };
};

const getColName = (item?: Partial<DataItem>) => item?.isFolder ? 'folders' : 'voices';

export const addItem = async (item: Omit<DataItem, 'id' | 'createdAt'>): Promise<string> => {
  try {
    const itemToSave = cleanData(item);
    const targetCol = getColName(item);
    const docRef = await addDoc(collection(db, targetCol), {
      ...itemToSave,
      createdAt: serverTimestamp()
    });
    return docRef.id;
  } catch (e) {
    console.error("Error adding document: ", e);
    throw e;
  }
};

export const updateItem = async (id: string, item: Partial<DataItem>) => {
  try {
    const targetCol = getColName(item);
    const docRef = doc(db, targetCol, id);
    const { id: _, createdAt: __, ...updateData } = item;
    const sanitizedUpdateData = cleanData(updateData);
    await updateDoc(docRef, {
      ...sanitizedUpdateData,
      updatedAt: serverTimestamp()
    });
  } catch (e) {
    console.error("Error updating document: ", e);
    throw e;
  }
};

// Soft delete (moves item to trash bin)
export const deleteItem = async (id: string, isFolder?: boolean) => {
  try {
    const targetCol = isFolder ? 'folders' : 'voices';
    const docRef = doc(db, targetCol, id);
    await updateDoc(docRef, {
      isDeleted: true,
      deletedAt: Date.now()
    });
  } catch (e) {
    console.error("Error soft deleting document: ", e);
    throw e;
  }
};

// Restore item from trash bin
export const restoreItem = async (id: string, isFolder?: boolean) => {
  try {
    const targetCol = isFolder ? 'folders' : 'voices';
    const docRef = doc(db, targetCol, id);
    await updateDoc(docRef, {
      isDeleted: false,
      deletedAt: null
    });
  } catch (e) {
    console.error("Error restoring document: ", e);
    throw e;
  }
};

// Permanently delete item
export const permanentlyDeleteItem = async (id: string, isFolder?: boolean) => {
  try {
    const targetCol = isFolder ? 'folders' : 'voices';
    await deleteDoc(doc(db, targetCol, id));
  } catch (e) {
    console.error("Error permanently deleting document: ", e);
    throw e;
  }
};

// Restore multiple items
export const restoreAllItems = async (items: {id: string, isFolder: boolean}[]) => {
  try {
    await Promise.all(items.map(item => restoreItem(item.id, item.isFolder)));
  } catch (e) {
    console.error("Error restoring all items: ", e);
    throw e;
  }
};



// Permanently empty trash bin
export const emptyTrash = async (ids: string[]) => {
  try {
    await Promise.all(ids.map(id => permanentlyDeleteItem(id)));
  } catch (e) {
    console.error("Error emptying trash: ", e);
    throw e;
  }
};