import { useState, useEffect, useRef } from 'react';
import { Heart, ExternalLink, BookOpen, Book, ZoomOut, ZoomIn, X, ChevronLeft, ChevronRight } from 'lucide-react';
import { ImageLoader } from './ImageLoader';
import { addFavorite, removeFavorite, isFavorite, subscribeFavorites } from '../utils/favorites';

interface ImageLightboxProps {
  images: string[];
  initialIndex: number;
  onClose: () => void;
  mangaId?: string;
  mangaTitle?: string;
  onRequestHD?: (index: number) => void;
  isHDLoaded?: (index: number) => boolean;
  onNavigateToComic?: (index: number) => void;
  isAdmin?: boolean;
}

export function ImageLightbox({ images, initialIndex, onClose, mangaId, mangaTitle, onRequestHD, isHDLoaded, onNavigateToComic, isAdmin = false }: ImageLightboxProps) {
  const [currentIndex, setCurrentIndex] = useState(initialIndex);
  const [isBookMode, setIsBookMode] = useState(false);
  const [favRefresh, setFavRefresh] = useState(0);

  useEffect(() => {
    return subscribeFavorites(() => {
      setFavRefresh(p => p + 1);
    });
  }, []);

  // -- Carousel State --
  const [dragOffset, setDragOffset] = useState(0); // Pixels


  // -- Zoom & Pan --
  const [scale, setScale] = useState(1);
  const [position, setPosition] = useState({ x: 0, y: 0 });

  // -- Interaction State --
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [startPinchDist, setStartPinchDist] = useState<number | null>(null);
  const [startScale, setStartScale] = useState(1);

  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = 'unset'; };
  }, []);

  // -- Helpers --
  const getWrappedIndex = (index: number) => {
    const len = images.length;
    return ((index % len) + len) % len;
  };

  const getDistance = (touches: React.TouchList) => {
    return Math.hypot(
      touches[0].clientX - touches[1].clientX,
      touches[0].clientY - touches[1].clientY
    );
  };

  const clampPosition = (pos: { x: number, y: number }, s: number) => {
    const width = window.innerWidth;
    const height = window.innerHeight;

    // Bounds: (Dimension * Scale - Dimension) / 2
    // If scale < 1, limits are 0 (or negative, but we clamp to 0)
    const maxX = (width * s - width) / 2;
    const maxY = (height * s - height) / 2;

    return {
      x: Math.min(Math.max(pos.x, -maxX), maxX),
      y: Math.min(Math.max(pos.y, -maxY), maxY)
    };
  };

  // -- Navigation --
  const stride = isBookMode ? 2 : 1;

  const handlePrevious = () => {
    // if (scale > 1) return; // Allow navigation even if zoomed, just reset.
    setCurrentIndex(prev => getWrappedIndex(prev - stride));
    setDragOffset(0);
    setScale(1); // Reset zoom
    setPosition({ x: 0, y: 0 }); // Reset position
  };

  const handleNext = () => {
    // if (scale > 1) return; // Allow navigation even if zoomed, just reset.
    setCurrentIndex(prev => getWrappedIndex(prev + stride));
    setDragOffset(0);
    setScale(1); // Reset zoom
    setPosition({ x: 0, y: 0 }); // Reset position
  };

  // -- Interaction Handlers --
  const handleStart = (clientX: number, clientY: number) => {
    // if (isAnimating) return; // Removed
    setIsDragging(true);
    setDragStart({ x: clientX, y: clientY });
  };

  const handleMove = (clientX: number, clientY: number) => {
    if (!isDragging) return;

    if (scale > 1) {
      const deltaX = clientX - dragStart.x;
      const deltaY = clientY - dragStart.y;
      setPosition(prev => ({ x: prev.x + deltaX, y: prev.y + deltaY }));
      setDragStart({ x: clientX, y: clientY });
    } else {
      const deltaX = clientX - dragStart.x;
      setDragOffset(deltaX);
    }
  };

  const handleEnd = () => {
    setIsDragging(false);
    setStartPinchDist(null);

    if (scale > 1) return;

    const width = containerRef.current?.clientWidth || window.innerWidth;
    const threshold = width * 0.25;

    if (Math.abs(dragOffset) > threshold) {
      if (dragOffset > 0) handlePrevious();
      else handleNext();
    } else {
      setDragOffset(0);
    }
  };

  // -- Event Listeners --
  const onMouseDown = (e: React.MouseEvent) => { e.preventDefault(); handleStart(e.clientX, e.clientY); };
  const onMouseMove = (e: React.MouseEvent) => { e.preventDefault(); handleMove(e.clientX, e.clientY); };
  const onMouseUp = () => handleEnd();

  const onTouchStart = (e: React.TouchEvent) => {
    if (e.touches.length === 2) {
      const dist = getDistance(e.touches);
      setStartPinchDist(dist);
      setStartScale(scale);
      setIsDragging(false);
    } else if (e.touches.length === 1) {
      handleStart(e.touches[0].clientX, e.touches[0].clientY);
    }
  };

  const onTouchMove = (e: React.TouchEvent) => {
    if (e.touches.length === 2 && startPinchDist !== null) {
      const dist = getDistance(e.touches);
      const zoomFactor = dist / startPinchDist;
      const newScale = Math.min(Math.max(startScale * zoomFactor, 1), 4);

      setScale(newScale);
      setPosition(prev => clampPosition(prev, newScale));

    } else if (e.touches.length === 1) {
      handleMove(e.touches[0].clientX, e.touches[0].clientY);
    }
  };

  const onTouchEnd = (e: React.TouchEvent) => {
    if (startPinchDist !== null && e.touches.length < 2) {
      setStartPinchDist(null);
      return;
    }
    handleEnd();
  };

  // -- Keyboard --
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
      else if (e.key === 'ArrowLeft') handlePrevious();
      else if (e.key === 'ArrowRight') handleNext();
      else if (e.key === '+' || e.key === '=') setScale(p => { const newS = Math.min(p + 0.5, 4); setPosition(prev => clampPosition(prev, newS)); return newS; });
      else if (e.key === '-') setScale(p => { const newS = Math.max(p - 0.5, 1); setPosition(prev => clampPosition(prev, newS)); return newS; });
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [scale, isBookMode]); // Removed isAnimating dependency

  // -- Render --
  let transform = `translateX(calc(-33.333333% + ${dragOffset}px))`;
  let transition = isDragging ? 'none' : 'transform 0.1s ease-out';
  // If not dragging, we want a tiny snap transition for the dragOffset reset, but NOT for page change.
  // Since handlePrevious reset dragOffset to 0 instantly and change index, we might not need transition at all for page change.
  // But if we just released a drag and it didn't change page, we want it to snap back.
  // Actually, simplest is no transition if we want INSTANT page change.
  // But for "snap back" (cancel drag), a small transition is nice.
  // Given user wants "no slide on change", we prioritize that. 
  // Let's set transition only if dragOffset is being animated back to 0 without index change? 
  // For simplicity and robustness of "no animation", let's use 'none' whenever dragOffset is 0.

  if (dragOffset === 0) {
    transition = 'none';
  }

  // Pre-calculate indices for slots
  // Slot 1 (Prev): currentIndex - stride
  // Slot 2 (Current): currentIndex
  // Slot 3 (Next): currentIndex + stride

  const renderSlot = (baseIndex: number) => {
    // If Book Mode: render baseIndex and baseIndex+1
    // If Single Mode: render baseIndex

    const img1Index = getWrappedIndex(baseIndex);

    if (!isBookMode) {
      return (
        <div className="relative w-full h-full flex items-center justify-center">
          <ImageLoader
            src={images[img1Index]}
            alt={`Página ${img1Index + 1}`}
            aspectRatio="auto"
            objectFit="contain"
            loading="lazy"
            draggable={false}
            imgClassName="max-w-full max-h-screen object-contain select-none shadow-2xl transition-none"
            showControls={true}
          />
          {mangaId && mangaTitle && isAdmin && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (!isAdmin) return;
                if (isFavorite(mangaId, img1Index)) {
                  removeFavorite(`${mangaId}_${img1Index}`);
                } else {
                  addFavorite({ mangaId, mangaTitle, pageUrl: images[img1Index], pageIndex: img1Index });
                }
                setFavRefresh(p => p + 1);
              }}
              className={`absolute top-6 left-6 p-3 rounded-full transition-all duration-200 z-[60] ${isFavorite(mangaId, img1Index) ? 'bg-[#ff4b4b]/20 text-[#ff4b4b]' : 'bg-black/50 text-white hover:bg-[#ff4b4b]/20 hover:text-[#ff4b4b]'}`}
              title={isFavorite(mangaId, img1Index) ? "Quitar de favoritos" : "Añadir a favoritos"}
            >
              <Heart className="w-6 h-6" fill={isFavorite(mangaId, img1Index) ? "currentColor" : "none"} />
            </button>
          )}
        </div>
      );
    } else {
      const img2Index = getWrappedIndex(baseIndex + 1);
      return (
        <div className="flex w-full h-full items-center justify-center px-2 sm:px-10">
          {/* Page 1 (Left) */}
          <div className="flex-1 h-full flex items-center justify-end relative">
            <ImageLoader
              src={images[img1Index]}
              alt={`Página ${img1Index + 1}`}
              aspectRatio="auto"
              objectFit="contain"
              loading="lazy"
              draggable={false}
              imgClassName="max-w-full max-h-screen object-contain select-none shadow-lg origin-right object-right transition-none"
              showControls={true}
            />
            {mangaId && mangaTitle && isAdmin && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isAdmin) return;
                  if (isFavorite(mangaId, img1Index)) {
                    removeFavorite(`${mangaId}_${img1Index}`);
                  } else {
                    addFavorite({ mangaId, mangaTitle, pageUrl: images[img1Index], pageIndex: img1Index });
                  }
                  setFavRefresh(p => p + 1);
                }}
                className={`absolute top-6 left-6 p-3 rounded-full transition-all duration-200 z-[60] ${isFavorite(mangaId, img1Index) ? 'bg-[#ff4b4b]/20 text-[#ff4b4b]' : 'bg-black/50 text-white hover:bg-[#ff4b4b]/20 hover:text-[#ff4b4b]'}`}
                title={isFavorite(mangaId, img1Index) ? "Quitar de favoritos" : "Añadir a favoritos"}
              >
                <Heart className="w-5 h-5" fill={isFavorite(mangaId, img1Index) ? "currentColor" : "none"} />
              </button>
            )}
          </div>
          {/* Page 2 (Right) */}
          <div className="flex-1 h-full flex items-center justify-start relative">
            <ImageLoader
              src={images[img2Index]}
              alt={`Página ${img2Index + 1}`}
              aspectRatio="auto"
              objectFit="contain"
              loading="lazy"
              draggable={false}
              imgClassName="max-w-full max-h-screen object-contain select-none shadow-lg origin-left object-left transition-none"
              showControls={true}
            />
            {mangaId && mangaTitle && isAdmin && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isAdmin) return;
                  if (isFavorite(mangaId, img2Index)) {
                    removeFavorite(`${mangaId}_${img2Index}`);
                  } else {
                    addFavorite({ mangaId, mangaTitle, pageUrl: images[img2Index], pageIndex: img2Index });
                  }
                  setFavRefresh(p => p + 1);
                }}
                className={`absolute top-6 right-6 p-3 rounded-full transition-all duration-200 z-[60] ${isFavorite(mangaId, img2Index) ? 'bg-[#ff4b4b]/20 text-[#ff4b4b]' : 'bg-black/50 text-white hover:bg-[#ff4b4b]/20 hover:text-[#ff4b4b]'}`}
                title={isFavorite(mangaId, img2Index) ? "Quitar de favoritos" : "Añadir a favoritos"}
              >
                <Heart className="w-5 h-5" fill={isFavorite(mangaId, img2Index) ? "currentColor" : "none"} />
              </button>
            )}
          </div>
        </div>
      );
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/95 flex items-center justify-center z-50 select-none touch-none overflow-hidden"
      style={{ touchAction: 'none' }}
      ref={containerRef}
      onWheel={(e) => {
        e.stopPropagation();
        const delta = e.deltaY < 0 ? 0.5 : -0.5;
        setScale(p => {
          const newS = Math.min(Math.max(p + delta, 1), 4);
          setPosition(prev => clampPosition(prev, newS));
          return newS;
        });
      }}
      onMouseDown={onMouseDown}
      onMouseMove={onMouseMove}
      onMouseUp={onMouseUp}
      onMouseLeave={() => { setIsDragging(false); if (scale === 1) setDragOffset(0); }}
      onTouchStart={onTouchStart}
      onTouchMove={onTouchMove}
      onTouchEnd={onTouchEnd}
    >
      {/* Controls */}
      <div className="absolute top-6 right-6 flex items-center gap-4 z-50">
        <div className="flex items-center gap-2 bg-black/50 rounded-lg p-1">
          {/* Navigate to Comic */}
          {onNavigateToComic && (
            <>
              <button
                onClick={() => {
                  onNavigateToComic(currentIndex);
                  onClose();
                }}
                className="p-2 text-white hover:text-[#bb86fc] transition-colors"
                title="Ir a leer el cómic completo"
              >
                <ExternalLink className="w-5 h-5" />
              </button>
              <div className="w-px h-4 bg-white/20 mx-1"></div>
            </>
          )}

          {/* Book Mode Toggle */}
          <button
            onClick={() => setIsBookMode(!isBookMode)}
            className={`p-2 transition-colors ${isBookMode ? 'text-[#bb86fc]' : 'text-white hover:text-[#bb86fc]'}`}
            title={isBookMode ? "Vista Individual" : "Vista de Libro"}
          >
            {isBookMode ? <BookOpen className="w-5 h-5" /> : <Book className="w-5 h-5" />}
          </button>
          <div className="w-px h-4 bg-white/20 mx-1"></div>

          {/* HD Toggle */}
          {onRequestHD && (
            <>
              <button
                onClick={() => onRequestHD(currentIndex)}
                className={`p-2 transition-colors font-bold text-sm ${isHDLoaded?.(currentIndex) ? 'text-[#bb86fc]' : 'text-white hover:text-[#bb86fc]'}`}
                title="Cargar versión en alta calidad (HD)"
              >
                HD
              </button>
              <div className="w-px h-4 bg-white/20 mx-1"></div>
            </>
          )}

          <button onClick={() => setScale(p => {
            const newS = Math.max(p - 0.5, 1);
            setPosition(prev => clampPosition(prev, newS));
            return newS;
          })} className="p-2 text-white hover:text-[#bb86fc] transition-colors"><ZoomOut className="w-5 h-5" /></button>
          <span className="text-white text-sm min-w-[3ch] text-center">{Math.round(scale * 100)}%</span>
          <button onClick={() => setScale(p => {
            const newS = Math.min(p + 0.5, 4);
            setPosition(prev => clampPosition(prev, newS));
            return newS;
          })} className="p-2 text-white hover:text-[#bb86fc] transition-colors"><ZoomIn className="w-5 h-5" /></button>
        </div>
        <button onClick={onClose} className="p-2 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-all duration-200">
          <X className="w-6 h-6" />
        </button>
      </div>

      {/* TRACK */}
      <div
        className="flex h-full w-[300%] absolute top-0 left-0"
        style={{ transform, transition }}
      >
        {/* PREV Slot */}
        <div className="w-1/3 h-full flex items-center justify-center relative">
          {renderSlot(currentIndex - stride)}
        </div>

        {/* CURRENT Slot (Zoomable Container) */}
        <div className="w-1/3 h-full flex items-center justify-center relative">
          <div
            className="relative flex items-center justify-center w-full h-full"
            style={{
              transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`,
              transition: isDragging ? 'none' : 'transform 0.1s ease-out',
              cursor: scale > 1 ? (isDragging ? 'grabbing' : 'grab') : 'default',
            }}
            onDoubleClick={(e) => { e.stopPropagation(); setScale(p => p > 1 ? 1 : 2.5); setPosition({ x: 0, y: 0 }); }}
          >
            {renderSlot(currentIndex)}
          </div>
        </div>

        {/* NEXT Slot */}
        <div className="w-1/3 h-full flex items-center justify-center relative">
          {renderSlot(currentIndex + stride)}
        </div>
      </div>

      {/* Navigation Arrows */}
      {scale === 1 && (
        <>
          <button
            onClick={(e) => { e.stopPropagation(); handlePrevious(); }}
            className="absolute left-4 sm:left-8 top-1/2 -translate-y-1/2 p-3 sm:p-4 rounded-lg text-white opacity-40 hover:opacity-100 transition-opacity duration-200 z-40"
          >
            <ChevronLeft className="w-8 h-8 sm:w-10 sm:h-10" />
          </button>
          <button
            onClick={(e) => { e.stopPropagation(); handleNext(); }}
            className="absolute right-4 sm:right-8 top-1/2 -translate-y-1/2 p-3 sm:p-4 rounded-lg text-white opacity-40 hover:opacity-100 transition-opacity duration-200 z-40"
          >
            <ChevronRight className="w-8 h-8 sm:w-10 sm:h-10" />
          </button>
        </>
      )}

      <div className="absolute bottom-6 left-1/2 -translate-x-1/2 bg-black/60 text-white px-4 py-2 rounded-lg text-sm font-medium z-40 pointer-events-none">
        {isBookMode
          ? `${currentIndex + 1}-${Math.min(currentIndex + 2, images.length)} / ${images.length}`
          : `${currentIndex + 1} / ${images.length}`
        }
      </div>
    </div>
  );
}
