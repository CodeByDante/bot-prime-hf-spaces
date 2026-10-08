
import { ArrowLeft, Rows, Grid2X2, Grid3X3, ZoomIn, ZoomOut, RotateCcw, Heart } from 'lucide-react';
import { useState } from 'react';
import { Manga } from '../types/manga';
import { ImageLoader } from './ImageLoader';
import { ImageLightbox } from './ImageLightbox';
import { GlobalFooter } from './GlobalFooter';
import { LazyImageWrapper } from './LazyImageWrapper';
import { addFavorite, removeFavorite, isFavorite } from '../utils/favorites';


interface HDComicViewerProps {
  manga: Manga;
  onBack: () => void;
  isAdmin?: boolean;
}

export function HDComicViewer({ manga, onBack, isAdmin = false }: HDComicViewerProps) {
  // Assuming the first chapter contains the full comic pages for "Graphic Novels" / "Doujins" style
  // If there are multiple chapters, we might default to the first one or need a selector.
  // Given the context of "Ver HD" implies seeing the "book" in full quality.
  const chapter = manga.chapters && manga.chapters.length > 0 ? manga.chapters[0] : null;
  const pages = chapter ? (chapter.original_pages && chapter.original_pages.length > 0 ? chapter.original_pages : chapter.pages) : [];

  const [viewMode, setViewMode] = useState<'vertical' | 'gallery' | 'grid'>('vertical');
  const [zoomLevel, setZoomLevel] = useState(1); // 1 = 100%
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  const [favRefresh, setFavRefresh] = useState(0);

  const toggleFavorite = (e: React.MouseEvent, pageUrl: string, index: number) => {
    e.stopPropagation();
    if (!manga) return;
    const favId = `${manga.id}_${index}`;
    if (isFavorite(manga.id, index)) {
      removeFavorite(favId);
    } else {
      addFavorite({
        mangaId: manga.id,
        mangaTitle: manga.title,
        pageUrl,
        pageIndex: index
      });
    }
    setFavRefresh(prev => prev + 1);
  };

  if (!pages || pages.length === 0) {
    return (
      <div className="min-h-screen bg-[#121212] flex flex-col items-center justify-center">
        <button
          onClick={onBack}
          className="absolute top-6 left-6 p-2 hover:bg-[#333] rounded-lg transition-colors text-white"
        >
          <ArrowLeft className="w-6 h-6" />
        </button>
        <div className="text-gray-400 text-lg">No hay páginas disponibles</div>
      </div>
    );
  }

  const handleZoomIn = () => setZoomLevel(prev => Math.min(prev + 0.25, 3));
  const handleZoomOut = () => setZoomLevel(prev => Math.max(prev - 0.25, 0.5));
  const handleResetZoom = () => setZoomLevel(1);

  return (
    <div className="min-h-screen flex flex-col bg-[#121212]">
      {/* Sticky Header */}
      <header className="sticky top-0 z-50 bg-[#121212]/90 backdrop-blur-md border-b border-gray-800 px-4 py-3 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 flex-shrink-0">
          <button
            onClick={onBack}
            className="p-2 hover:bg-[#333] rounded-lg transition-colors text-white flex items-center gap-2"
          >
            <ArrowLeft className="w-5 h-5" />
            <span className="font-semibold text-sm hidden sm:inline">Volver</span>
          </button>
        </div>

        <div className="flex-1 flex justify-center min-w-0">
          <h1 className="text-white font-bold truncate text-center max-w-full">
            {manga.title} <span className="text-[#bb86fc] text-xs ml-2 border border-[#bb86fc] px-1 rounded">HD</span>
          </h1>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          {/* View Modes */}
          <div className="flex items-center gap-1 bg-[#0a0a0a] border border-gray-800 rounded-lg p-1 hidden md:flex">
            <button
              onClick={() => setViewMode('vertical')}
              className={`p-2 rounded-md transition-all duration-200 ${viewMode === 'vertical' ? 'bg-[#bb86fc] text-white' : 'text-gray-400 hover:text-white'}`}
              title="Vertical"
            >
              <Rows className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('gallery')}
              className={`p-2 rounded-md transition-all duration-200 ${viewMode === 'gallery' ? 'bg-[#bb86fc] text-white' : 'text-gray-400 hover:text-white'}`}
              title="Galería"
            >
              <Grid2X2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={`p-2 rounded-md transition-all duration-200 ${viewMode === 'grid' ? 'bg-[#bb86fc] text-white' : 'text-gray-400 hover:text-white'}`}
              title="Cuadrícula"
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
          </div>

          {/* Zoom Controls (Only for Vertical) */}
          {viewMode === 'vertical' && (
            <div className="flex items-center gap-1 bg-[#0a0a0a] border border-gray-800 rounded-lg p-1">
              <button onClick={handleZoomOut} className="p-2 text-gray-400 hover:text-white hover:bg-[#333] rounded"><ZoomOut className="w-4 h-4" /></button>
              <span className="text-xs text-gray-300 w-8 text-center">{Math.round(zoomLevel * 100)}%</span>
              <button onClick={handleZoomIn} className="p-2 text-gray-400 hover:text-white hover:bg-[#333] rounded"><ZoomIn className="w-4 h-4" /></button>
              <button onClick={handleResetZoom} className="p-2 text-gray-400 hover:text-white hover:bg-[#333] rounded" title="Reset"><RotateCcw className="w-3 h-3" /></button>
            </div>
          )}
        </div>
      </header>

      {/* Mobile View Mode Selector (if screen is small) */}
      <div className="md:hidden px-4 py-2 border-b border-gray-800 bg-[#121212] flex justify-center">
        <div className="flex items-center gap-1 bg-[#0a0a0a] border border-gray-800 rounded-lg p-1">
          <button
            onClick={() => setViewMode('vertical')}
            className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-xs font-medium ${viewMode === 'vertical' ? 'bg-[#bb86fc] text-white' : 'text-gray-400'}`}
          >
            <Rows className="w-3 h-3" /> Vertical
          </button>
          <button
            onClick={() => setViewMode('gallery')}
            className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-xs font-medium ${viewMode === 'gallery' ? 'bg-[#bb86fc] text-white' : 'text-gray-400'}`}
          >
            <Grid2X2 className="w-3 h-3" /> Galería
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`px-3 py-1.5 rounded-md flex items-center gap-2 text-xs font-medium ${viewMode === 'grid' ? 'bg-[#bb86fc] text-white' : 'text-gray-400'}`}
          >
            <Grid3X3 className="w-3 h-3" /> Cuadrícula
          </button>
        </div>
      </div>

      <main className="flex-1 w-full max-w-[1920px] mx-auto px-0 sm:px-4 py-0 sm:py-6">
        <div className={`
             bg-[#050505] min-h-screen transition-all duration-150 ease-out
             ${viewMode === 'vertical' ? 'flex flex-col items-center gap-0 sm:gap-1' : ''}
             ${viewMode === 'gallery' ? 'masonry-container p-2' : ''}
             ${viewMode === 'grid' ? 'grid grid-cols-3 md:grid-cols-5 gap-2 p-2' : ''}
        `}>
          {pages.map((pageUrl, index) => {
            // Use the direct URL to avoid proxy issues, matching ComicDetail behavior.
            const src = pageUrl;

            if (viewMode === 'vertical') {
              // Calculate width style based on zoom
              // Default max-w-5xl is roughly 64rem (1024px).
              // We can apply transform or width. Width is safer for layout flow.
              // Let's use inline style for width percentage relative to "normal" max-width, or just set max-width.
              // Actually, simpler: Wrapper width.
              // Better approach: Control the wrapper width directly.
              return (
                <div key={index} className="relative transition-all duration-200" style={{ width: zoomLevel === 1 ? '100%' : `${100 * zoomLevel}%`, maxWidth: zoomLevel > 1 ? 'none' : '80rem' }}>
                  <div className={`mx-auto ${zoomLevel <= 1 ? 'max-w-5xl' : ''}`}>
                    <LazyImageWrapper minHeight="50vh">
                      {() => (
                        <ImageLoader
                          src={src}
                          alt={`Página ${index + 1}`}
                          aspectRatio="auto"
                          objectFit="contain"
                          loading="eager"
                          className="w-full h-auto"
                          imgClassName="w-full h-auto block"
                          showControls={true}
                        />
                      )}
                    </LazyImageWrapper>
                    {isAdmin && (
                      <button
                        onClick={(e) => toggleFavorite(e, src, index)}
                        className={`absolute top-4 right-4 p-3 rounded-full transition-all duration-200 z-[40] ${isFavorite(manga.id, index) ? 'bg-[#ff4b4b]/20 text-[#ff4b4b]' : 'bg-black/50 text-white hover:bg-[#ff4b4b]/20 hover:text-[#ff4b4b]'}`}
                        title={isFavorite(manga.id, index) ? "Quitar de favoritos" : "Añadir a favoritos"}
                      >
                        <Heart className="w-6 h-6" fill={isFavorite(manga.id, index) ? "currentColor" : "none"} />
                      </button>
                    )}
                  </div>
                </div>
              );
            }

            // Gallery / Grid
            return (
              <div
                key={index}
                className={`
                    group cursor-pointer relative bg-black rounded-lg shadow-lg overflow-hidden transition-transform duration-300 hover:scale-[1.02]
                    ${viewMode === 'gallery' ? 'masonry-item' : ''}
                 `}
                onClick={() => {
                  setLightboxIndex(index);
                  setLightboxOpen(true);
                }}
              >
                <ImageLoader
                  src={src}
                  alt={`Página ${index + 1}`}
                  aspectRatio={viewMode === 'grid' ? '1/1' : 'auto'}
                  objectFit={viewMode === 'grid' ? 'cover' : 'contain'}
                  loading={index < 5 ? "eager" : "lazy"}
                  className="w-full h-auto rounded-lg"
                  imgClassName="group-hover:scale-110"
                />
                {isAdmin && (
                  <button
                    onClick={(e) => toggleFavorite(e, src, index)}
                    className={`absolute top-2 right-2 p-2 rounded-full transition-all duration-200 z-10 ${isFavorite(manga.id, index) ? 'bg-[#ff4b4b]/20 text-[#ff4b4b]' : 'bg-black/50 text-white hover:bg-[#ff4b4b]/20 hover:text-[#ff4b4b]'}`}
                    title={isFavorite(manga.id, index) ? "Quitar de favoritos" : "Añadir a favoritos"}
                  >
                    <Heart className="w-4 h-4" fill={isFavorite(manga.id, index) ? "currentColor" : "none"} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </main>

      <GlobalFooter />

      {lightboxOpen && (
        <ImageLightbox
          images={pages} // Use direct URLs
          initialIndex={lightboxIndex}
          onClose={() => setLightboxOpen(false)}
          mangaId={manga.id}
          mangaTitle={manga.title}
          isAdmin={isAdmin}
        />
      )}
    </div>
  );
}
