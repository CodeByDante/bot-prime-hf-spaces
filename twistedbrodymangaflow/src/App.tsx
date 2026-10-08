import { Plus, Settings, Layers, User, Copy, Edit3, Tag, BookOpen, Folder, ArrowLeft, Menu, X, ExternalLink, Link } from 'lucide-react';
import { useState, useEffect, useMemo } from 'react';
import { HDComicViewer } from './components/HDComicViewer';
import { NewMangaModal } from './components/NewMangaModal';
import { SettingsModal } from './components/SettingsModal';
import { AnnouncementBanner } from './components/AnnouncementBanner';
import { ComicDetail } from './components/ComicDetail';
import { ChapterReader } from './components/ChapterReader';
import { InfoPage } from './components/InfoPage';
import { BulkCategoryModal } from './components/BulkCategoryModal';
import { BulkRemoveCategoryModal } from './components/BulkRemoveCategoryModal';
import { CategoryFilterModal } from './components/CategoryFilterModal';
import { TitleManagerModal } from './components/TitleManagerModal';
import { BulkEditTitleModal } from './components/BulkEditTitleModal';
import { EtiquetadoraModal } from './components/EtiquetadoraModal';
import { CreateFolderModal } from './components/CreateFolderModal';
import { MoveToFolderModal } from './components/MoveToFolderModal';
import { MoveSectionModal } from './components/MoveSectionModal';
import { FolderMentalMapModal } from './components/FolderMentalMapModal';
import { TrashModal } from './components/TrashModal';
import { ConfirmModal } from './components/ConfirmModal';
import { TransferPagesModal } from './components/TransferPagesModal';
import { Category } from './types/manga';
import { PatreonIcon } from './components/PatreonIcon';
import { NavigationDrawer } from './components/NavigationDrawer';
import { FavoritesView } from './components/FavoritesView';

import { SearchBar } from './components/SearchBar';
import { SearchResults } from './components/SearchResults';
import { Toaster, toast } from 'sonner';
import { deleteManga, getAllMangas, updateMangaTitles, restoreManga, permanentDeleteManga, mergeMangas } from './services/manga';
import { Manga, Chapter } from './types/manga';
import { searchItems } from './utils/searchUtils';
import { GlobalFooter } from './components/GlobalFooter';

type SortType = 'random' | 'name' | 'date' | 'pages' | 'modified' | 'views';
type SortDirection = 'asc' | 'desc';

