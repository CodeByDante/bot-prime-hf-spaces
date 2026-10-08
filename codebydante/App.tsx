import React, { useState, useEffect, useMemo } from 'react';
import { DataItem, ViewState } from './types';
import { Card } from './components/Card';
import { DataForm } from './components/DataForm';
import { DetailView } from './components/DetailView';
import { Button } from './components/Button';
import { Plus, Search, Layers, Loader2, WifiOff, Settings, Code, Type, Clock, Calendar, Shuffle, ChevronsLeft, ChevronLeft, ChevronRight, ChevronsRight, Check, Trash, MapPin, Copy, Pin } from 'lucide-react';
import { subscribeToItems, addItem, updateItem, deleteItem } from './services/firebase';
import { subscribeToStyleConfig } from './services/codeStyleService';
import { BulkCategoryModal } from './components/BulkCategoryModal';
import { ConfirmModal } from './components/ConfirmModal';
import { MoveToFolderModal } from './components/MoveToFolderModal';
import { TrashModal } from './components/TrashModal';
import { Folder, Trash2, RotateCcw } from 'lucide-react';

const App: React.FC = () => {
  const [items, setItems] = useState<DataItem[]>([]);
  const [view, setView] = useState<ViewState>('LIST');
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [showBulkCategoryModal, setShowBulkCategoryModal] = useState(false);
  const [isApplyingCategories, setIsApplyingCategories] = useState(false);
  const [viewMode, setViewMode] = useState<'normal' | 'admin'>(() => {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      if (params.get('admin') === 'true') {
        localStorage.setItem('viewMode', 'admin');
        return 'admin';
      }
      return (localStorage.getItem('viewMode') as 'normal' | 'admin') || 'normal';
    }
    return 'normal';
  });
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isFolderMenuOpen, setIsFolderMenuOpen] = useState(false);
  const [folderSearchQuery, setFolderSearchQuery] = useState('');
  const [isCategoriesPlusEnabled, setIsCategoriesPlusEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('categoriesPlusEnabled') === 'true';
    }
    return false;
  });
  const [isDeletePlusEnabled, setIsDeletePlusEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('deletePlusEnabled') === 'true';
    }
    return false;
  });
  const [isDuplicatePlusEnabled, setIsDuplicatePlusEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('duplicatePlusEnabled') === 'true';
    }
    return false;
  });
  const [isFoldersPlusEnabled, setIsFoldersPlusEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('foldersPlusEnabled') === 'true';
    }
    return false;
  });
  const [isPinPlusEnabled, setIsPinPlusEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('pinPlusEnabled') === 'true';
    }
    return false;
  });
  const [isShowBreadcrumbsEnabled, setIsShowBreadcrumbsEnabled] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('showBreadcrumbsEnabled') !== 'false';
    }
    return true;
  });
  const [isDragging, setIsDragging] = useState(false);
  const [dragMode, setDragMode] = useState<'select' | 'deselect'>('select');
  const [currentPage, setCurrentPage] = useState(() => {
    if (typeof window !== 'undefined') {
      const p = new URLSearchParams(window.location.search).get('page');
      if (p && !isNaN(Number(p))) return Math.max(1, parseInt(p, 10));
    }
    return 1;
  });
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  
  const [showConfirmDelete, setShowConfirmDelete] = useState(false);
  const [showMoveToFolder, setShowMoveToFolder] = useState(false);
  const [isTrashOpen, setIsTrashOpen] = useState(false);

  const ITEMS_PER_PAGE = 20;

  useEffect(() => {
    const handleMouseUp = () => setIsDragging(false);
    window.addEventListener('mouseup', handleMouseUp);
    return () => window.removeEventListener('mouseup', handleMouseUp);
  }, []);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      url.search = '';
      console.log('%c--- ENLACES DE ACCESO ---', 'color: #00ff00; font-weight: bold; font-size: 14px;');
      console.log(`%cAcceso Normal: %c${url.toString()}`, 'color: white;', 'color: #4da6ff; text-decoration: underline;');
      console.log(`%cAcceso Administrador: %c${url.toString()}?admin=true`, 'color: white;', 'color: #ff4d4d; text-decoration: underline;');
    }
  }, []);
  const [selectedItem, setSelectedItem] = useState<DataItem | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [sortOrder, setSortOrder] = useState<'updated' | 'created' | 'name' | 'random'>(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('sortOrder');
      if (saved && ['updated', 'created', 'name', 'random'].includes(saved)) {
        return saved as 'updated' | 'created' | 'name' | 'random';
      }
    }
    return 'random';
  });

  useEffect(() => {
    localStorage.setItem('sortOrder', sortOrder);
  }, [sortOrder]);

  useEffect(() => {
    localStorage.setItem('categoriesPlusEnabled', isCategoriesPlusEnabled.toString());
    localStorage.setItem('deletePlusEnabled', isDeletePlusEnabled.toString());
    localStorage.setItem('foldersPlusEnabled', isFoldersPlusEnabled.toString());
    localStorage.setItem('duplicatePlusEnabled', isDuplicatePlusEnabled.toString());
    localStorage.setItem('pinPlusEnabled', isPinPlusEnabled.toString());
  }, [isCategoriesPlusEnabled, isDeletePlusEnabled, isFoldersPlusEnabled, isDuplicatePlusEnabled, isPinPlusEnabled]);

  useEffect(() => {
    localStorage.setItem('showBreadcrumbsEnabled', isShowBreadcrumbsEnabled.toString());
  }, [isShowBreadcrumbsEnabled]);

  useEffect(() => {
    if (!isCategoriesPlusEnabled && !isDeletePlusEnabled && !isFoldersPlusEnabled && !isDuplicatePlusEnabled && !isPinPlusEnabled) {
      setSelectedItemIds(new Set());
    }
  }, [isCategoriesPlusEnabled, isDeletePlusEnabled, isFoldersPlusEnabled, isDuplicatePlusEnabled, isPinPlusEnabled]);

  // Handle URL Sync
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const url = new URL(window.location.href);
      const params = url.searchParams;
      let modified = false;

      if (selectedItem) {
        if (params.get('item') !== selectedItem.id) {
          params.set('item', selectedItem.id);
          modified = true;
        }
      } else {
        if (params.has('item')) {
          params.delete('item');
          modified = true;
        }
      }

      if (currentPage > 1) {
        if (params.get('page') !== currentPage.toString()) {
          params.set('page', currentPage.toString());
          modified = true;
        }
      } else {
        if (params.has('page')) {
          params.delete('page');
          modified = true;
        }
      }

      if (currentFolderId) {
        if (params.get('folder') !== currentFolderId) {
          params.set('folder', currentFolderId);
          modified = true;
        }
      } else {
        if (params.has('folder')) {
          params.delete('folder');
          modified = true;
        }
      }

      if (modified) {
        const newSearch = params.toString() ? `?${params.toString()}` : '';
        window.history.replaceState({}, '', url.pathname + newSearch);
      }
    }
  }, [currentPage, selectedItem]);

  // Load deep linked item and folder
  useEffect(() => {
    if (!loading && items.length > 0 && typeof window !== 'undefined' && view === 'LIST' && !selectedItem) {
      const params = new URLSearchParams(window.location.search);
      const itemId = params.get('item');
      let urlModified = false;
      
      if (itemId) {
        const found = items.find((i) => i.id === itemId);
        if (found) {
          setSelectedItem(found);
          setView('DETAIL');
        } else {
          params.delete('item');
          urlModified = true;
        }
      }

      if (!itemId && view === 'LIST' && currentFolderId === null) {
         const folderId = params.get('folder');
         if (folderId) {
           const foundFolder = items.find(i => i.id === folderId && i.isFolder);
           if (foundFolder) {
              setCurrentFolderId(folderId);
           } else {
              params.delete('folder');
              urlModified = true;
           }
         }
      }

      if (urlModified) {
        const newSearch = params.toString() ? `?${params.toString()}` : '';
        window.history.replaceState({}, '', window.location.pathname + newSearch);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, items]);

  // Helper function to apply code style dynamically to DOM
  const applyCodeStyleToDOM = (config: any) => {
    const rgbaMatch = config.bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
    let bgColorWithOpacity = config.bgColor;

    if (rgbaMatch) {
      const [_, r, g, b] = rgbaMatch;
      bgColorWithOpacity = `rgba(${r}, ${g}, ${b}, ${config.opacity / 100})`;
    }

    const widthValue = config.width === 'auto' ? 0 : parseFloat(config.width) || 0;
    const heightValue = config.height === 'auto' ? 0 : parseFloat(config.height) || 0;

    const existingStyle = document.getElementById('dynamic-code-style');
    if (existingStyle) {
      existingStyle.remove();
    }

    const style = document.createElement('style');
    style.id = 'dynamic-code-style';
    style.innerHTML = `
      :not(pre) > code {
        background-color: ${bgColorWithOpacity} !important;
        color: ${config.textColor} !important;
        font-size: ${config.fontSize} !important;
        border-radius: ${config.borderRadius} !important;
        padding: 0px 2px !important;
        ${config.width !== 'auto' && widthValue > 0 ? `min-width: ${config.width} !important;` : ''}
        ${config.height !== 'auto' && heightValue > 0 ? `min-height: ${config.height} !important;` : ''}

        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;

        vertical-align: middle !important;
        border: none !important;
        font-family: 'Consolas', monospace !important;
        line-height: 1 !important;
        margin: 0 1px !important;
      }

      button code, a code, .btn code {
        background: transparent !important;
        padding: 0 !important;
        color: inherit !important;
        border: none !important;
      }

      code::before, code::after {
        content: "" !important;
        display: none !important;
      }
    `;

    document.head.appendChild(style);
  };

  // Subscribe to style config changes from cloud
  useEffect(() => {
    const unsubscribe = subscribeToStyleConfig((config) => {
      applyCodeStyleToDOM(config.code);
    });
    return () => unsubscribe();
  }, [applyCodeStyleToDOM]);

  // Persist viewMode to localStorage
  useEffect(() => {
    localStorage.setItem('viewMode', viewMode);
  }, [viewMode]);

  // Subscribe to Firestore updates
  useEffect(() => {
    const unsubscribe = subscribeToItems((newItems) => {
      setItems(newItems);
      setLoading(false);
      setError(null);
    });

    // Cleanup subscription on unmount
    return () => unsubscribe();
  }, []);

  const activeItems = useMemo(() => items.filter(i => !i.isDeleted), [items]);
  const deletedItems = useMemo(() => items.filter(i => i.isDeleted === true), [items]);

  const filteredItems = useMemo(() => {
    const inFolder = activeItems.filter(i => (i.parentId || null) === currentFolderId);

    if (!searchQuery.trim()) {
      const sorted = [...inFolder];
      if (sortOrder === 'random') return sorted.sort(() => Math.random() - 0.5);
      return sorted.sort((a, b) => {
        // Pinned status always takes first priority
        if (!!a.isPinned !== !!b.isPinned) return a.isPinned ? -1 : 1;

        if (sortOrder === 'name') {
          if (a.isFolder === b.isFolder) return (a.title || '').localeCompare(b.title || '');
          return a.isFolder ? -1 : 1;
        }
        if (sortOrder === 'updated') {
          if (a.isFolder === b.isFolder) return (b.updatedAt || b.createdAt) - (a.updatedAt || a.createdAt);
          return a.isFolder ? -1 : 1;
        }
        // Default sort (created)
        if (a.isFolder === b.isFolder) return b.createdAt - a.createdAt;
        return a.isFolder ? -1 : 1;
      });
    }

    const lowerQ = searchQuery.toLowerCase();

    // SMART SEARCH LOGIC
    const stopWords = new Set([
      'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero', 'si', 'no',
      'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'entre',
      'mi', 'tu', 'su', 'nuestro', 'vuestro', 'sus', 'mis', 'tus',
      'que', 'cual', 'quien', 'donde', 'cuando', 'como', 'porque',
      'es', 'son', 'fue', 'fueron', 'era', 'eran', 'está', 'están',
      'este', 'esta', 'ese', 'esa', 'aquel', 'aquella', 'esto', 'eso', 'aquello',
      'hizo', 'hacer', 'todo', 'toda', 'todos', 'todas', 'muy', 'más', 'tan',
      'ya', 'hoy', 'ayer', 'ahora', 'después', 'antes', 'mira', 'voy'
    ]);

    // Tokenize and clean query
    const tokens = lowerQ.replace(/[^\w\sáéíóúñü]/g, '').split(/\s+/).filter(t => t.length > 0);
    const keywords = tokens.filter(t => !stopWords.has(t));

    // Fallback: If all words were stop words (e.g. "el la"), search normally with full query
    const validKeywords = keywords.length > 0 ? keywords : tokens;

    // Scoring function
    const getScore = (item: DataItem) => {
      let score = 0;
      const title = String(item.title || '').toLowerCase();
      const summary = String(item.summary || '').toLowerCase();
      const tags = Array.isArray(item.tags) ? item.tags.map(t => String(t || '').toLowerCase()) : [];
      const content = String(item.content || '').toLowerCase();

      validKeywords.forEach(keyword => {
        if (title.includes(keyword)) score += 10;
        else if (tags.some(t => t.includes(keyword))) score += 5;
        else if (summary.includes(keyword)) score += 2;
        else if (content.includes(keyword)) score += 1;
      });

      return score;
    };

    // 1. Score ALL active items in the database regardless of folder
    const allScored = activeItems
      .map(item => ({ item, score: getScore(item) }))
      .filter(entry => entry.score > 0);

    // 2. Map matches to the current folder context
    const visibleResultsMap = new Map<string, { item: DataItem, score: number }>();

    allScored.forEach(entry => {
      let currentItem = entry.item;
      let valid = true;
      const seenIds = new Set<string>();

      // Trace up to find the ancestor that lives in currentFolderId
      while (currentItem && (currentItem.parentId || null) !== currentFolderId) {
        if (seenIds.has(currentItem.id)) {
          valid = false; // Circular reference detected
          break;
        }
        seenIds.add(currentItem.id);
        const parent = activeItems.find(i => i.id === currentItem.parentId);
        if (!parent) {
          valid = false; // Broken link or orphaned item, ignore
          break;
        }
        currentItem = parent;
      }

      if (valid && currentItem) {
        // currentItem now lives in currentFolderId!
        // We accumulate the MAX score so that folders bubble up with the highest relevance of their contents.
        if (!visibleResultsMap.has(currentItem.id)) {
          visibleResultsMap.set(currentItem.id, { item: currentItem, score: entry.score });
        } else {
          const existing = visibleResultsMap.get(currentItem.id)!;
          if (entry.score > existing.score) {
            existing.score = entry.score;
          }
        }
      }
    });

    const scoredItems = Array.from(visibleResultsMap.values());

    // Boost folders so they appear first in the results
    scoredItems.forEach(entry => {
      if (entry.item.isFolder) entry.score += 50;
    });

    // Sort by Score DESC, then by sortOrder
    scoredItems.sort((a, b) => {
      if (a.score !== b.score) return b.score - a.score; // Higher score first

      // Secondary sort based on user preference
      if (sortOrder === 'name') return (a.item.title || '').localeCompare(b.item.title || '');
      if (sortOrder === 'updated') return (b.item.updatedAt || b.item.createdAt) - (a.item.updatedAt || a.item.createdAt);
      if (sortOrder === 'created') return b.item.createdAt - a.item.createdAt;
      return 0;
    });

    return scoredItems.map(entry => entry.item);

  }, [activeItems, searchQuery, sortOrder, currentFolderId]);

  // Reset to first page when search or sort changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery, sortOrder]);

  const paginatedItems = useMemo(() => {
    const startIndex = (currentPage - 1) * ITEMS_PER_PAGE;
    return filteredItems.slice(startIndex, startIndex + ITEMS_PER_PAGE);
  }, [filteredItems, currentPage]);

  const breadcrumbs = useMemo(() => {
    const crumbs = [];
    let current = currentFolderId;
    while (current) {
      const folder = items.find(i => i.id === current);
      if (folder) {
        crumbs.unshift(folder);
        current = folder.parentId || null;
      } else {
        break;
      }
    }
    return crumbs;
  }, [currentFolderId, items]);

  const totalPages = Math.ceil(filteredItems.length / ITEMS_PER_PAGE);

  const renderPagination = () => {
    if (totalPages <= 1) return null;

    const pages = [];
    const maxVisiblePages = 5;
    
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);

    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <button
          key={i}
          onClick={() => { setCurrentPage(i); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
          className={`w-10 h-10 flex items-center justify-center rounded-xl font-medium transition-colors ${
            currentPage === i 
              ? 'bg-primary text-background' 
              : 'bg-surface hover:bg-white/10 text-gray-400 hover:text-white'
          }`}
        >
          {i}
        </button>
      );
    }

    return (
      <div className="flex items-center justify-center gap-2 mt-12 mb-8 animate-fade-in">
        <button
          onClick={() => { setCurrentPage(1); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
          disabled={currentPage === 1}
          className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-white/10 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronsLeft size={18} />
        </button>
        <button
          onClick={() => { setCurrentPage(prev => Math.max(1, prev - 1)); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
          disabled={currentPage === 1}
          className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-white/10 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronLeft size={18} />
        </button>
        
        {pages}

        {endPage < totalPages && (
          <span className="text-gray-500 px-1">...</span>
        )}

        <button
          onClick={() => { setCurrentPage(prev => Math.min(totalPages, prev + 1)); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
          disabled={currentPage === totalPages}
          className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-white/10 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronRight size={18} />
        </button>
        <button
          onClick={() => { setCurrentPage(totalPages); window.scrollTo({ top: 0, behavior: 'smooth' }); }}
          disabled={currentPage === totalPages}
          className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface hover:bg-white/10 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          <ChevronsRight size={18} />
        </button>
      </div>
    );
  };

  const handleCreate = async (data: Omit<DataItem, 'id' | 'createdAt'>) => {
    try {
      await addItem(data);
      setView('LIST');
    } catch (e) {
      alert("Error al guardar en la nube.");
    }
  };

  const handleUpdate = async (data: Omit<DataItem, 'id' | 'createdAt'>) => {
    if (!selectedItem) return;
    try {
      await updateItem(selectedItem.id, data);

      // Update local selected item to reflect changes immediately in UI if still in Detail view
      setSelectedItem(prev => prev ? { ...prev, ...data } : null);
      // We do NOT switch view here automatically to allow inline edits in DetailView
    } catch (e) {
      alert("Error al actualizar.");
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteItem(id);
      setView('LIST');
      setSelectedItem(null);
    } catch (e) {
      alert("Error al eliminar.");
    }
  };

  if (error) {
    return (
      <div className="min-h-screen bg-background flex flex-col items-center justify-center text-white p-4 text-center">
        <WifiOff size={48} className="text-red-500 mb-4" />
        <h2 className="text-xl font-bold mb-2">Error de Conexión</h2>
        <p className="text-gray-400 max-w-md">{error}</p>
        <p className="text-sm text-gray-500 mt-4">Por favor verifica tu conexión a internet o la configuración de Firebase.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background font-sans text-gray-200 selection:bg-primary selection:text-background pb-20">

      {/* Sliding Drawer Sidebar */}
      {isFolderMenuOpen && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm animate-in fade-in duration-300"
            onClick={() => setIsFolderMenuOpen(false)}
          />
          
          {/* Sliding Drawer */}
          <div className="fixed top-0 left-0 h-full w-72 bg-[#121212] border-r border-white/10 shadow-2xl z-[70] flex flex-col animate-in slide-in-from-left duration-300">
            <div className="h-20 px-6 border-b border-white/10 flex items-center justify-between shrink-0">
              <span className="font-bold text-lg text-white flex items-center gap-2">
                <Folder size={20} className="text-primary" /> Carpetas
              </span>
              <button onClick={() => setIsFolderMenuOpen(false)} className="text-gray-400 hover:text-white p-2 rounded-lg hover:bg-white/10 transition-colors">
                <ChevronLeft size={20} />
              </button>
            </div>
            
            <div className="p-4 border-b border-white/5">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                <input
                  type="text"
                  placeholder="Buscar carpeta..."
                  className="w-full bg-surface/80 border border-white/5 focus:border-primary/50 rounded-lg py-2 pl-9 pr-3 outline-none text-sm transition-all shadow-inner placeholder:text-gray-600"
                  value={folderSearchQuery}
                  onChange={(e) => setFolderSearchQuery(e.target.value)}
                />
              </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
              <div className="flex flex-col gap-1">
                <button
                  onClick={() => {
                    setCurrentFolderId(null);
                    setCurrentPage(1);
                    setView('LIST');
                    setIsFolderMenuOpen(false);
                  }}
                  className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm transition-all ${currentFolderId === null ? 'bg-primary/20 text-primary font-medium' : 'text-gray-400 hover:bg-white/5 hover:text-white'}`}
                >
                  <Layers size={18} />
                  Raíz
                </button>
                
                <div className="my-2 border-t border-white/5"></div>
                
                {items.filter(i => i.isFolder && (!folderSearchQuery || (i.title && i.title.toLowerCase().includes(folderSearchQuery.toLowerCase())))).length === 0 && folderSearchQuery && (
                  <div className="text-center py-4 text-xs text-gray-500">
                    No se encontraron carpetas
                  </div>
                )}
                
                {items.filter(i => i.isFolder && (!folderSearchQuery || (i.title && i.title.toLowerCase().includes(folderSearchQuery.toLowerCase())))).map(folder => (
                  <button
                    key={folder.id}
                    onClick={() => {
                      setCurrentFolderId(folder.id);
                      setCurrentPage(1);
                      setView('LIST');
                      setIsFolderMenuOpen(false);
                    }}
                    className={`w-full flex items-center gap-3 px-3 py-3 rounded-xl text-sm transition-all text-left truncate ${currentFolderId === folder.id ? 'bg-primary/20 text-primary font-medium' : 'text-gray-400 hover:bg-white/5 hover:text-white'}`}
                  >
                    <Folder size={18} className="shrink-0" />
                    <span className="truncate">{folder.title}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {/* Navbar */}
      <nav className="sticky top-0 z-50 bg-background/80 backdrop-blur-md border-b border-white/5">
        <div className="w-full max-w-[95%] 2xl:max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-20">
            <div className="flex items-center gap-4">
              <div className="relative">
                <Button
                  variant="secondary"
                  onClick={() => setIsFolderMenuOpen(!isFolderMenuOpen)}
                  className="bg-surface border border-white/5 hover:bg-surfaceHover !px-3 justify-center flex items-center gap-2"
                  title="Carpetas"
                >
                  <Folder size={20} className={isFolderMenuOpen ? "text-primary" : ""} />
                </Button>
              </div>

              <div
                className="flex items-center gap-2 cursor-pointer group"
                onClick={() => { 
                  setView('LIST'); 
                  setSearchQuery(''); 
                  setCurrentFolderId(null);
                  setCurrentPage(1);
                }}
              >
                <div className="p-2 bg-surface rounded-lg group-hover:bg-primary/20 transition-colors">
                  <Layers className="text-primary" size={24} />
                </div>
                <span className="text-lg sm:text-xl font-bold tracking-tight text-white">
                  CodeBy<span className="text-primary">Dante</span>
                </span>
              </div>
            </div>

            {view === 'LIST' && (
              <div className="hidden md:flex flex-1 max-w-2xl mx-8 relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
                <input
                  type="text"
                  placeholder="Buscar en CodeByDante..."
                  className="w-full bg-surface border border-white/5 focus:border-primary rounded-full py-2.5 pl-10 pr-4 outline-none text-sm transition-all shadow-inner bg-opacity-50"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            )}

            <div className="flex items-center gap-1 sm:gap-3">
              <Button
                variant="secondary"
                onClick={() => {
                  const orders: ('updated' | 'created' | 'name' | 'random')[] = ['updated', 'created', 'name', 'random'];
                  const currentIndex = orders.indexOf(sortOrder);
                  const nextOrder = orders[(currentIndex + 1) % orders.length];
                  setSortOrder(nextOrder);
                }}
                className="bg-surface border border-white/5 hover:bg-surfaceHover transition-all hover:scale-105 active:scale-95 flex items-center gap-2 !px-2 sm:!px-4 min-w-[36px] sm:min-w-[140px] justify-center"
                title={`Ordenar por: ${sortOrder === 'updated' ? 'Modificación' : sortOrder === 'created' ? 'Fecha' : sortOrder === 'name' ? 'Nombre' : 'Aleatorio'}`}
              >
                {sortOrder === 'updated' && (
                  <>
                    <Clock size={16} className="text-primary" />
                    <span className="text-sm font-medium hidden sm:inline">Recientes</span>
                  </>
                )}
                {sortOrder === 'created' && (
                  <>
                    <Calendar size={16} className="text-primary" />
                    <span className="text-sm font-medium hidden sm:inline">Fecha</span>
                  </>
                )}
                {sortOrder === 'name' && (
                  <>
                    <Type size={16} className="text-primary" />
                    <span className="text-sm font-medium hidden sm:inline">Nombre</span>
                  </>
                )}
                {sortOrder === 'random' && (
                  <>
                    <Shuffle size={16} className="text-primary" />
                    <span className="text-sm font-medium hidden sm:inline">Aleatorio</span>
                  </>
                )}
              </Button>

              <Button
                variant="secondary"
                onClick={() => setIsTrashOpen(true)}
                className="bg-surface border border-white/5 hover:bg-surfaceHover !px-3 sm:!px-4 justify-center flex items-center gap-2 relative transition-all hover:scale-105 active:scale-95"
                title="Papelera de Reciclaje"
              >
                <Trash2 size={18} className={deletedItems.length > 0 ? "text-red-400" : "text-gray-400"} />
                <span className="hidden sm:inline font-medium">Papelera</span>
                {deletedItems.length > 0 && (
                  <span className="ml-1 text-xs px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-300 font-bold border border-red-500/30">
                    {deletedItems.length}
                  </span>
                )}
              </Button>

              <div className="relative">
                <Button
                  variant="secondary"
                  onClick={() => setIsSettingsOpen(!isSettingsOpen)}
                  className="bg-surface border border-white/5 hover:bg-surfaceHover !px-3 sm:!px-4 justify-center flex items-center gap-2"
                >
                  <Settings size={20} />
                  <span className="hidden sm:inline font-medium">Ajustes</span>
                </Button>

                {isSettingsOpen && (
                  <>
                    <div
                      className="fixed inset-0 z-10"
                      onClick={() => setIsSettingsOpen(false)}
                    />
                    <div className={`absolute right-0 mt-2 ${viewMode === 'admin' ? 'w-[320px]' : 'w-48'} bg-surface border border-white/10 rounded-xl shadow-xl z-20 overflow-hidden animate-in fade-in zoom-in-95 duration-200`}>
                      <div className="p-1">

                        <button
                          onClick={() => {
                            if (viewMode === 'admin') {
                              setViewMode('normal');
                            } else {
                              setViewMode('admin');
                            }
                            // setIsSettingsOpen(false); // remove auto close for admin view to show/hide extra settings smoothly
                          }}
                          className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors ${viewMode === 'admin'
                            ? 'bg-primary/10 text-primary'
                            : 'text-gray-400 hover:bg-white/5 hover:text-white'
                            }`}
                        >
                          <Settings size={16} />
                          {viewMode === 'admin' ? 'Desactivar Admin' : 'Modo Admin'}
                        </button>
                        
                        {viewMode === 'admin' && (
                          <div className="animate-in fade-in slide-in-from-top-2 duration-200">
                            <div className="my-1 border-t border-white/5"></div>
                            <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
                              Ajustes de Administrador
                            </div>
                            
                            <div className="mt-1">
                              <div 
                                className="flex items-center justify-between px-3 py-3 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsShowBreadcrumbsEnabled(!isShowBreadcrumbsEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <MapPin size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Mostrar Ubicación</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Mostrar barra de navegación de carpetas (Migajas de pan)</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isShowBreadcrumbsEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Mostrar Ubicación</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isShowBreadcrumbsEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>

                              <div 
                                className="flex items-center justify-between px-3 py-3 mt-1 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsCategoriesPlusEnabled(!isCategoriesPlusEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <Layers size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Categorías Plus</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Habilitar selección múltiple y edición masiva</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isCategoriesPlusEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Habilitar Categorías Plus</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isCategoriesPlusEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>

                              <div 
                                className="flex items-center justify-between px-3 py-3 mt-1 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsDeletePlusEnabled(!isDeletePlusEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <Trash size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Eliminar Plus</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Habilitar selección masiva para eliminar mangas</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isDeletePlusEnabled ? 'bg-red-500' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Habilitar Eliminar Plus</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isDeletePlusEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>

                              <div 
                                className="flex items-center justify-between px-3 py-3 mt-1 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsFoldersPlusEnabled(!isFoldersPlusEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <Folder size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Carpetas Plus</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Habilitar selección para crear carpetas y agrupar mangas</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isFoldersPlusEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Habilitar Carpetas Plus</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isFoldersPlusEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>

                              <div 
                                className="flex items-center justify-between px-3 py-3 mt-1 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsDuplicatePlusEnabled(!isDuplicatePlusEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <Copy size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Duplicar Plus</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Habilitar selección masiva para duplicar entradas</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isDuplicatePlusEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Habilitar Duplicar Plus</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isDuplicatePlusEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>

                              <div 
                                className="flex items-center justify-between px-3 py-3 mt-1 rounded-lg hover:bg-white/5 group border border-transparent hover:border-white/5 transition-all cursor-pointer"
                                onClick={() => setIsPinPlusEnabled(!isPinPlusEnabled)}
                              >
                                <div className="flex items-start gap-3">
                                  <div className="p-2 bg-[#1a1f2e] group-hover:bg-[#22283a] border border-white/5 rounded-xl transition-colors">
                                    <Pin size={18} className="text-gray-300 group-hover:text-white transition-colors" />
                                  </div>
                                  <div className="flex flex-col text-left justify-center">
                                    <span className="text-sm font-medium text-white mb-0.5">Anclar Plus</span>
                                    <span className="text-[11px] text-gray-400 leading-tight">Habilitar selección para anclar tarjetas</span>
                                  </div>
                                </div>
                                <button 
                                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${isPinPlusEnabled ? 'bg-primary' : 'bg-gray-600'}`}
                                >
                                  <span className="sr-only">Habilitar Anclar Plus</span>
                                  <span className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${isPinPlusEnabled ? 'translate-x-5' : 'translate-x-0'}`} />
                                </button>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </>
                )}
              </div>

              {viewMode === 'admin' && (
                <Button onClick={() => { setSelectedItem(null); setView('CREATE'); }} className="!px-2 sm:!px-4 justify-center">
                  <Plus size={20} /> <span className="hidden sm:inline">Nueva Entrada</span>
                </Button>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile Search Bar */}
      {view === 'LIST' && (
        <div className="md:hidden px-4 py-4 bg-background border-b border-white/5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={18} />
            <input
              type="text"
              placeholder="Buscar..."
              className="w-full bg-surface border border-white/5 focus:border-primary rounded-lg py-3 pl-10 pr-4 outline-none text-sm"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="w-full max-w-[95%] 2xl:max-w-[1800px] mx-auto px-4 sm:px-6 lg:px-8 py-8">
{loading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="animate-spin text-primary mb-4" size={40} />
            <p className="text-gray-500">Sincronizando con CodeByDante Cloud...</p>
          </div>
        ) : (
          <>
            {view === 'LIST' && (
              <>
                {/* Navegación (Solo visible dentro de carpetas para mantener limpia la raíz) */}
                {currentFolderId !== null && (
                  <div className="mb-5">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4 -mt-3 sm:-mt-4">
                      <button 
                        onClick={() => {
                           if (breadcrumbs.length > 1) {
                               setCurrentFolderId(breadcrumbs[breadcrumbs.length - 2].id);
                           } else {
                               setCurrentFolderId(null);
                           }
                           setCurrentPage(1);
                        }}
                        className="flex items-center justify-center sm:justify-start gap-2 px-3 py-1.5 rounded-lg bg-surface hover:bg-white/10 text-gray-300 hover:text-white transition-all text-sm font-medium border border-white/5 w-fit shadow-sm shrink-0"
                      >
                        <ChevronLeft size={16} /> Volver
                      </button>
                      
                      {isShowBreadcrumbsEnabled && (
                        <div className="flex items-center gap-1 text-sm text-gray-400 overflow-x-auto pb-1 sm:pb-0 custom-scrollbar w-max max-w-full">
                          <button 
                            onClick={() => {
                               setCurrentFolderId(null);
                               setCurrentPage(1);
                            }}
                            className="hover:text-white transition-colors px-2 py-1 rounded-md hover:bg-white/5"
                          >
                            Raíz
                          </button>
                          {breadcrumbs.map((crumb) => (
                            <React.Fragment key={crumb.id}>
                              <ChevronRight size={14} className="opacity-50 shrink-0" />
                              <button
                                onClick={() => {
                                   setCurrentFolderId(crumb.id);
                                   setCurrentPage(1);
                                }}
                                className={`hover:text-white transition-colors whitespace-nowrap px-2 py-1 rounded-md hover:bg-white/5 ${currentFolderId === crumb.id ? 'text-white font-bold' : ''}`}
                              >
                                {crumb.title}
                              </button>
                            </React.Fragment>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {filteredItems.length === 0 ? (
                  <div className="text-center py-20 opacity-50">
                    <div className="inline-block p-6 rounded-full bg-surface mb-4">
                      <Search size={48} className="text-gray-600" />
                    </div>
                    <h3 className="text-xl font-medium">No se encontraron elementos</h3>
                    <p className="text-gray-500 mt-2">El repositorio está vacío o no hay coincidencias.</p>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 items-start">
                      {paginatedItems.map(item => (
                        <Card
                          key={item.id}
                          item={item}
                          onClick={(i) => { 
                            if (isCategoriesPlusEnabled || isDeletePlusEnabled || isFoldersPlusEnabled || isDuplicatePlusEnabled || isPinPlusEnabled) return;
                            if (i.isFolder) {
                               setCurrentFolderId(i.id);
                               setCurrentPage(1);
                               return;
                            }
                            setSelectedItem(i);
                            setView('DETAIL');
                          }}
                          isSelectable={viewMode === 'admin' && (isCategoriesPlusEnabled || isDeletePlusEnabled || isFoldersPlusEnabled || isDuplicatePlusEnabled || isPinPlusEnabled)}
                          isSelected={selectedItemIds.has(item.id)}
                          onMouseDown={(e, i) => {
                            if (!(isCategoriesPlusEnabled || isDeletePlusEnabled || isFoldersPlusEnabled || isDuplicatePlusEnabled || isPinPlusEnabled)) return;
                            setIsDragging(true);
                            const currentlySelected = selectedItemIds.has(i.id);
                            setDragMode(currentlySelected ? 'deselect' : 'select');
                            
                            setSelectedItemIds(prev => {
                              const next = new Set(prev);
                              if (currentlySelected) next.delete(i.id);
                              else next.add(i.id);
                              return next;
                            });
                          }}
                          onMouseEnter={(e, i) => {
                            if (!(isCategoriesPlusEnabled || isDeletePlusEnabled || isFoldersPlusEnabled || isDuplicatePlusEnabled || isPinPlusEnabled) || !isDragging) return;
                            setSelectedItemIds(prev => {
                              const next = new Set(prev);
                              if (dragMode === 'select') next.add(i.id);
                              else next.delete(i.id);
                              return next;
                            });
                          }}
                        />
                      ))}
                    </div>
                    {renderPagination()}
                  </>
                )}
              </>
            )}

            {view === 'CREATE' && (
              <DataForm
                onSave={async (data) => {
                  try {
                    await addItem({
                       ...data,
                       parentId: currentFolderId
                    });
                    setView('LIST');
                  } catch (e) {
                    alert("Error al guardar en la nube.");
                  }
                }}
                onCancel={() => setView('LIST')}
              />
            )}

            {view === 'EDIT' && selectedItem && (
              <DataForm
                initialData={selectedItem}
                onSave={(data) => {
                  handleUpdate(data);
                  setView('DETAIL');
                }}
                onCancel={() => setView('DETAIL')}
              />
            )}

            {view === 'DETAIL' && selectedItem && (
              <DetailView
                item={selectedItem}
                onBack={() => setView('LIST')}
                onUpdate={handleUpdate}
                onDelete={handleDelete}
                onDuplicate={() => {
                  const { id, createdAt, updatedAt, ...rest } = selectedItem;
                  handleCreate({ ...rest, title: `${rest.title} (Copia)` });
                }}
                isEditable={viewMode === 'admin'}
                onTagClick={(tag) => {
                  setSearchQuery(tag);
                  setView('LIST');
                }}
              />
            )}
          </>
        )}
      </main>

      {/* Floating Action Bar for Bulk Mode */}
      {(isCategoriesPlusEnabled || isDeletePlusEnabled || isFoldersPlusEnabled || isDuplicatePlusEnabled || isPinPlusEnabled || selectedItemIds.size > 0) && viewMode === 'admin' && view === 'LIST' && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-40 bg-[#121212] border border-white/10 p-4 rounded-2xl shadow-[0_0_30px_rgba(0,0,0,0.8)] flex items-center justify-between gap-6 min-w-[320px] animate-in slide-in-from-bottom-5 duration-300">
          <div className="flex flex-col min-w-[120px]">
            <span className="text-white font-bold">{selectedItemIds.size} seleccionados</span>
            <span className="text-gray-500 text-xs text-left">Listos para acción</span>
          </div>
          <div className="flex items-center gap-3">
            {paginatedItems.length > 0 && (
              <button 
                onClick={() => {
                  const visibleIds = paginatedItems.map(i => i.id);
                  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every(id => selectedItemIds.has(id));
                  
                  setSelectedItemIds(prev => {
                    const next = new Set(prev);
                    if (allVisibleSelected) {
                      visibleIds.forEach(id => next.delete(id));
                    } else {
                      visibleIds.forEach(id => next.add(id));
                    }
                    return next;
                  });
                }}
                className="text-primary hover:text-primary/80 px-2 py-1 text-sm font-medium transition-colors whitespace-nowrap"
              >
                {paginatedItems.length > 0 && paginatedItems.every(i => selectedItemIds.has(i.id)) ? 'Desmarcar Todos' : 'Seleccionar Todos'}
              </button>
            )}
            <button 
              onClick={() => setSelectedItemIds(new Set())} 
              className="text-gray-400 hover:text-white px-2 py-1 text-sm transition-colors"
            >
              Limpiar
            </button>
            {isDeletePlusEnabled && (
              <Button 
                onClick={() => setShowConfirmDelete(true)} 
                className="!py-2 !px-4 bg-red-500/10 text-red-500 hover:bg-red-500 hover:text-white border-transparent"
                disabled={selectedItemIds.size === 0}
              >
                <Trash size={16} /> <span className="hidden sm:inline">Eliminar</span>
              </Button>
            )}
            {isDuplicatePlusEnabled && (
              <Button 
                onClick={async () => {
                   try {
                     await Promise.all(
                       Array.from(selectedItemIds).map(async (id) => {
                         const item = items.find(i => i.id === id);
                         if (item) {
                           const { id: _id, createdAt, updatedAt, ...rest } = item;
                           await addItem({ ...rest, title: `${rest.title} (Copia)` });
                         }
                       })
                     );
                     setSelectedItemIds(new Set());
                   } catch(e) {
                     alert("Error al duplicar las entradas.");
                   }
                }} 
                className="!py-2 !px-4 bg-purple-500/10 text-purple-400 hover:bg-purple-500 hover:text-white border-transparent"
                disabled={selectedItemIds.size === 0}
              >
                <Copy size={16} /> <span className="hidden sm:inline">Duplicar</span>
              </Button>
            )}
            {isPinPlusEnabled && (
              <Button 
                onClick={async () => {
                   try {
                     const selectedItems = items.filter(i => selectedItemIds.has(i.id));
                     const allPinned = selectedItems.every(i => i.isPinned);
                     
                     await Promise.all(
                       Array.from(selectedItemIds).map(id => updateItem(id, { isPinned: !allPinned }))
                     );
                     setSelectedItemIds(new Set());
                   } catch(e) {
                     alert("Error al anclar las entradas.");
                   }
                }} 
                className={`!py-2 !px-4 ${items.filter(i => selectedItemIds.has(i.id)).every(i => i.isPinned) ? 'bg-gray-500/10 text-gray-400 hover:bg-gray-500 hover:text-white' : 'bg-primary/10 text-primary hover:bg-primary hover:text-[#121212]'} border-transparent`}
                disabled={selectedItemIds.size === 0}
              >
                <Pin size={16} /> <span className="hidden sm:inline">{items.filter(i => selectedItemIds.has(i.id)).every(i => i.isPinned) ? 'Desanclar' : 'Anclar'}</span>
              </Button>
            )}
            {isFoldersPlusEnabled && (
              <Button 
                onClick={() => setShowMoveToFolder(true)} 
                className="!py-2 !px-4 bg-blue-500/10 text-blue-400 hover:bg-blue-500 hover:text-white border-transparent"
                disabled={selectedItemIds.size === 0}
              >
                <Folder size={16} /> <span className="hidden sm:inline">Mover a Carpeta</span>
              </Button>
            )}
            {isCategoriesPlusEnabled && (
              <Button 
                onClick={() => setShowBulkCategoryModal(true)} 
                className="!py-2 !px-4"
                disabled={isApplyingCategories || selectedItemIds.size === 0}
              >
                {isApplyingCategories ? <Loader2 size={16} className="animate-spin" /> : 'Aplicar Categorías'}
              </Button>
            )}
          </div>
        </div>
      )}

      <ConfirmModal 
        isOpen={showConfirmDelete}
        onClose={() => setShowConfirmDelete(false)}
        title="Confirmar eliminación"
        message={`¿Estás seguro de que quieres eliminar ${selectedItemIds.size} elemento(s)? Esta acción no se puede deshacer.`}
        confirmText="Eliminar"
        isDestructive={true}
        onConfirm={async () => {
          try {
            await Promise.all(Array.from(selectedItemIds).map(id => deleteItem(id)));
            setSelectedItemIds(new Set());
          } catch (e) {
            alert('Error al eliminar los elementos.');
          }
        }}
      />

      <MoveToFolderModal 
        isOpen={showMoveToFolder}
        onClose={() => setShowMoveToFolder(false)}
        selectionCount={selectedItemIds.size}
        currentFolderId={currentFolderId}
        folders={items.filter(i => i.isFolder)}
        onMoveToFolder={async (folderId) => {
           try {
             await Promise.all(
               Array.from(selectedItemIds).map(id => updateItem(id, { parentId: folderId }))
             );
             setSelectedItemIds(new Set());
           } catch (e) {
             console.error(e);
             throw e;
           }
        }}
        onCreateFolder={async (name) => {
           const newFolder = {
             title: name,
             summary: 'Carpeta',
             content: '',
             tags: [],
             categories: [],
             isFolder: true,
             parentId: currentFolderId
           };
           
           const newId = await addItem(newFolder);
           return newId;
        }}
      />

      <BulkCategoryModal
        isOpen={showBulkCategoryModal}
        onClose={() => setShowBulkCategoryModal(false)}
        selectionCount={selectedItemIds.size}
        onApply={async (categories) => {
          setIsApplyingCategories(true);
          try {
            await Promise.all(
              Array.from(selectedItemIds).map(async (id) => {
                const item = items.find(i => i.id === id);
                if (item) {
                  const mergedCats = Array.from(new Set([...(item.categories || []), ...categories]));
                  await updateItem(id, { categories: mergedCats });
                }
              })
            );
            setShowBulkCategoryModal(false);
            setSelectedItemIds(new Set());
          } catch (err) {
            console.error('Error applying bulk categories:', err);
            alert('Error al aplicar las categorías');
          } finally {
            setIsApplyingCategories(false); 
          }
        }}
      />

      <TrashModal
        isOpen={isTrashOpen}
        onClose={() => setIsTrashOpen(false)}
        deletedItems={deletedItems}
        allFolders={items.filter(i => i.isFolder)}
      />
    </div>
  );
};

export default App;