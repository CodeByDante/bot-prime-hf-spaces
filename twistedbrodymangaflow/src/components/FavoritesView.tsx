import { useState, useEffect } from 'react';
import { Heart, Trash2, Loader2, Sparkles, Search } from 'lucide-react';
import { getFavorites, removeFavorite, FavoriteImage, subscribeFavorites } from '../utils/favorites';
import { getMangaById } from '../services/manga';
import { ImageLoader } from './ImageLoader';
import { ImageLightbox } from './ImageLightbox';

export function FavoritesView({ isAdmin = false }: { isAdmin?: boolean }) {
  const [favorites, setFavorites] = useState<FavoriteImage[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [lightboxImages, setLightboxImages] = useState<string[]>([]);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  const [hdUrls, setHdUrls] = useState<Record<string, string>>({}); // Key is fav.id
  const [isLoadingAllHD, setIsLoadingAllHD] = useState(false);

  const isAllHDLoaded = favorites.length > 0 && Object.keys(hdUrls).length === favorites.length;

  const handleToggleAllHD = async () => {
    if (Object.keys(hdUrls).length > 0) {
      // Toggle OFF all
      setHdUrls({});
      if (lightboxImages.length > 0) {
        setLightboxImages(favorites.map(f => f.pageUrl));
      }
      return;
    }

    // Toggle ON all
    setIsLoadingAllHD(true);
    const newHdUrls = { ...hdUrls };
    
    // Agrupar por mangaId para no hacer peticiones repetidas al mismo cómic
    const mangaGroups: Record<string, FavoriteImage[]> = {};
    for (const fav of favorites) {
      if (!newHdUrls[fav.id]) {
        if (!mangaGroups[fav.mangaId]) mangaGroups[fav.mangaId] = [];
        mangaGroups[fav.mangaId].push(fav);
      }
    }

    try {
      for (const mangaId of Object.keys(mangaGroups)) {
        const manga = await getMangaById(mangaId);
        if (manga && manga.chapters?.[0]?.original_pages) {
          for (const fav of mangaGroups[mangaId]) {
            const hdUrl = manga.chapters[0].original_pages[fav.pageIndex];
            if (hdUrl) {
              newHdUrls[fav.id] = hdUrl;
            }
          }
        }
      }
      setHdUrls(newHdUrls);
      
      // Si el lightbox está abierto, actualizarlo
      if (lightboxImages.length > 0) {
        setLightboxImages(favorites.map(f => newHdUrls[f.id] || f.pageUrl));
      }
    } catch (error) {
      console.error("Error loading all HD:", error);
    } finally {
      setIsLoadingAllHD(false);
    }
  };

  const handleRequestHD = async (index: number) => {
    const fav = favorites[index];
    if (!fav) return;

    // Si ya está en HD, lo desactivamos (Toggle OFF)
    if (hdUrls[fav.id]) {
      setHdUrls(prev => {
        const newHdUrls = { ...prev };
        delete newHdUrls[fav.id];
        return newHdUrls;
      });
      setLightboxImages(prev => {
        const newImages = [...prev];
        newImages[index] = fav.pageUrl;
        return newImages;
      });
      return;
    }

    try {
      const manga = await getMangaById(fav.mangaId);
      const hdUrl = manga?.chapters?.[0]?.original_pages?.[fav.pageIndex];
      
      if (hdUrl) {
        setHdUrls(prev => ({ ...prev, [fav.id]: hdUrl }));
        // Actualizamos las imágenes del lightbox para que el visor actualice la fuente
        setLightboxImages(prev => {
          const newImages = [...prev];
          newImages[index] = hdUrl;
          return newImages;
        });
      } else {
        console.warn('No hay versión HD para esta página');
      }
    } catch (e) {
      console.error("Error cargando versión HD", e);
    }
  };

  const sortFavorites = (favs: FavoriteImage[]) => {
    return favs.sort((a, b) => {
      // Ordenar por título del cómic alfabéticamente
      const titleCompare = a.mangaTitle.localeCompare(b.mangaTitle);
      if (titleCompare !== 0) return titleCompare;
      // Si es el mismo cómic, ordenar por número de página
      return a.pageIndex - b.pageIndex;
    });
  };

  useEffect(() => {
    setFavorites(sortFavorites(getFavorites()));
    const unsubscribe = subscribeFavorites(() => {
      setFavorites(sortFavorites(getFavorites()));
    });
    return unsubscribe;
  }, []);

  const handleRemove = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    if (!isAdmin) return;
    removeFavorite(id);
    setFavorites(sortFavorites(getFavorites()));
  };

  const filteredFavorites = favorites.filter(fav => 
    fav.mangaTitle.toLowerCase().includes(searchQuery.toLowerCase())
  );

  if (favorites.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-20 animate-in fade-in duration-300">
        <Heart className="w-16 h-16 text-gray-600 mb-4 animate-bounce" />
        <p className="text-gray-400 text-lg mb-2">No tienes páginas favoritas</p>
        <p className="text-gray-500 text-sm">Agrega tus páginas preferidas desde el lector de cómics.</p>
      </div>
    );
  }

  return (
    <div className="max-w-[1800px] mx-auto p-2 sm:p-4 animate-in fade-in duration-300">
      <div className="flex items-center justify-between gap-4 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <Heart className="w-5 h-5 sm:w-6 sm:h-6 text-[#ff4b4b] fill-[#ff4b4b]" />
          <h2 className="text-lg sm:text-xl font-bold text-white">Tus Páginas Favoritas</h2>
          <span className="text-gray-400 text-xs sm:text-sm ml-1">({favorites.length})</span>
        </div>

        {/* Search Bar */}
        {favorites.length > 0 && (
          <div className="w-full sm:w-auto flex-1 max-w-md order-3 sm:order-none mt-2 sm:mt-0">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Buscar por título de cómic..."
                className="w-full bg-[#1e1e1e] border border-gray-700/50 rounded-lg pl-9 pr-4 py-2 text-sm text-white placeholder:text-gray-500 focus:outline-none focus:border-[#bb86fc] transition-colors"
              />
            </div>
          </div>
        )}
        
        {favorites.length > 0 && (
          <button
            onClick={handleToggleAllHD}
            disabled={isLoadingAllHD}
            className={`flex items-center justify-center gap-2 px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg font-bold text-sm transition-all duration-300 shadow-lg whitespace-nowrap
              ${Object.keys(hdUrls).length > 0 
                ? 'bg-gradient-to-r from-[#bb86fc] to-[#9965f4] text-white shadow-[#bb86fc]/20 hover:shadow-[#bb86fc]/40' 
                : 'bg-white/10 text-gray-300 hover:bg-white/20 hover:text-white'
              }
              ${isLoadingAllHD ? 'opacity-70 cursor-not-allowed' : ''}
            `}
          >
            {isLoadingAllHD ? (
              <Loader2 className="w-4 h-4 animate-spin shrink-0" />
            ) : (
              <Sparkles className="w-4 h-4 shrink-0" />
            )}
            <span className="hidden sm:inline">Modo Full HD</span>
            <span className="sm:hidden">Full HD</span>
          </button>
        )}
      </div>

      {filteredFavorites.length === 0 && favorites.length > 0 ? (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <Search className="w-12 h-12 mb-4 opacity-20" />
          <p>No se encontraron páginas para "{searchQuery}"</p>
        </div>
      ) : (
        <div className="masonry-container">
          {filteredFavorites.map((fav, index) => (
            <div
            key={fav.id}
            className="masonry-item group relative bg-black rounded-lg shadow-lg overflow-hidden cursor-pointer"
            onClick={() => {
              setLightboxImages(filteredFavorites.map(f => hdUrls[f.id] || f.pageUrl));
              setLightboxIndex(index);
            }}
          >
            <ImageLoader
              src={hdUrls[fav.id] || fav.pageUrl}
              alt={`Favorito de ${fav.mangaTitle}`}
              aspectRatio="auto"
              objectFit="contain"
              className="rounded-lg transition-transform duration-300 group-hover:scale-[1.02] w-full"
            />
            
            {/* Overlay Info */}
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/0 to-black/0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex flex-col justify-end p-3 sm:p-4 pointer-events-none">
              <h3 className="text-white text-sm sm:text-base font-semibold truncate shadow-black drop-shadow-md">
                {fav.mangaTitle}
              </h3>
              <p className="text-gray-300 text-xs font-medium shadow-black drop-shadow-md">
                Página {fav.pageIndex + 1}
              </p>
            </div>

            {/* Remove Button */}
            {isAdmin && (
              <button
                onClick={(e) => handleRemove(e, fav.id)}
                className="absolute top-2 right-2 p-2 bg-black/60 hover:bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-all duration-200 transform translate-y-[-10px] group-hover:translate-y-0 pointer-events-auto"
                title="Quitar de favoritos"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    )}

      {lightboxImages.length > 0 && (
        <ImageLightbox
          images={lightboxImages}
          initialIndex={lightboxIndex}
          onClose={() => setLightboxImages([])}
          onRequestHD={handleRequestHD}
          isHDLoaded={(idx) => !!hdUrls[filteredFavorites[idx]?.id]}
          onNavigateToComic={(idx) => {
            const fav = filteredFavorites[idx];
            if (fav) window.location.hash = `#manga/${fav.mangaId}`;
          }}
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
}
