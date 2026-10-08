
import { Plus, Settings, Layers, User, Copy } from 'lucide-react';
import { useState, useEffect, useMemo } from 'react';
import { HDComicViewer } from './components/HDComicViewer';
import { NewMangaModal } from './components/NewMangaModal';
import { SettingsModal } from './components/SettingsModal';
import { AnnouncementBanner } from './components/AnnouncementBanner';
import { ComicDetail } from './components/ComicDetail';
import { ChapterReader } from './components/ChapterReader';
import { InfoPage } from './components/InfoPage';
import { BulkCategoryModal } from './components/BulkCategoryModal';
import { CategoryFilterModal } from './components/CategoryFilterModal';
import { Category } from './types/manga';

import { SearchBar } from './components/SearchBar';
import { SearchResults } from './components/SearchResults';
import { Toaster, toast } from 'sonner';
import { getAllMangas, deleteManga } from './services/manga';
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
  const [selectedMangaIds, setSelectedMangaIds] = useState<string[]>([]);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [selectedComicId, setSelectedComicId] = useState<string | null>(null);
  const [navigationHistory, setNavigationHistory] = useState<string[]>([]);
  const [selectedChapter, setSelectedChapter] = useState<{ manga: Manga; chapter: Chapter } | null>(null);
  const [mangas, setMangas] = useState<Manga[]>([]);
  const [showHD, setShowHD] = useState(false);
  const [showInfo, setShowInfo] = useState(false);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);
  const [sortType, setSortType] = useState<SortType>(() =>
    (localStorage.getItem('sortType') as SortType) || 'modified'
  );
  const [sortDirection, setSortDirection] = useState<SortDirection>(() =>
    (localStorage.getItem('sortDirection') as SortDirection) || 'desc'
  );

  useEffect(() => {
    // Check for admin mode via URL query parameter
    const searchParams = new URLSearchParams(window.location.search);
    const isAdminMode = searchParams.get('admin') === 'true';
    setIsAdmin(isAdminMode);
  }, []);

  useEffect(() => {
    localStorage.setItem('sortType', sortType);
  }, [sortType]);

  useEffect(() => {
    localStorage.setItem('sortDirection', sortDirection);
  }, [sortDirection]);

  useEffect(() => {
    // Initialize Telegram Web App
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
      } else if (hash === 'info') {
        setShowInfo(true);
        setSelectedComicId(null);
        setSelectedChapter(null);
      }
    };

    window.addEventListener('hashchange', handleHashChange);
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  useEffect(() => {
    if (!isCategoryPlusEnabled && !isCopyIdsEnabled) {
      setSelectedMangaIds([]);
    }
  }, [isCategoryPlusEnabled, isCopyIdsEnabled]);

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

  const allCategories = useMemo(() => {
    const categoriesMap = new Map<string, Category>();
    mangas.forEach(manga => {
      manga.categories?.forEach(cat => {
        if (!categoriesMap.has(cat.id)) {
          categoriesMap.set(cat.id, cat);
        }
      });
    });
    return Array.from(categoriesMap.values());
  }, [mangas]);

  const searchResult = useMemo(() => {
    if (!searchTerm.trim()) {
      return { items: mangas, query: '', resultCount: mangas.length };
    }
    return searchItems(
      mangas.map(m => ({
        id: m.id,
        title: m.title,
        author: m.author,
        categories: m.categories ? m.categories.map(c => c.name) : []
      })),
      searchTerm,
      { fuzzyMatch: true, minChars: 1 }
    );
  }, [mangas, searchTerm]);

  const filteredMangas = useMemo(() => {
    let items = searchResult.items.length > 0
      ? searchResult.items.map(item => mangas.find(m => m.id === item.id)).filter(Boolean) as Manga[]
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

    const sorted = [...items];

    if (sortType === 'random') {
      return sorted.sort(() => Math.random() - 0.5);
    }

    sorted.sort((a, b) => {
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

    return sorted;
  }, [mangas, searchTerm, searchResult.items, sortType, sortDirection, selectedCategories, selectedAuthors]);

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

  const toggleSelectManga = (id: string, forceSelect?: boolean) => {
    setSelectedMangaIds(prev => {
      const isSelected = prev.includes(id);
      const shouldSelect = forceSelect !== undefined ? forceSelect : !isSelected;
      if (shouldSelect) {
        return isSelected ? prev : [...prev, id];
      } else {
        return prev.filter(mId => mId !== id);
      }
    });
  };

  const handleSelectComic = (mangaId: string) => {
    if (isCategoryPlusEnabled || isCopyIdsEnabled) {
      toggleSelectManga(mangaId);
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
    if (selectedComicId) {
      setNavigationHistory([...navigationHistory, selectedComicId]);
    }
    window.location.hash = `manga / ${newMangaId} `;
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
            window.history.back();
            // Fallback if history back doesn't work or we want explicit control:
            // window.location.hash = `manga / ${ selectedComicId } `;
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
            window.location.hash = `manga / ${previousId} `;
            setSelectedComicId(previousId);
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
          <div className="flex items-center gap-1 sm:gap-1.5 group cursor-pointer">
            <img
              src="/icons/icones.png"
              alt="Twisted Brody Logo"
              className="w-10 h-10 sm:w-14 sm:h-14 object-contain transition-all duration-300 group-hover:rotate-12 group-hover:scale-110"
            />
            <h1 className="text-lg sm:text-2xl font-bold text-white transition-colors duration-300 group-hover:text-[#bb86fc]">
              Twisted Brody MangaFlow
            </h1>
          </div>
          <div className="flex items-center gap-1.5 sm:gap-3">
            {(isCategoryPlusEnabled || isCopyIdsEnabled) && (
              <div className="hidden sm:flex items-center gap-2 mr-2 px-3 py-1.5 bg-purple-500/10 rounded-lg border border-purple-500/20">
                <Layers className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-semibold text-purple-300">
                  {isCopyIdsEnabled ? 'Modo Copiar Activo' : 'Modo Plus Activo'}
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
                  className="bg-gray-800 hover:bg-gray-700 active:scale-95 text-white px-2 py-2 sm:px-4 sm:py-2.5 rounded-lg flex items-center gap-1.5 sm:gap-2 font-semibold transition-all duration-300 border border-gray-700/50 hover:border-gray-600 text-xs sm:text-sm hover:scale-110 hover:shadow-lg hover:shadow-700/50"
                  title="Ajustes y Admin"
                >
                  <Settings className="w-4 h-4 sm:w-5 sm:h-5 transition-transform duration-300 hover:rotate-180" />
                  <span className="hidden sm:inline">Ajustes</span>
                </button>
                <button
                  onClick={() => setShowModal(true)}
                  className="bg-purple-600 hover:bg-purple-700 active:scale-95 text-white px-2 py-2 sm:px-4 sm:py-2.5 rounded-lg flex items-center gap-1.5 sm:gap-2 font-semibold transition-all duration-300 shadow-lg shadow-purple-600/30 hover:shadow-purple-600/50 text-xs sm:text-sm hover:scale-110"
                >
                  <Plus className="w-4 h-4 sm:w-5 sm:h-5 transition-transform duration-300 hover:rotate-180" />
                  <span className="hidden sm:inline">Nuevo Manga</span>
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 sm:px-6 md:px-12 py-8">
        <AnnouncementBanner isAdmin={isAdmin} />

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

          {(selectedCategories.length > 0 || selectedAuthors.length > 0) && (
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
              {(selectedCategories.length > 0 || selectedAuthors.length > 0) && (
                <button
                  onClick={() => {
                    setSelectedCategories([]);
                    setSelectedAuthors([]);
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
          {false ? (
            <div className="hidden"></div>
          ) : (
            <>
              <link rel="preconnect" href="https://i.ibb.co" />
              <SearchResults
                items={mangaItems}
                searchTerm={searchTerm}
                isSearching={false}
                isLoading={loading}
                onSelectComic={handleSelectComic}
                onEditManga={isAdmin ? handleEditManga : undefined}
                onDeleteManga={isAdmin ? handleDeleteManga : undefined}
                isCategoryPlusEnabled={isCategoryPlusEnabled || isCopyIdsEnabled}
                selectedMangaIds={selectedMangaIds}
                onToggleSelectManga={toggleSelectManga}
              />
            </>
          )}
        </div>
      </main>

      {/* Bulk Action Bar */}
      {(isCategoryPlusEnabled || isCopyIdsEnabled) && selectedMangaIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-40 animate-in slide-in-from-bottom-4 duration-200">
          <div className="bg-[#1a1a1a] border border-gray-700/50 shadow-2xl rounded-xl px-6 py-3 flex items-center gap-4">
            <div className="flex flex-col">
              <span className="text-sm font-bold text-white">{selectedMangaIds.length} seleccionados</span>
              <span className="text-xs text-gray-400">Listos para acción</span>
            </div>
            <div className="h-8 w-px bg-gray-700"></div>
            <button
              onClick={() => setSelectedMangaIds([])}
              className="text-gray-400 hover:text-white text-sm font-semibold transition-colors"
            >
              Cancelar
            </button>
            <div className="flex gap-2">
              {isCategoryPlusEnabled && (
                <button
                  onClick={() => setShowBulkModal(true)}
                  className="bg-[#bb86fc] hover:bg-[#9966dd] text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg shadow-purple-500/20 transition-all transform hover:scale-105 active:scale-95"
                >
                  Aplicar Categorías
                </button>
              )}
              {isCopyIdsEnabled && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(selectedMangaIds.join(', '));
                    toast.success('IDs copiados al portapapeles');
                    setSelectedMangaIds([]);
                  }}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm font-bold shadow-lg shadow-blue-500/20 transition-all transform hover:scale-105 active:scale-95 flex items-center gap-2"
                >
                  <Copy className="w-4 h-4"/>
                  Copiar IDs
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      <GlobalFooter />

      <NewMangaModal
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

      <SettingsModal
        isOpen={showSettingsModal}
        onClose={() => setShowSettingsModal(false)}
        isAdmin={isAdmin}
        onAdminChange={setIsAdmin}
        isCategoryPlusEnabled={isCategoryPlusEnabled}
        onCategoryPlusChange={setIsCategoryPlusEnabled}
        isCopyIdsEnabled={isCopyIdsEnabled}
        onCopyIdsChange={setIsCopyIdsEnabled}
      />

      <CategoryFilterModal
        isOpen={showFilterModal}
        onClose={() => setShowFilterModal(false)}
        categories={allCategories}
        selectedCategories={selectedCategories}
        onToggleCategory={handleSelectCategory}
        onClearFilters={() => setSelectedCategories([])}
      />
      <Toaster position="top-center" richColors theme="dark" />
    </div>
  );
}

export default App;

