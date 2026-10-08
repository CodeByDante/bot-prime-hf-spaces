import { BookOpen, ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';
import { useState, useEffect } from 'react';
import { MangaCard } from './MangaCard';
import { MangaCardSkeleton } from './MangaCardSkeleton';
import { Manga } from '../types/manga';

interface SearchResult {
  id: string;
  title: string;
  author: string;
  chapterCount: number;
  pageCount: number;
  thumbnail?: string;
  manga?: Manga;
}

interface SearchResultsProps {
  items: SearchResult[];
  searchTerm: string;
  isSearching: boolean;
  onSelectComic: (id: string) => void;
  onEditManga?: (manga: Manga) => void;
  onDeleteManga?: (id: string) => void;
  isLoading?: boolean;
  isCategoryPlusEnabled?: boolean;
  selectedMangaIds?: string[];
  onToggleSelectManga?: (id: string, forceSelect?: boolean) => void;
  allMangas?: Manga[];
  isFolderAnimationEnabled?: boolean;
  currentSection?: 'flow' | 'patreon' | 'onlyfans' | 'grok';
}

const ITEMS_PER_PAGE = 24;

export function getAllFolderThumbnails(folderId: string, mangas: Manga[], visited = new Set<string>()): string[] {
  if (visited.has(folderId)) return [];
  visited.add(folderId);

  const children = mangas.filter(m => m.folder_id === folderId);
  const result: string[] = [];
  
  for (const child of children) {
    const image = child.cover_url || child.thumbnail_url;
    if (image && !result.includes(image)) {
      result.push(image);
    }
    if (child.is_folder) {
      const childThumbs = getAllFolderThumbnails(child.id, mangas, visited);
      for (const t of childThumbs) {
        if (!result.includes(t)) result.push(t);
      }
    }
  }
  return result;
}

export function getFolderThumbnails(folderId: string, mangas: Manga[], limit = 12): string[] {
  const children = mangas.filter(m => m.folder_id === folderId);
  const subFolders = children.filter(m => m.is_folder);
  const directMangas = children.filter(m => !m.is_folder && (m.cover_url || m.thumbnail_url));


  // Recolectar todas las secuencias de miniaturas por cada subcarpeta
  const subfolderThumbnails: string[][] = [];
  for (const sf of subFolders) {
    const sfThumbs = getAllFolderThumbnails(sf.id, mangas, new Set());
    if (sfThumbs.length > 0) {
      subfolderThumbnails.push(sfThumbs);
    }
  }

  if (directMangas.length > 0) {
    const directThumbs = directMangas.map(m => m.cover_url || m.thumbnail_url).filter(Boolean) as string[];
    if (directThumbs.length > 0) subfolderThumbnails.push(directThumbs);
  }

  // Intercalar (1 de A, 1 de B, 1 de C, 2 de A, 2 de B...)
  const result: string[] = [];
  let added = true;
  let index = 0;
  
  while (added && result.length < limit) {
    added = false;
    for (const sfThumbs of subfolderThumbnails) {
      if (result.length >= limit) break;
      if (index < sfThumbs.length) {
        if (!result.includes(sfThumbs[index])) {
          result.push(sfThumbs[index]);
          added = true;
        }
      }
    }
    index++;
  }

  return result;
}

export function SearchResults({
  items,
  searchTerm,
  isSearching,
  onSelectComic,
  onEditManga,
  onDeleteManga,
  isLoading = false,
  isCategoryPlusEnabled = false,
  selectedMangaIds = [],
  onToggleSelectManga,
  allMangas = [],
  isFolderAnimationEnabled = true,
  currentSection,
}: SearchResultsProps) {
  const [dragState, setDragState] = useState<{ isDragging: boolean, action: 'select' | 'deselect' | null, startId: string | null, hasDragged: boolean }>({ isDragging: false, action: null, startId: null, hasDragged: false });

  useEffect(() => {
    const handleMouseUp = () => {
      if (dragState.isDragging) {
        setDragState({ isDragging: false, action: null, startId: null, hasDragged: false });
      }
    };
    window.addEventListener('mouseup', handleMouseUp);
    return () => window.removeEventListener('mouseup', handleMouseUp);
  }, [dragState.isDragging]);

  const handleSetSelection = (id: string, select: boolean) => {
    if (onToggleSelectManga) {
      onToggleSelectManga(id, select);
    }
  };

  const handleMouseDown = (e: React.MouseEvent, id: string) => {
    if (e.button !== 0) return; // Only left click
    
    // Only allow drag selection if a tool is enabled or items are already selected
    if (!isCategoryPlusEnabled && selectedMangaIds.length === 0) return;
    
    const isCurrentlySelected = selectedMangaIds.includes(id);
    const action = isCurrentlySelected ? 'deselect' : 'select';
    setDragState({ isDragging: true, action, startId: id, hasDragged: false });
  };

  const handleMouseEnter = (id: string) => {
    if (!dragState.isDragging || !dragState.action) return;
    
    if (!dragState.hasDragged && dragState.startId) {
      // First drag movement over a new card
      handleSetSelection(dragState.startId, dragState.action === 'select');
      setDragState(prev => ({ ...prev, hasDragged: true }));
    }
    
    handleSetSelection(id, dragState.action === 'select');
  };

  const [currentPage, setCurrentPage] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    const page = params.get('page');
    return page ? Math.max(1, Number(page)) : 1;
  });

  // Listen for browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      const params = new URLSearchParams(window.location.search);
      const page = params.get('page');
      setCurrentPage(page ? Math.max(1, Number(page)) : 1);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  // Correct page if out of bounds (e.g. after filtering changes)
  const totalPages = Math.ceil(items.length / ITEMS_PER_PAGE);

  useEffect(() => {
    if (totalPages > 0 && currentPage > totalPages) {
      // Silent correction
      setCurrentPage(totalPages);
      const url = new URL(window.location.href);
      url.searchParams.set('page', String(totalPages));
      window.history.replaceState({}, '', url);
    }
  }, [totalPages, currentPage]);

  // Reset page ONLY when search term changes (not when items change due to sorting)
  useEffect(() => {
    if (searchTerm) {
      setCurrentPage(1);
      const url = new URL(window.location.href);
      url.searchParams.delete('page');
      window.history.replaceState({}, '', url);
    }
  }, [searchTerm]);

  // Get current items
  const currentItems = items.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  );

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    const url = new URL(window.location.href);
    url.searchParams.set('page', String(page));
    window.history.pushState({}, '', url);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const renderPagination = () => {
    if (totalPages <= 1) return null;

    const pages = [];
    // Logic to show a window of pages for better UX (e.g. 1 ... 4 5 6 ... 10)
    const showMax = 5;
    let startPage = Math.max(1, currentPage - Math.floor(showMax / 2));
    let endPage = Math.min(totalPages, startPage + showMax - 1);

    if (endPage - startPage + 1 < showMax) {
      startPage = Math.max(1, endPage - showMax + 1);
    }

    for (let i = startPage; i <= endPage; i++) {
      pages.push(i);
    }

    return (
      <div className="flex items-center justify-center gap-2 mt-8 flex-wrap">
        <button
          onClick={() => handlePageChange(1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg bg-[#1a1a1a] text-white hover:bg-[#bb86fc] disabled:opacity-50 disabled:hover:bg-[#1a1a1a] transition-colors"
          title="Primera página"
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>
        <button
          onClick={() => handlePageChange(currentPage - 1)}
          disabled={currentPage === 1}
          className="p-2 rounded-lg bg-[#1a1a1a] text-white hover:bg-[#bb86fc] disabled:opacity-50 disabled:hover:bg-[#1a1a1a] transition-colors"
          title="Anterior"
        >
          <ChevronLeft className="w-4 h-4" />
        </button>

        {startPage > 1 && (
          <span className="text-gray-500 px-1">...</span>
        )}

        {pages.map((page) => (
          <button
            key={page}
            onClick={() => handlePageChange(page)}
            className={`w-8 h-8 rounded-lg text-sm font-medium transition-colors ${currentPage === page
              ? 'bg-[#bb86fc] text-white'
              : 'bg-[#1a1a1a] text-gray-400 hover:bg-[#333] hover:text-white'
              }`}
          >
            {page}
          </button>
        ))}

        {endPage < totalPages && (
          <span className="text-gray-500 px-1">...</span>
        )}

        <button
          onClick={() => handlePageChange(currentPage + 1)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg bg-[#1a1a1a] text-white hover:bg-[#bb86fc] disabled:opacity-50 disabled:hover:bg-[#1a1a1a] transition-colors"
          title="Siguiente"
        >
          <ChevronRight className="w-4 h-4" />
        </button>
        <button
          onClick={() => handlePageChange(totalPages)}
          disabled={currentPage === totalPages}
          className="p-2 rounded-lg bg-[#1a1a1a] text-white hover:bg-[#bb86fc] disabled:opacity-50 disabled:hover:bg-[#1a1a1a] transition-colors"
          title="Última página"
        >
          <ChevronsRight className="w-4 h-4" />
        </button>
      </div>
    );
  };

  if (isSearching && searchTerm) {
    return (
      <div className="flex flex-col items-center justify-center py-16 animate-in fade-in duration-300">
        <div className="text-gray-400 text-sm animate-pulse">Buscando "{searchTerm}"...</div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-1.5 sm:gap-2 md:gap-3 justify-center items-start animate-in fade-in duration-300">
        {Array.from({ length: 12 }).map((_, index) => (
          <MangaCardSkeleton key={index} />
        ))}
      </div>
    );
  }
  if (searchTerm && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 animate-in fade-in duration-300">
        <BookOpen className="w-16 h-16 text-gray-600 mb-4 animate-bounce" />
        <p className="text-gray-400 text-lg mb-2">No se encontraron resultados</p>
        <p className="text-gray-500 text-sm">Intenta con otros términos de búsqueda</p>
      </div>
    );
  }

  if (!searchTerm && items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 animate-in fade-in duration-300">
        <BookOpen className="w-16 h-16 text-gray-600 mb-4 animate-bounce" />
        <p className="text-gray-400 text-lg mb-2">No hay mangas disponibles</p>
        <p className="text-gray-500 text-sm">Crea tu primer manga usando el botón "Nuevo"</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-1.5 sm:gap-2 md:gap-3 justify-center items-start">
        {currentItems.map((item) => (
          <div key={item.id}>
            <MangaCard
              id={item.id}
              title={item.title}
              author={item.author}
              pageCount={item.pageCount}
              thumbnail={item.thumbnail}
              manga={item.manga}
              onSelect={() => onSelectComic(item.id)}
              onEdit={onEditManga}
              onDelete={onDeleteManga ? () => onDeleteManga(item.id) : undefined}
              isCategoryPlusEnabled={isCategoryPlusEnabled}
              isSelected={selectedMangaIds.includes(item.id)}
              onMouseDown={(e) => handleMouseDown(e, item.id)}
              onMouseEnter={() => handleMouseEnter(item.id)}
              dragStateParams={dragState}
              hasAnySelection={selectedMangaIds.length > 0}
              onToggleSelect={() => handleSetSelection(item.id, !selectedMangaIds.includes(item.id))}
              folderItemCount={item.manga?.is_folder ? allMangas.filter(m => m.folder_id === item.id).length : undefined}
              folderThumbnails={item.manga?.is_folder ? getFolderThumbnails(item.id, allMangas) : undefined}
              hasSubfolders={item.manga?.is_folder ? allMangas.some(m => m.folder_id === item.id && m.is_folder) : false}
              isFolderAnimationEnabled={isFolderAnimationEnabled}
              currentSection={currentSection}
            />
          </div>
        ))}
      </div>

      {renderPagination()}
    </div>
  );
}