function App() {
  const [showModal, setShowModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showFilterModal, setShowFilterModal] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [editingManga, setEditingManga] = useState<Manga | null>(null);
  const [isCategoryPlusEnabled, setIsCategoryPlusEnabled] = useState(false);
  const [isCopyIdsEnabled, setIsCopyIdsEnabled] = useState(false);
  const [isDeletePlusEnabled, setIsDeletePlusEnabled] = useState(false);
  const [selectedMangaIds, setSelectedMangaIds] = useState<string[]>([]);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showBulkRemoveModal, setShowBulkRemoveModal] = useState(false);
  const [showBulkEditTitleModal, setShowBulkEditTitleModal] = useState(false);
  const [showEtiquetadoraModal, setShowEtiquetadoraModal] = useState(false);
  const [showTitleManagerModal, setShowTitleManagerModal] = useState(false);
  const [showFolderMapModal, setShowFolderMapModal] = useState(false);
  const [showTrashModal, setShowTrashModal] = useState(false);
  const [showTransferPagesModal, setShowTransferPagesModal] = useState(false);
  const [showKemonoCleanConfirm, setShowKemonoCleanConfirm] = useState(false);
  const [isFolderAnimationEnabled, setIsFolderAnimationEnabled] = useState(() => {
    return localStorage.getItem('isFolderAnimationEnabled') === 'true';
  });
  const [isCategoryMinusEnabled, setIsCategoryMinusEnabled] = useState(false);
  const [isEditTitlePlusEnabled, setIsEditTitlePlusEnabled] = useState(false);
  const [isEtiquetadoraEnabled, setIsEtiquetadoraEnabled] = useState(false);
  const [isFolderPlusEnabled, setIsFolderPlusEnabled] = useState(false);
  const [isPortalPlusEnabled, setIsPortalPlusEnabled] = useState(false);
  const [isMergePlusEnabled, setIsMergePlusEnabled] = useState(false);
  const [isTransferPlusEnabled, setIsTransferPlusEnabled] = useState(false);
  const [currentFolderId, setCurrentFolderId] = useState<string | null>(null);
  const [showCreateFolderModal, setShowCreateFolderModal] = useState(false);
  const [showMoveToFolderModal, setShowMoveToFolderModal] = useState(false);
  const [showMoveSectionModal, setShowMoveSectionModal] = useState(false);
  const [selectedComicId, setSelectedComicId] = useState<string | null>(null);
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<{ manga: Manga; chapter: Chapter } | null>(null);
  const [mangas, setMangas] = useState<Manga[]>([]);
  const [currentSection, setCurrentSection] = useState<'flow' | 'patreon' | 'onlyfans' | 'grok' | 'favorites'>(() => {
    const params = new URLSearchParams(window.location.search);
    const sec = params.get('section');
    if (sec === 'flow' || sec === 'patreon' || sec === 'onlyfans' || sec === 'grok' || sec === 'favorites') return sec as 'flow' | 'patreon' | 'onlyfans' | 'grok' | 'favorites';
    return (localStorage.getItem('currentSection') as 'flow' | 'patreon' | 'onlyfans' | 'grok' | 'favorites') || 'flow';
  });
  const [showHD, setShowHD] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [viewFilter, setViewFilter] = useState<'all' | 'mangas' | 'folders'>('all');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  const [filterDecensored, setFilterDecensored] = useState<boolean>(false);
  const [filterBN, setFilterBN] = useState<boolean>(false);
  const [filterColor, setFilterColor] = useState<boolean>(false);
  const [sortType, setSortType] = useState<SortType>(() =>
    (localStorage.getItem('sortType') as SortType) || 'modified'
  );
  const [sortDirection, setSortDirection] = useState<SortDirection>(() =>
    (localStorage.getItem('sortDirection') as SortDirection) || 'desc'
  );

  useEffect(() => {
    const searchParams = new URLSearchParams(window.location.search);
    const isAdminMode = searchParams.get('admin') === 'true';
    setIsAdmin(isAdminMode);
  }, []);

  useEffect(() => {
    localStorage.setItem('sortType', sortType);
  }, [sortType]);

  useEffect(() => {
    localStorage.setItem('isFolderAnimationEnabled', String(isFolderAnimationEnabled));
  }, [isFolderAnimationEnabled]);

  useEffect(() => {
    localStorage.setItem('sortDirection', sortDirection);
  }, [sortDirection]);

  useEffect(() => {
    localStorage.setItem('currentSection', currentSection);
    const url = new URL(window.location.href);
    if (currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' || currentSection === 'favorites') {
      url.searchParams.set('section', currentSection);
    } else {
      url.searchParams.delete('section');
    }
    window.history.replaceState({}, '', url.toString());
  }, [currentSection]);

  useEffect(() => {
    // @ts-expect-error Window interface is extended in vite-env.d.ts
    if (window.Telegram?.WebApp) {
      // @ts-expect-error Window interface is extended in vite-env.d.ts
      window.Telegram.WebApp.ready();
    }
    loadMangas();

    const hash = window.location.hash.slice(1);
    if (hash && hash.startsWith('manga/')) {
      if (hash.endsWith('/hd')) {
        const mangaId = hash.replace('manga/', '').replace('/hd', '');
        setSelectedComicId(mangaId);
        setShowHD(true);
      } else {
        const mangaId = hash.replace('manga/', '');
        setSelectedComicId(mangaId);
        setShowHD(false);
      }
    } else if (hash && hash.startsWith('folder/')) {
      const folderId = hash.replace('folder/', '');
      setCurrentFolderId(folderId);
    } else if (hash === 'info') {
      setShowInfo(true);
    }

    const handleHashChange = () => {
      const hash = window.location.hash.slice(1);
      if (!hash) {
        setSelectedComicId(null);
        setSelectedChapter(null);
        setShowInfo(false);
        setShowHD(false);
        setCurrentFolderId(null);
      } else if (hash.startsWith('manga/')) {
        if (hash.endsWith('/hd')) {
          const mangaId = hash.replace('manga/', '').replace('/hd', '');
          setSelectedComicId(mangaId);
          setShowHD(true);
        } else {
          const mangaId = hash.replace('manga/', '');
          setSelectedComicId(mangaId);
          setShowHD(false);
        }
        setSelectedChapter(null);
        setShowInfo(false);
        setCurrentFolderId(null);
      } else if (hash.startsWith('folder/')) {
        setCurrentFolderId(hash.replace('folder/', ''));
        setSelectedComicId(null);
        setSelectedChapter(null);
        setShowInfo(false);
        setShowHD(false);
      } else if (hash === 'info') {
        setShowInfo(true);
        setSelectedComicId(null);
        setSelectedChapter(null);
        setCurrentFolderId(null);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    const isAnyToolEnabled = isCategoryPlusEnabled || isCopyIdsEnabled || isDeletePlusEnabled || isCategoryMinusEnabled || isEditTitlePlusEnabled || isEtiquetadoraEnabled || isFolderPlusEnabled || isPortalPlusEnabled || isMergePlusEnabled || isTransferPlusEnabled;
    if (!isAnyToolEnabled && selectedMangaIds.length > 0) {
      setSelectedMangaIds([]);
    }
  }, [
    isCategoryPlusEnabled, isCopyIdsEnabled, isDeletePlusEnabled, isCategoryMinusEnabled, 
    isEditTitlePlusEnabled, isEtiquetadoraEnabled, isFolderPlusEnabled, isPortalPlusEnabled, 
    isMergePlusEnabled, isTransferPlusEnabled
  ]);

  async function loadMangas() {
    try {
      setLoading(true);
      const data = await getAllMangas();
      setMangas(data);
    } catch (error) {
      console.error('Error loading mangas:', error);
    } finally {
      setLoading(false);
    }
  }

  const sectionMangas = useMemo(() => {
    return mangas.filter(m => !m.is_deleted && (m.section || 'flow') === currentSection);
  }, [mangas, currentSection]);

  const deletedMangas = useMemo(() => {
    return mangas.filter(m => m.is_deleted);
  }, [mangas]);

  const allCategories = useMemo(() => {
    const categoriesMap = new Map<string, Category>();
    sectionMangas.forEach(manga => {
      manga.categories?.forEach(cat => {
        if (!categoriesMap.has(cat.id)) {
          categoriesMap.set(cat.id, cat);
        }
      });
    });
    return Array.from(categoriesMap.values());
  }, [sectionMangas]);

  const searchResult = useMemo(() => {
    if (!searchTerm.trim()) {
      return { items: sectionMangas, query: '', resultCount: sectionMangas.length };
    }
    return searchItems(
      sectionMangas
        .filter(m => !m.is_folder)
        .map(m => ({
          id: m.id,
          title: m.title,
          author: m.author,
          categories: m.categories ? m.categories.map(c => c.name) : []
        })),
      searchTerm,
      { fuzzyMatch: true, minChars: 1 }
    );
  }, [sectionMangas, searchTerm]);

  const filteredMangas = useMemo(() => {
    let items = searchResult.items.length > 0
      ? searchResult.items.map(item => sectionMangas.find(m => m.id === item.id)).filter(Boolean) as Manga[]
      : [];

    if (selectedCategories.length > 0) {
      items = items.filter(m =>
        selectedCategories.some(selCat => m.categories?.some(c => c.name === selCat))
      );
    }

    if (selectedAuthors.length > 0) {
      items = items.filter(m =>
        selectedAuthors.includes(m.author)
      );
    }

    if (filterDecensored) items = items.filter(m => m.is_decensored);
    if (filterBN) items = items.filter(m => m.is_bn);
    if (filterColor) items = items.filter(m => m.is_color);

    const sorted = [...items];

    const isFiltering = selectedCategories.length > 0 || selectedAuthors.length > 0 || filterDecensored || filterBN || filterColor;
    const isTextSearching = searchTerm.trim().length > 0;
    
    let filteredByFolder: Manga[];

    if (isFiltering) {
      filteredByFolder = sorted;
    } else if (isTextSearching) {
      const matchedIds = new Set(sorted.map(m => m.id));
      const matchedFolderIds = new Set<string>();
      
      for (const m of sorted) {
        let current = m.folder_id;
        let depth = 0;
        while (current && depth < 20) {
          matchedFolderIds.add(current);
          const parent = sectionMangas.find(p => p.id === current);
          if (parent) {
            current = parent.folder_id;
          } else {
            break;
          }
          depth++;
        }
      }

      filteredByFolder = sectionMangas.filter(m => {
        const effectiveFolderId = (m.folder_id && sectionMangas.some(sm => sm.id === m.folder_id)) ? m.folder_id : null;
        if (effectiveFolderId !== (currentFolderId || null)) return false;
        
        if (m.is_folder) {
          return matchedIds.has(m.id) || matchedFolderIds.has(m.id);
        }
        
        return matchedIds.has(m.id);
      });
    } else {
      filteredByFolder = sorted.filter(m => {
        const effectiveFolderId = (m.folder_id && sectionMangas.some(sm => sm.id === m.folder_id)) ? m.folder_id : null;
        return effectiveFolderId === (currentFolderId || null);
      });
    }

    let filteredByView = filteredByFolder;
    if (viewFilter === 'mangas') {
      filteredByView = filteredByView.filter(m => !m.is_folder);
    } else if (viewFilter === 'folders') {
      filteredByView = filteredByView.filter(m => m.is_folder);
    }

    if (sortType === 'random') {
      return filteredByView.sort(() => Math.random() - 0.5);
    }

    filteredByView.sort((a, b) => {
      let compareValue = 0;

      if (sortType === 'name') {
        compareValue = a.title.localeCompare(b.title);
      } else if (sortType === 'date') {
        const dateA = new Date(a.created_at || 0).getTime();
        const dateB = new Date(b.created_at || 0).getTime();
        compareValue = dateA - dateB;
      } else if (sortType === 'modified') {
        const dateA = new Date(a.updated_at || a.created_at || 0).getTime();
        const dateB = new Date(b.updated_at || b.created_at || 0).getTime();
        compareValue = dateA - dateB;
      } else if (sortType === 'pages') {
        const pagesA = a.chapters?.reduce((sum: number, ch: any) => sum + (ch.pages?.length || 0), 0) || 0;
        const pagesB = b.chapters?.reduce((sum: number, ch: any) => sum + (ch.pages?.length || 0), 0) || 0;
        compareValue = pagesA - pagesB;
      } else if (sortType === 'views') {
        compareValue = (a.views || 0) - (b.views || 0);
      }

      return sortDirection === 'asc' ? compareValue : -compareValue;
    });

    return filteredByView;
  }, [sectionMangas, searchTerm, searchResult.items, sortType, sortDirection, selectedCategories, selectedAuthors, currentFolderId, viewFilter, filterDecensored, filterBN, filterColor]);

  const handleEditManga = (manga: Manga) => {
    setEditingManga(manga);
    setShowModal(true);
  };

  const handleDeleteManga = async (mangaId: string) => {
    try {
      await deleteManga(mangaId);
      await loadMangas();
    } catch (error) {
      console.error('Error deleting manga:', error);
      alert('Error al eliminar el manga. Por favor intenta de nuevo.');
    }
  };

  const handleCleanKemonoTitles = async () => {
    const pattern = /\s*\[\d+\]\s*$/;
    const updates = mangas
      .filter(m => pattern.test(m.title))
      .map(m => {
          let newTitle = m.title.replace(pattern, '').trim();
          if (!newTitle) newTitle = m.title;
          return { id: m.id, title: newTitle };
      })
      .filter(u => u.title !== mangas.find(m => m.id === u.id)?.title);

    if (updates.length === 0) {
      toast.info('No hay nombres con formato [ID] que requieran limpieza.');
      return;
    }

    try {
      await updateMangaTitles(updates);
      toast.success(`Se limpiaron ${updates.length} nombres correctamente.`);
      loadMangas();
    } catch (err) {
      console.error(err);
      toast.error('Ocurrió un error al intentar limpiar los nombres.');
    }
  };

  const handleSelectAll = () => {
    let allIds: string[] = [];
    
    const getItemsInFolder = (folderId: string): string[] => {
      let result: string[] = [];
      const children = sectionMangas.filter(m => m.folder_id === folderId);
      for (const child of children) {
        result.push(child.id);
        if (child.is_folder) {
          result = result.concat(getItemsInFolder(child.id));
        }
      }
      return result;
    };

    filteredMangas.forEach(target => {
      allIds.push(target.id);
      if (target.is_folder) {
        allIds = allIds.concat(getItemsInFolder(target.id));
      }
    });

    const uniqueIds = Array.from(new Set(allIds));
    const allSelected = uniqueIds.length > 0 && uniqueIds.every(id => selectedMangaIds.includes(id));
    
    if (allSelected) {
      setSelectedMangaIds([]);
    } else {
      setSelectedMangaIds(uniqueIds);
    }
  };

  const toggleSelectManga = (id: string) => {
    const target = sectionMangas.find(m => m.id === id);
    if (!target) return;

    if (target.is_folder) {
      const getItemsInFolder = (folderId: string): string[] => {
        let result: string[] = [];
        const children = sectionMangas.filter(m => m.folder_id === folderId);
        for (const child of children) {
          result.push(child.id);
          if (child.is_folder) {
            result = result.concat(getItemsInFolder(child.id));
          }
        }
        return result;
      };

      const itemsInFolder = getItemsInFolder(id);
      const idsToToggle = [id, ...itemsInFolder];

      setSelectedMangaIds(prev => {
        const isSelected = prev.includes(id);
        if (isSelected) {
          return prev.filter(mId => !idsToToggle.includes(mId));
        } else {
          const newSelection = [...prev];
          idsToToggle.forEach(mId => {
            if (!newSelection.includes(mId)) {
              newSelection.push(mId);
            }
          });
          return newSelection;
        }
      });
      return;
    }

    setSelectedMangaIds(prev => {
      if (prev.includes(id)) {
        return prev.filter(mId => mId !== id);
      } else {
        return [...prev, id];
      }
    });
  };

  const handleSelectComic = (mangaId: string) => {
    if (isCategoryPlusEnabled || isCopyIdsEnabled || isDeletePlusEnabled || isCategoryMinusEnabled || isEditTitlePlusEnabled || isEtiquetadoraEnabled || isFolderPlusEnabled || isPortalPlusEnabled || isMergePlusEnabled || isTransferPlusEnabled) {
      toggleSelectManga(mangaId);
      return;
    }
    const manga = sectionMangas.find(m => m.id === mangaId);
    if (manga?.is_folder) {
      window.location.hash = `folder/${mangaId}`;
      return;
    }
    window.location.hash = `manga/${mangaId}`;
    setSelectedComicId(mangaId);
    setShowHD(false);
  };

  const handleBackToHome = () => {
    window.location.hash = '';
    setSelectedComicId(null);
    setShowInfo(false);
  };

  const handleNavigateToManga = (newMangaId: string) => {
    const manga = mangas.find(m => m.id === newMangaId);
    if (manga?.is_folder) {
      window.location.hash = `folder/${newMangaId}`;
      return;
    }

    if (selectedComicId) {
      setNavigationHistory([...navigationHistory, selectedComicId]);
    }
    window.location.hash = `manga/${newMangaId}`;
    setSelectedComicId(newMangaId);
  };

  const handleSelectCategory = (category: string) => {
    setSelectedCategories(prev => {
      if (prev.includes(category)) {
        return prev.filter(c => c !== category);
      }
      return [...prev, category];
    });
    handleBackToHome();
  };

  const handleRemoveCategory = (category: string) => {
    setSelectedCategories(prev => prev.filter(c => c !== category));
  };

  const handleSelectAuthor = (author: string) => {
    setSelectedAuthors(prev => {
      if (prev.includes(author)) {
        return prev.filter(c => c !== author);
      }
      return [...prev, author];
    });
    handleBackToHome();
  };

  const handleRemoveAuthor = (author: string) => {
    setSelectedAuthors(prev => prev.filter(c => c !== author));
  };

  const mangaItems = useMemo(() => filteredMangas.map(manga => {
    const chapterCount = manga.chapters?.length || 0;
    const totalPages = manga.chapters?.reduce((sum: number, ch: any) => sum + (ch.pages?.length || 0), 0) || 0;
    return {
      id: manga.id,
      title: manga.title,
      author: manga.author,
      chapterCount,
      pageCount: totalPages,
      thumbnail: manga.cover_url || manga.thumbnail_url || undefined,
      manga,
    };
  }), [filteredMangas]);

  if (selectedChapter) {
    return (
      <ChapterReader
        manga={selectedChapter.manga}
        chapter={selectedChapter.chapter}
        onBack={() => setSelectedChapter(null)}
      />
    );
  }

  if (showInfo) {
    return <InfoPage onBack={handleBackToHome} isAdmin={isAdmin} />;
  }

  if (selectedComicId !== null) {
    let currentManga = mangas.find(m => m.id === selectedComicId);

    if (showHD && currentManga) {
      return (
        <HDComicViewer
          manga={currentManga}
          onBack={() => {
            if (currentManga) {
              window.location.hash = `manga/${currentManga.id}`;
            }
            setShowHD(false);
          }}
        />
      );
    }

    return (
      <ComicDetail
        id={selectedComicId}
        onBack={() => {
          if (navigationHistory.length > 0) {
            const previousId = navigationHistory[navigationHistory.length - 1];
            setNavigationHistory(navigationHistory.slice(0, -1));
            window.location.hash = `manga/${previousId}`;
            setSelectedComicId(previousId);
          } else if (currentManga?.folder_id) {
            window.location.hash = `folder/${currentManga.folder_id}`;
            setCurrentFolderId(currentManga.folder_id);
            setSelectedComicId(null);
          } else {
            handleBackToHome();
          }
        }}
        onReadChapter={(chapter) => {
          if (currentManga) {
            setSelectedChapter({ manga: currentManga, chapter });
          }
        }}
        onMangaLoaded={(loadedManga) => {
          if (!currentManga) {
            currentManga = loadedManga;
          }
        }}
        onNavigateToManga={handleNavigateToManga}
        onSelectCategory={handleSelectCategory}
        onSelectAuthor={handleSelectAuthor}
        isAdmin={isAdmin}
      />
    );
  }

  return (
    <div className="min-h-screen bg-[#121212] text-white flex flex-col">
      <header className="border-b border-gray-800/50 px-3 sm:px-6 md:px-12 py-4 sm:py-6 flex-shrink-0 transition-all duration-300">
        <div className="max-w-[1800px] mx-auto flex items-center justify-between gap-2 sm:gap-0">
          <div className="flex items-center gap-1 sm:gap-3">
            <NavigationDrawer currentSection={currentSection} onSectionChange={setCurrentSection} />
            <div className="flex items-center gap-1.5 sm:gap-3 group cursor-pointer min-w-0 flex-1">
              <img
                src="/icons/icones.png"
                alt="Twisted Brody Logo"
                className="w-8 h-8 sm:w-14 sm:h-14 object-contain transition-all duration-300 group-hover:rotate-12 group-hover:scale-110 flex-shrink-0"
              />
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-0.5 sm:gap-3 min-w-0">
              <h1 className="text-[13px] sm:text-2xl font-bold text-white transition-colors duration-300 group-hover:text-[#bb86fc] leading-tight truncate w-full max-w-[130px] sm:max-w-none">
                Twisted Brody MangaFlow
              </h1>
              <div className="flex items-center gap-1 bg-[#1a1a1a] border border-[#333] px-1.5 sm:px-3 py-0.5 sm:py-1 rounded-full shadow-inner w-fit mt-0.5 sm:mt-0 flex-shrink-0">
                <button
                  onClick={() => setViewFilter(prev => prev === 'mangas' ? 'all' : 'mangas')}
                  className={`flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 rounded-full transition-colors ${viewFilter === 'mangas' ? 'bg-[#bb86fc]/20 border border-[#bb86fc]/50' : 'hover:bg-white/5 border border-transparent cursor-pointer'}`}
                >
                  <BookOpen className="w-3 h-3 sm:w-4 sm:h-4 text-[#bb86fc]" />
                  <span className="text-xs sm:text-sm font-bold text-gray-300">
                    {sectionMangas.filter(m => !m.is_folder).length} <span className="text-[9px] sm:text-xs text-gray-500 font-normal hidden sm:inline">mangas</span>
                  </span>
                </button>
                <span className="text-gray-600 mx-0.5 sm:mx-1 text-xs sm:text-base">|</span>
                <button
                  onClick={() => setViewFilter(prev => prev === 'folders' ? 'all' : 'folders')}
                  className={`flex items-center gap-1 sm:gap-1.5 px-1.5 sm:px-2 py-0.5 rounded-full transition-colors ${viewFilter === 'folders' ? 'bg-[#bb86fc]/20 border border-[#bb86fc]/50' : 'hover:bg-white/5 border border-transparent cursor-pointer'}`}
                >
                  <Folder className="w-3 h-3 sm:w-4 sm:h-4 text-[#bb86fc]" />
                  <span className="text-xs sm:text-sm font-bold text-gray-300">
                    {sectionMangas.filter(m => m.is_folder).length} <span className="text-[9px] sm:text-xs text-gray-500 font-normal hidden sm:inline">carpetas</span>
                  </span>
                </button>
              </div>
            </div>
            </div>
          </div>
          <div className="flex items-center gap-1 sm:gap-3 flex-shrink-0">
            {(isCategoryPlusEnabled || isCopyIdsEnabled || isDeletePlusEnabled || isCategoryMinusEnabled || isEditTitlePlusEnabled || isEtiquetadoraEnabled || isFolderPlusEnabled || isPortalPlusEnabled || isTransferPlusEnabled) && (
              <div className="hidden sm:flex items-center gap-2 mr-2 px-3 py-1.5 bg-purple-500/10 rounded-lg border border-purple-500/20">
                <Layers className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-semibold text-purple-300">
                  {isEtiquetadoraEnabled ? 'Modo Etiquetar Activo' : isPortalPlusEnabled ? 'Portal Plus Activo' : isFolderPlusEnabled ? 'Carpetas Plus Activo' : isEditTitlePlusEnabled ? 'Modo Nombres Activo' : isCopyIdsEnabled ? 'Modo Copiar Activo' : isDeletePlusEnabled ? 'Modo Eliminar Activo' : isCategoryMinusEnabled ? 'Modo Minus Activo' : isTransferPlusEnabled ? 'Transferencia Activa' : 'Modo Plus Activo'}
                </span>
                <span className="text-xs bg-purple-500/20 px-2 py-0.5 rounded text-purple-200">
                  {selectedMangaIds.length}
                </span>
              </div>
            )}
            {isAdmin && (
              <>
                <button
                  onClick={() => setShowSettingsModal(true)}
                  className="bg-gray-800 hover:bg-gray-700 active:scale-95 text-white p-1.5 sm:px-4 sm:py-2.5 rounded-lg flex items-center gap-1.5 sm:gap-2 font-semibold transition-all duration-300 border border-gray-700/50 hover:border-gray-600 text-xs sm:text-sm hover:scale-110 hover:shadow-lg hover:shadow-700/50"
                  title="Ajustes y Admin"
                >
                  <Settings className="w-4 h-4 sm:w-5 sm:h-5 transition-transform duration-300 hover:rotate-180" />
                  <span className="hidden sm:inline">Ajustes</span>
                </button>
                <button
                  onClick={() => setShowModal(true)}
                  className="bg-purple-600 hover:bg-purple-700 active:scale-95 text-white p-1.5 sm:px-4 sm:py-2.5 rounded-lg flex items-center gap-1.5 sm:gap-2 font-semibold transition-all duration-300 shadow-lg shadow-purple-600/30 hover:shadow-purple-600/50 text-xs sm:text-sm hover:scale-110"
                >
                  <Plus className="w-4 h-4 sm:w-5 sm:h-5 transition-transform duration-300 hover:rotate-180" />
                  <span className="hidden sm:inline">{currentSection === 'patreon' ? 'Subir Imágenes' : currentSection === 'onlyfans' ? 'Subir Only' : currentSection === 'grok' ? 'Subir Grok' : 'Nuevo Manga'}</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 sm:px-6 md:px-12 py-8">
        <AnnouncementBanner isAdmin={isAdmin} />

        {currentSection === 'favorites' ? (
          <FavoritesView isAdmin={isAdmin} />
        ) : (
          <>
            <div className="max-w-[1800px] mx-auto mb-8 flex-shrink-0">
              <SearchBar
                value={searchTerm}
                onChange={setSearchTerm}
            placeholder="Buscar por título, autor..."
            sortType={sortType}
            onSortTypeChange={setSortType}
            sortDirection={sortDirection}
            onSortDirectionChange={setSortDirection}
            onOpenFilter={() => setShowFilterModal(true)}
          />
          {searchTerm && (
            <div className="mt-2 text-sm text-gray-400">
              {searchResult.resultCount} resultado{searchResult.resultCount !== 1 ? 's' : ''} encontrado{searchResult.resultCount !== 1 ? 's' : ''}
            </div>
          )}

          {(selectedCategories.length > 0 || selectedAuthors.length > 0 || filterDecensored || filterBN || filterColor) && (
            <div className="mt-4 flex flex-wrap items-center gap-2 animate-in fade-in slide-in-from-top-2 duration-300">
              <span className="text-sm text-gray-400">Filtrado por:</span>
              {selectedCategories.map(cat => (
                <button
                  key={cat}
                  onClick={() => handleRemoveCategory(cat)}
                  className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2 border border-purple-500/30 hover:border-purple-500/50 transition-all group"
                >
                  {cat}
                  <div className="bg-purple-500/20 rounded-full p-0.5 group-hover:bg-purple-500/40 transition-colors">
                    <Plus className="w-3 h-3 transform rotate-45" />
                  </div>
                </button>
              ))}
              {selectedAuthors.map(auth => (
                <button
                  key={auth}
                  onClick={() => handleRemoveAuthor(auth)}
                  className="bg-[#bb86fc]/20 hover:bg-[#bb86fc]/30 text-[#bb86fc] px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2 border border-[#bb86fc]/30 hover:border-[#bb86fc]/50 transition-all group"
                >
                  <User size={14} />
                  {auth}
                  <div className="bg-[#bb86fc]/20 rounded-full p-0.5 group-hover:bg-[#bb86fc]/40 transition-colors">
                    <Plus className="w-3 h-3 transform rotate-45" />
                  </div>
                </button>
              ))}
              {filterDecensored && (
                <button
                  onClick={() => { setFilterDecensored(false); handleBackToHome(); }}
                  className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2 border border-purple-500/30 hover:border-purple-500/50 transition-all group"
                >
                  Sin censura
                  <div className="bg-purple-500/20 rounded-full p-0.5 group-hover:bg-purple-500/40 transition-colors">
                    <Plus className="w-3 h-3 transform rotate-45" />
                  </div>
                </button>
              )}
              {filterBN && (
                <button
                  onClick={() => { setFilterBN(false); handleBackToHome(); }}
                  className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2 border border-purple-500/30 hover:border-purple-500/50 transition-all group"
                >
                  B/N
                  <div className="bg-purple-500/20 rounded-full p-0.5 group-hover:bg-purple-500/40 transition-colors">
                    <Plus className="w-3 h-3 transform rotate-45" />
                  </div>
                </button>
              )}
              {filterColor && (
                <button
                  onClick={() => { setFilterColor(false); handleBackToHome(); }}
                  className="bg-purple-500/20 hover:bg-purple-500/30 text-purple-300 px-3 py-1 rounded-full text-sm font-medium flex items-center gap-2 border border-purple-500/30 hover:border-purple-500/50 transition-all group"
                >
                  A color
                  <div className="bg-purple-500/20 rounded-full p-0.5 group-hover:bg-purple-500/40 transition-colors">
                    <Plus className="w-3 h-3 transform rotate-45" />
                  </div>
                </button>
              )}
              {(selectedCategories.length > 0 || selectedAuthors.length > 0 || filterDecensored || filterBN || filterColor) && (
                <button
                  onClick={() => {
                    setSelectedCategories([]);
                    setSelectedAuthors([]);
                    setFilterDecensored(false);
                    setFilterBN(false);
                    setFilterColor(false);
                  }}
                  className="text-xs text-gray-400 hover:text-white underline decoration-gray-600 hover:decoration-white transition-colors ml-2"
                >
                  Limpiar todo
                </button>
              )}
            </div>
          )}
        </div>

        <div className="max-w-[1800px] mx-auto">
          {currentFolderId && (() => {
             const folder = mangas.find(m => m.id === currentFolderId);
             if (!folder) return null;
             return (
               <div className="mb-6 flex items-center gap-4 bg-[#1a1a1a] p-4 rounded-xl border border-gray-800 animate-in slide-in-from-top-2">
                 <button onClick={() => { 
                   if (folder.folder_id) {
                     window.location.hash = `folder/${folder.folder_id}`;
                   } else {
                     window.location.hash = ''; 
                   }
                 }} className="p-2 hover:bg-gray-800 rounded-lg text-white transition-colors">
                   <ArrowLeft className="w-5 h-5" />
                 </button>
                 <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center">
                   {!folder.folder_id && folder.title.toLowerCase().includes('patreon') ? (
                     <PatreonIcon className="w-6 h-6 text-white" />
                   ) : (
                     <Folder className="w-6 h-6 text-purple-400" />
                   )}
                 </div>
                 <div>
                   <h2 className="text-xl font-bold text-white uppercase tracking-wider">{folder.title}</h2>
                   <p className="text-sm text-gray-400">Carpeta • {sectionMangas.filter(m => m.folder_id === folder.id).length} elementos</p>
                 </div>
               </div>
             );
          })()}
          <SearchResults
            items={mangaItems}
            searchTerm={searchTerm}
            isSearching={false}
            isLoading={loading}
            onSelectComic={handleSelectComic}
            onEditManga={isAdmin ? handleEditManga : undefined}
            onDeleteManga={isAdmin ? handleDeleteManga : undefined}
            isCategoryPlusEnabled={isCategoryPlusEnabled || isCopyIdsEnabled || isDeletePlusEnabled || isCategoryMinusEnabled || isEditTitlePlusEnabled || isEtiquetadoraEnabled || isFolderPlusEnabled || isPortalPlusEnabled || isMergePlusEnabled || isTransferPlusEnabled}
            selectedMangaIds={selectedMangaIds}
            onToggleSelectManga={toggleSelectManga}
            allMangas={sectionMangas}
            isFolderAnimationEnabled={isFolderAnimationEnabled}
            currentSection={currentSection}
          />
        </div>
        </>
        )}
      </main>

      {/* Bulk Action Bar */}
      {(selectedMangaIds.length > 0 || isFolderPlusEnabled) && (
        <div className="fixed bottom-4 sm:bottom-6 left-2 right-2 sm:left-1/2 sm:right-auto sm:w-auto sm:transform sm:-translate-x-1/2 z-40 animate-in slide-in-from-bottom-4 duration-200">
          <div className="bg-[#1a1a1a] border border-gray-700/50 shadow-2xl rounded-xl px-3 sm:px-6 py-2 sm:py-3 flex flex-wrap sm:flex-nowrap items-center justify-between sm:justify-start gap-2 sm:gap-4 w-full">
            <div className="flex flex-col flex-shrink-0">
              <span className="text-xs sm:text-sm font-bold text-white">
                {(() => {
                  const selectedFolders = selectedMangaIds.filter(id => mangas.find(m => m.id === id)?.is_folder).length;
                  const selectedMangas = selectedMangaIds.length - selectedFolders;
                  const parts = [];
                  if (selectedMangas > 0) parts.push(`${selectedMangas} manga${selectedMangas !== 1 ? 's' : ''}`);
                  if (selectedFolders > 0) parts.push(`${selectedFolders} carpeta${selectedFolders !== 1 ? 's' : ''}`);
                  return parts.length > 0 ? parts.join(' y ') + ' seleccionad' + (selectedFolders > 0 && selectedMangas === 0 ? 'as' : 'os') : '0 seleccionados';
                })()}
              </span>
              <button 
                onClick={handleSelectAll} 
                className="text-[10px] sm:text-xs text-[#bb86fc] hover:text-white transition-colors text-left mt-0.5 underline decoration-[#bb86fc]/30 underline-offset-2"
              >
                Seleccionar todo
              </button>
            </div>
            <div className="hidden sm:block h-8 w-px bg-gray-700"></div>
            
            <div className="flex flex-wrap sm:flex-nowrap items-center gap-1.5 sm:gap-2">
              {isFolderPlusEnabled ? (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowMoveToFolderModal(true)}
                    disabled={selectedMangaIds.length === 0}
                    className={`bg-blue-600 hover:bg-blue-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-blue-500/20 transition-all transform ${selectedMangaIds.length === 0 ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'}`}
                  >
                    Mover a Carpeta
                  </button>
                    <button
                      onClick={() => setShowCreateFolderModal(true)}
                      className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-indigo-500/20 transition-all transform hover:scale-105 active:scale-95"
                    >
                      Crear Carpeta
                    </button>
                </div>
              ) : isPortalPlusEnabled ? (
                <button
                  onClick={() => setShowMoveSectionModal(true)}
                  className="bg-indigo-600 hover:bg-indigo-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-indigo-500/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <ExternalLink className="w-4 h-4" />
                  Mover de Sección
                </button>
              ) : isCategoryPlusEnabled ? (
                <button
                  onClick={() => setShowBulkModal(true)}
                  className="bg-[#bb86fc] hover:bg-[#9966dd] text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-purple-500/20 transition-all transform hover:scale-105 active:scale-95"
                >
                  Aplicar Categorías
                </button>
              ) : isEtiquetadoraEnabled ? (
                <button
                  onClick={() => setShowEtiquetadoraModal(true)}
                  className="bg-[#bb86fc] hover:bg-[#9966dd] text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-[#bb86fc]/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <Tag className="w-4 h-4"/>
                  Etiquetar
                </button>
              ) : isCategoryMinusEnabled ? (
                <button
                  onClick={() => setShowBulkRemoveModal(true)}
                  className="bg-orange-500 hover:bg-orange-600 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-orange-500/20 transition-all transform hover:scale-105 active:scale-95"
                >
                  Remover Categorías
                </button>
              ) : isEditTitlePlusEnabled ? (
                <button
                  onClick={() => setShowBulkEditTitleModal(true)}
                  className="bg-pink-500 hover:bg-pink-600 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-pink-500/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <Edit3 className="w-4 h-4"/>
                  Editar Nombres
                </button>
              ) : isCopyIdsEnabled ? (
                <button
                  onClick={() => {
                    const mangasOnly = selectedMangaIds.filter(id => !mangas.find(m => m.id === id)?.is_folder);
                    navigator.clipboard.writeText(mangasOnly.join(', '));
                    toast.success(`Se copiaron ${mangasOnly.length} IDs`);
                    setSelectedMangaIds([]);
                  }}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-blue-500/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <Copy className="w-4 h-4"/>
                  Copiar IDs
                </button>
              ) : isDeletePlusEnabled ? (
                <button
                  onClick={async () => {
                   if (window.confirm(`¿Seguro que quieres eliminar ${selectedMangaIds.length} elementos?`)) {
                     try {
                        for (const id of selectedMangaIds) {
                            await deleteManga(id);
                        }
                        toast.success(`Se eliminaron ${selectedMangaIds.length} elementos.`);
                        setSelectedMangaIds([]);
                        loadMangas();
                     } catch (error) {
                         toast.error('Error al eliminar');
                     }
                   }
                  }}
                  className="bg-red-600 hover:bg-red-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-red-500/20 transition-all transform hover:scale-105 active:scale-95"
                >
                  Eliminar Selección
                </button>
              ) : isMergePlusEnabled ? (
                <button
                  onClick={async () => {
                    const idsToMerge = selectedMangaIds.filter(id => !mangas.find(m => m.id === id)?.is_folder);
                    if (idsToMerge.length < 2) {
                        toast.error("Debes seleccionar al menos 2 mangas para unirlos (las carpetas son ignoradas).");
                        return;
                    }
                    if (window.confirm(`¿Seguro que quieres unir ${idsToMerge.length} mangas en uno solo? Los originales serán eliminados.`)) {
                      try {
                        await mergeMangas(idsToMerge);
                        toast.success(`Se fusionaron ${idsToMerge.length} mangas correctamente.`);
                        setSelectedMangaIds([]);
                        loadMangas();
                      } catch (err) {
                        toast.error('Error al unir mangas');
                      }
                    }
                  }}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-emerald-500/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <Link className="w-4 h-4" />
                  Unir Mangas
                </button>
              ) : isTransferPlusEnabled ? (
                <button
                  onClick={() => {
                      const validMangas = selectedMangaIds.filter(id => !mangas.find(m => m.id === id)?.is_folder);
                      if (validMangas.length !== 2) {
                          toast.error("Debes seleccionar exactamente 2 mangas para transferir páginas.");
                          return;
                      }
                      setShowTransferPagesModal(true);
                  }}
                  className={`bg-amber-600 hover:bg-amber-700 text-white px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg text-xs sm:text-sm font-bold shadow-lg shadow-amber-500/20 transition-all transform flex items-center gap-2 ${selectedMangaIds.filter(id => !mangas.find(m => m.id === id)?.is_folder).length !== 2 ? 'opacity-50 cursor-not-allowed' : 'hover:scale-105 active:scale-95'}`}
                >
                  <Layers className="w-4 h-4" />
                  Transferir Páginas
                </button>
              ) : null}
              {selectedMangaIds.length > 0 && (
                <button
                  onClick={() => setSelectedMangaIds([])}
                  className="text-gray-400 hover:text-white text-xs sm:text-sm font-semibold transition-colors px-1 sm:px-2"
                >
                  Cancelar
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <GlobalFooter 
        isAdmin={isAdmin}
        onOpenTrash={() => setShowTrashModal(true)}
      />

      <NewMangaModal
        currentSection={currentSection}
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setEditingManga(null);
        }}
        editingManga={editingManga}
        onMangaCreated={(mangaId) => {
          loadMangas();
          setEditingManga(null);
          if (mangaId && !editingManga) {
            setTimeout(() => {
              handleSelectComic(mangaId);
            }, 500);
          }
        }}
        onDelete={isAdmin ? handleDeleteManga : undefined}
      />

      <BulkCategoryModal
        isOpen={showBulkModal}
        onClose={() => setShowBulkModal(false)}
        selectedMangaIds={selectedMangaIds}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />

      <BulkRemoveCategoryModal
        isOpen={showBulkRemoveModal}
        onClose={() => setShowBulkRemoveModal(false)}
        selectedMangaIds={selectedMangaIds}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />

      <BulkEditTitleModal
        isOpen={showBulkEditTitleModal}
        onClose={() => setShowBulkEditTitleModal(false)}
        mangas={mangas}
        selectedMangaIds={selectedMangaIds}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />

      <EtiquetadoraModal
        isOpen={showEtiquetadoraModal}
        onClose={() => setShowEtiquetadoraModal(false)}
        selectedMangaIds={selectedMangaIds}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />
      <CreateFolderModal
        isOpen={showCreateFolderModal}
        onClose={() => setShowCreateFolderModal(false)}
        selectedMangaIds={selectedMangaIds}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
        currentFolderId={currentFolderId}
        currentSection={currentSection}
      />
      <MoveToFolderModal
        isOpen={showMoveToFolderModal}
        onClose={() => setShowMoveToFolderModal(false)}
        selectedMangaIds={selectedMangaIds}
        mangas={sectionMangas}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />
      <MoveSectionModal
        isOpen={showMoveSectionModal}
        onClose={() => setShowMoveSectionModal(false)}
        selectedMangaIds={selectedMangaIds}
        currentSection={currentSection}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />

      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        isAdmin={isAdmin}
        onAdminChange={setIsAdmin}
        isCategoryPlusEnabled={isCategoryPlusEnabled}
        onCategoryPlusChange={setIsCategoryPlusEnabled}
        isCopyIdsEnabled={isCopyIdsEnabled}
        onCopyIdsChange={setIsCopyIdsEnabled}
        isDeletePlusEnabled={isDeletePlusEnabled}
        onDeletePlusChange={setIsDeletePlusEnabled}
        isCategoryMinusEnabled={isCategoryMinusEnabled}
        onCategoryMinusChange={setIsCategoryMinusEnabled}
        isEditTitlePlusEnabled={isEditTitlePlusEnabled}
        onEditTitlePlusChange={setIsEditTitlePlusEnabled}
        isEtiquetadoraEnabled={isEtiquetadoraEnabled}
        onEtiquetadoraChange={setIsEtiquetadoraEnabled}
        isFolderPlusEnabled={isFolderPlusEnabled}
        onFolderPlusChange={(enabled) => {
          setIsFolderPlusEnabled(enabled);
          if (!enabled) setSelectedMangaIds([]);
        }}
        isPortalPlusEnabled={isPortalPlusEnabled}
        onPortalPlusChange={(enabled) => {
          setIsPortalPlusEnabled(enabled);
          if (!enabled) setSelectedMangaIds([]);
        }}
        isMergePlusEnabled={isMergePlusEnabled}
        onMergePlusChange={(enabled) => {
          setIsMergePlusEnabled(enabled);
          if (!enabled) setSelectedMangaIds([]);
        }}
        isTransferPlusEnabled={isTransferPlusEnabled}
        onTransferPlusChange={(enabled) => {
          setIsTransferPlusEnabled(enabled);
          if (!enabled) setSelectedMangaIds([]);
        }}
        isFolderAnimationEnabled={isFolderAnimationEnabled}
        onFolderAnimationChange={setIsFolderAnimationEnabled}
        onOpenTitleManager={() => setShowTitleManagerModal(true)}
        onOpenFolderMap={() => setShowFolderMapModal(true)}
        onCleanKemonoTitles={() => setShowKemonoCleanConfirm(true)}
      />

      <TitleManagerModal
        isOpen={showTitleManagerModal}
        onClose={() => setShowTitleManagerModal(false)}
        mangas={mangas}
        onSaveComplete={() => loadMangas()}
      />

      <CategoryFilterModal
        isOpen={showFilterModal}
        onClose={() => setShowFilterModal(false)}
        categories={allCategories}
        selectedCategories={selectedCategories}
        onToggleCategory={handleSelectCategory}
        onClearFilters={() => {
          setSelectedCategories([]);
          setFilterDecensored(false);
          setFilterBN(false);
          setFilterColor(false);
          handleBackToHome();
        }}
        filterDecensored={filterDecensored}
        setFilterDecensored={(val) => { setFilterDecensored(val); handleBackToHome(); }}
        filterBN={filterBN}
        setFilterBN={(val) => { setFilterBN(val); handleBackToHome(); }}
        filterColor={filterColor}
        setFilterColor={(val) => { setFilterColor(val); handleBackToHome(); }}
      />
      <FolderMentalMapModal
        isOpen={showFolderMapModal}
        onClose={() => setShowFolderMapModal(false)}
        mangas={sectionMangas}
      />

      <ConfirmModal
        isOpen={showKemonoCleanConfirm}
        onClose={() => setShowKemonoCleanConfirm(false)}
        onConfirm={handleCleanKemonoTitles}
        title="Limpiar IDs de Kemono"
        message="¿Seguro que quieres eliminar las etiquetas [Numeros] del final de todos los mangas y carpetas? Esta acción se aplicará automáticamente a toda la base de datos."
        confirmText="Sí, limpiar nombres"
        cancelText="Cancelar"
        variant="warning"
      />

      <TrashModal
        isOpen={showTrashModal}
        onClose={() => setShowTrashModal(false)}
        deletedMangas={deletedMangas}
        onRestore={async (id) => {
          await restoreManga(id);
          await loadMangas();
        }}
        onPermanentDelete={async (id) => {
          await permanentDeleteManga(id);
          await loadMangas();
        }}
      />

      <TransferPagesModal
        isOpen={showTransferPagesModal}
        onClose={() => {
          setShowTransferPagesModal(false);
          setSelectedMangaIds([]);
        }}
        mangaIds={selectedMangaIds.filter(id => !mangas.find(m => m.id === id)?.is_folder).slice(0, 2)}
        onSaveComplete={() => {
          loadMangas();
          setSelectedMangaIds([]);
        }}
      />

      <Toaster position="top-center" richColors theme="dark" />
    </div>
  );
}

export default App;

