import { useState, useEffect } from 'react';
import { BookOpen, Edit2, Trash2, Check, Folder } from 'lucide-react';
import { Manga } from '../types/manga';
import { ImageLoader } from './ImageLoader';
import { incrementMangaViews } from '../services/manga';
import { getThumbnailUrl } from '../utils/imageUtils';
import { Swiper, SwiperSlide } from 'swiper/react';
import { PatreonIcon } from './PatreonIcon';
import { EffectCreative } from 'swiper/modules';
import 'swiper/css';
import 'swiper/css/effect-creative';
import 'swiper/css/autoplay';

interface MangaCardProps {
  id: string;
  title: string;
  author: string;
  pageCount: number;
  thumbnail?: string;
  manga?: Manga;
  onSelect?: (id: string) => void;
  onEdit?: (manga: Manga) => void;
  onDelete?: (id: string) => void;
  isCategoryPlusEnabled?: boolean;
  isSelected?: boolean;
  onMouseDown?: (e: React.MouseEvent) => void;
  onMouseEnter?: (e: React.MouseEvent) => void;
  folderItemCount?: number;
  folderThumbnails?: string[];
  hasSubfolders?: boolean;
  isFolderAnimationEnabled?: boolean;
  currentSection?: 'flow' | 'patreon' | 'onlyfans' | 'grok';
  dragStateParams?: { isDragging: boolean, action: 'select' | 'deselect' | null, startId: string | null, hasDragged: boolean };
  hasAnySelection?: boolean;
  onToggleSelect?: () => void;
}

export function MangaCard({ id, title, author, pageCount, thumbnail, manga, onSelect, onEdit, onDelete, isCategoryPlusEnabled, isSelected, onMouseDown, onMouseEnter, folderItemCount, folderThumbnails, hasSubfolders, isFolderAnimationEnabled = true, currentSection, dragStateParams, hasAnySelection, onToggleSelect }: MangaCardProps) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [currentThumbIndex, setCurrentThumbIndex] = useState(0);
  const thumbnailUrl = thumbnail ? getThumbnailUrl(thumbnail) : undefined;
  const [swiperInstance, setSwiperInstance] = useState<any>(null);
  const [isZoomedIn, setIsZoomedIn] = useState(true);
  const [isHovered, setIsHovered] = useState(false);

  const isPatreonFolder = Boolean(manga?.is_folder && title.toLowerCase().includes('patreon'));
  const isRootPatreonLogo = isPatreonFolder && !manga?.folder_id && Boolean(folderThumbnails && folderThumbnails.length >= 2);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (!isHovered || !isFolderAnimationEnabled) {
      if (manga?.is_folder && folderThumbnails && folderThumbnails.length > 2) {
        setIsZoomedIn(true);
      }
      return;
    }
    
    // Crossfade fallback for exactly 2 images
    if (manga?.is_folder && folderThumbnails && folderThumbnails.length === 2) {
      const crossfadeAnimation = () => {
        setCurrentThumbIndex((prev) => (prev + 1) % folderThumbnails.length);
      };
      
      crossfadeAnimation(); // Correr inmediatamente al pasar el mouse
      interval = setInterval(crossfadeAnimation, 4000);
    }

    // Staggered zoom-slide-zoom animation for > 2 items
    if (swiperInstance && manga?.is_folder && folderThumbnails && folderThumbnails.length > 2) {
      const swiperAnimation = () => {
        setIsZoomedIn(false); // 1. Zoom out
        setTimeout(() => {
          swiperInstance?.slideNext(600); // 2. Slide
          setTimeout(() => {
            setIsZoomedIn(true); // 3. Zoom in
          }, 700); // Wait for slide to end
        }, 400); // Wait for zoom out to end
      };

      swiperAnimation(); // Correr inmediatamente al pasar el mouse
      interval = setInterval(swiperAnimation, 4500); // Cycle total
    }

    return () => clearInterval(interval);
  }, [manga?.is_folder, folderThumbnails, swiperInstance, isHovered]);

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    setShowDeleteConfirm(true);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    onDelete?.(id);
    setShowDeleteConfirm(false);
  };

  const handleEditClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (manga) {
      onEdit?.(manga);
    }
  };

  return (
    <div className="group cursor-pointer flex flex-col w-full max-w-xs">
      <div
        onMouseDown={onMouseDown}
        onMouseEnter={(e) => {
          setIsHovered(true);
          onMouseEnter?.(e);
        }}
        onMouseLeave={() => setIsHovered(false)}
        onDragStart={(e) => {
          e.preventDefault();
        }}
        onClick={(e) => {
          if (dragStateParams?.hasDragged) {
            e.preventDefault();
          } else if (isCategoryPlusEnabled || hasAnySelection) {
            e.preventDefault();
            onToggleSelect?.();
          } else {
            incrementMangaViews(id);
            onSelect?.(id);
          }
        }}
        className={`relative bg-black rounded-lg shadow-lg overflow-hidden transition-transform duration-300 hover:scale-[1.02] aspect-[2/3] ${isSelected ? 'ring-4 ring-[#bb86fc]' : ''}`}
      >
        {manga?.is_folder ? (
          <div className="w-full aspect-[2/3] relative flex items-center justify-center bg-gradient-to-br from-[#1a1a1a] to-[#2a2a2a] rounded-lg border-2 border-gray-800 transition-colors duration-300 overflow-hidden group-hover:border-purple-500/50">
            {folderThumbnails && folderThumbnails.length > 0 ? (
              <>
                <div className="absolute inset-0 w-full h-full bg-black flex items-center justify-center overflow-hidden pointer-events-none">
                  {currentSection !== 'flow' && folderThumbnails.length >= 2 ? (
                    <div 
                      className="w-full h-full bg-[#111] p-[3px] grid gap-[3px]" 
                      style={{
                        gridTemplateColumns: '1fr 1fr',
                        gridTemplateRows: folderThumbnails.length >= 3 ? '1fr 1fr' : '1fr'
                      }}
                    >
                      {folderThumbnails.slice(0, 4).map((thumb, index) => (
                        <div 
                          key={thumb + index} 
                          className={`relative overflow-hidden bg-gray-900 rounded-[3px] ${
                            (folderThumbnails.length === 3 && index === 0) ? 'col-span-2' : ''
                          }`}
                        >
                          <ImageLoader
                            src={getThumbnailUrl(thumb) || ''}
                            alt="Patreon Collage"
                            aspectRatio="auto"
                            objectFit="cover"
                            loading="lazy"
                            className="absolute inset-0 w-full h-full"
                            imgClassName="w-full h-full object-cover transition-transform duration-700 group-hover:scale-110"
                          />
                        </div>
                      ))}
                    </div>
                  ) : folderThumbnails.length > 2 ? (
                    (isHovered && isFolderAnimationEnabled) ? (
                      <Swiper
                        onSwiper={setSwiperInstance}
                        effect={'creative'}
                        grabCursor={false}
                        centeredSlides={true}
                        slidesPerView={1}
                        loop={folderThumbnails.length > 2}
                        allowTouchMove={false}
                        speed={600}
                        creativeEffect={{
                          limitProgress: 2,
                          prev: {
                            shadow: true,
                            translate: ['-65%', 0, -300],
                            rotate: [0, 45, 0],
                          },
                          next: {
                            shadow: true,
                            translate: ['65%', 0, -300],
                            rotate: [0, -45, 0],
                          },
                        }}
                        modules={[EffectCreative]}
                        className="w-full h-full flex items-center justify-center overflow-visible"
                      >
                         {folderThumbnails.map((thumb, index) => (
                          <SwiperSlide key={thumb + index} style={{ width: '100%', height: '100%' }} className="flex items-center justify-center overflow-visible">
                            {({ isActive }) => (
                              <div className={`w-full h-full transition-transform duration-[400ms] ease-in-out origin-center rounded-lg overflow-hidden shadow-2xl border-2 border-white/5 ${isActive && isZoomedIn ? 'scale-100' : 'scale-[0.80]'}`}>
                                <ImageLoader
                                  src={getThumbnailUrl(thumb) || ''}
                                  alt="Folder Cover"
                                  aspectRatio="2/3"
                                  objectFit="cover"
                                  loading="lazy"
                                  className="w-full h-full"
                                />
                              </div>
                            )}
                          </SwiperSlide>
                        ))}
                      </Swiper>
                    ) : (
                      <ImageLoader
                        src={getThumbnailUrl(folderThumbnails[0]) || ''}
                        alt="Folder Cover"
                        aspectRatio="2/3"
                        objectFit="cover"
                        loading="lazy"
                        className="w-full h-full"
                        imgClassName="transition-transform duration-700"
                      />
                    )
                  ) : folderThumbnails.length === 2 ? (
                    folderThumbnails.map((thumb, index) => (
                      <div 
                        key={thumb + index}
                        className={`absolute inset-0 w-full h-full transition-all duration-[600ms] ease-out ${index === currentThumbIndex ? 'opacity-100 scale-100 blur-0 z-10' : 'opacity-0 scale-110 blur-md z-0'} pointer-events-none`}
                      >
                        <ImageLoader
                          src={getThumbnailUrl(thumb) || ''}
                          alt="Folder Cover"
                          aspectRatio="2/3"
                          objectFit="cover"
                          loading="lazy"
                          className="w-full h-full"
                          imgClassName=""
                        />
                      </div>
                    ))
                  ) : (
                    <ImageLoader
                      src={getThumbnailUrl(folderThumbnails[0]) || ''}
                      alt="Folder Cover"
                      aspectRatio="2/3"
                      objectFit="cover"
                      loading="lazy"
                      className="w-full h-full"
                      imgClassName="transition-transform duration-700 group-hover:scale-110"
                    />
                  )}
                </div>
                <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none z-10"></div>
                
                {isRootPatreonLogo && (
                  <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
                    <div className="bg-gray-800/50 backdrop-blur-[8px] rounded-2xl w-[55%] aspect-square border border-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.5)] flex flex-col items-center justify-center gap-2 sm:gap-3 transition-transform duration-500 group-hover:scale-105">
                      <PatreonIcon className="w-[40%] h-[40%] text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" />
                      <span className="text-white font-bold text-[9px] sm:text-[11px] tracking-widest uppercase drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]">
                        Patreon
                      </span>
                    </div>
                  </div>
                )}

                {/* Iconito Glassmorphism en la esquina inferior derecha */}
                {!isRootPatreonLogo && (
                  <div className="absolute bottom-2 right-2 z-20 flex items-center justify-center bg-gray-800/70 backdrop-blur-md rounded-lg p-1.5 border border-gray-500/50 shadow-xl transition-all duration-300 group-hover:bg-gray-700/80 group-hover:scale-110">
                    {hasSubfolders ? (
                      <div className="relative w-[20px] h-[20px]">
                        <Folder className="absolute top-0 right-0 w-3.5 h-3.5 text-white/50" />
                        <Folder className="absolute bottom-0 left-0 w-4 h-4 text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)] fill-black/20" />
                      </div>
                    ) : (
                      <Folder className="w-4 h-4 text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)]" />
                    )}
                  </div>
                )}
              </>
            ) : (
              // Carpeta vacía
              <>
                {isRootPatreonLogo && (
                  <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
                    <div className="bg-gray-800/50 backdrop-blur-[8px] rounded-2xl w-[55%] aspect-square border border-white/10 shadow-[0_8px_32px_0_rgba(0,0,0,0.5)] flex flex-col items-center justify-center gap-2 sm:gap-3 transition-transform duration-500 group-hover:scale-105">
                      <PatreonIcon className="w-[40%] h-[40%] text-white drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]" />
                      <span className="text-white font-bold text-[9px] sm:text-[11px] tracking-widest uppercase drop-shadow-[0_2px_4px_rgba(0,0,0,0.6)]">
                        Patreon
                      </span>
                    </div>
                  </div>
                )}

                {!isRootPatreonLogo && (
                  <div className="absolute bottom-2 right-2 z-20 flex items-center justify-center bg-gray-800/70 backdrop-blur-md rounded-lg p-1.5 border border-gray-500/50 shadow-xl transition-all duration-300 group-hover:bg-gray-700/80 group-hover:scale-110">
                    {hasSubfolders ? (
                      <div className="relative w-[20px] h-[20px]">
                        <Folder className="absolute top-0 right-0 w-3.5 h-3.5 text-white/50" />
                        <Folder className="absolute bottom-0 left-0 w-4 h-4 text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)] fill-black/20" />
                      </div>
                    ) : (
                      <Folder className="w-4 h-4 text-white drop-shadow-[0_0_5px_rgba(255,255,255,0.5)]" />
                    )}
                  </div>
                )}
                
                <div className="relative z-10 flex flex-col items-center justify-center opacity-30">
                  {!isRootPatreonLogo && (
                    <Folder className="w-16 h-16 text-gray-400 mb-2" />
                  )}
                </div>
              </>
            )}
          </div>
        ) : thumbnailUrl ? (
          <>
            <ImageLoader
              src={thumbnailUrl}
              alt={title}
              aspectRatio="2/3"
              objectFit="cover"
              loading="lazy"
              imgClassName="group-hover:scale-110"
            />
            <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-black/60 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"></div>
          </>
        ) : (
          <div className="w-full aspect-[2/3] flex items-center justify-center text-white/40 bg-gradient-to-br from-gray-800 to-gray-900 rounded-lg group-hover:text-white/60">
            <BookOpen className="w-12 h-12" />
          </div>
        )}

        {manga?.is_folder && folderItemCount !== undefined && (
          <div className="absolute bottom-2 left-2 flex gap-1 flex-wrap pointer-events-none items-end z-10">
            <div className="bg-black/70 text-white text-xs px-2 py-1 rounded-md font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-md">
              {folderItemCount} elementos
            </div>
          </div>
        )}

        {!manga?.is_folder && (
          <div className="absolute bottom-2 left-2 flex gap-1 flex-wrap pointer-events-none items-end">
            <div className="bg-black/70 text-white text-xs px-2 py-1 rounded-md font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-md">
              {pageCount} paginas
            </div>
            {manga?.is_decensored && (
              <div className="bg-black/70 text-white text-xs px-2 py-1 rounded-md font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-md">
                Sin censura
              </div>
            )}
            {manga?.is_bn && (
              <div className="bg-black/70 text-white text-xs px-2 py-1 rounded-md font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-md">
                B/N
              </div>
            )}
            {manga?.is_color && (
              <div className="bg-black/70 text-white text-xs px-2 py-1 rounded-md font-semibold opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-md">
                a color
              </div>
            )}
          </div>
        )}

        {(isCategoryPlusEnabled || hasAnySelection) && (
          <div className={`absolute top-2 left-2 w-6 h-6 rounded-md border-2 flex items-center justify-center transition-all ${isSelected ? 'bg-[#bb86fc] border-[#bb86fc]' : 'bg-black/50 border-white/50 hover:border-white'}`}>
            {isSelected && <Check className="w-4 h-4 text-white" />}
          </div>
        )}

        {!isCategoryPlusEnabled && !hasAnySelection && (
          <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300 flex gap-1">
            {manga && onEdit && (
              <button
                onClick={handleEditClick}
                className="bg-black/60 hover:bg-purple-600 text-white p-1.5 rounded-full transition-colors backdrop-blur-sm"
                title="Editar manga"
              >
                <Edit2 className="w-3 h-3" />
              </button>
            )}
            {onDelete && (
              <button
                onClick={handleDeleteClick}
                className="bg-black/60 hover:bg-red-600 text-white p-1.5 rounded-full transition-colors backdrop-blur-sm"
                title="Eliminar manga"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        {showDeleteConfirm && (
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center gap-3 rounded-lg z-20 animate-in fade-in duration-200">
            <p className="text-white text-sm font-semibold text-center px-3">Eliminar manga?</p>
            <div className="flex gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowDeleteConfirm(false);
                }}
                className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-1.5 rounded-md text-xs font-semibold transition-all duration-200 transform hover:scale-105 active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmDelete}
                className="bg-red-600 hover:bg-red-700 text-white px-3 py-1.5 rounded-md text-xs font-semibold transition-all duration-200 transform hover:scale-105 active:scale-95"
              >
                Eliminar
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="mt-1 sm:mt-2 flex flex-col gap-0.5 text-center mb-2">
        <h3
          onClick={() => onSelect?.(id)}
          className="font-semibold text-xs sm:text-sm text-white line-clamp-2 cursor-pointer text-center group-hover:text-purple-400 transition-colors duration-300 ease-out"
        >
          {title}
        </h3>
        {author && author.trim() !== '' && author.toLowerCase() !== 'anónimo' && author.toLowerCase() !== 'anonimo' && (
          <p className="text-xs text-gray-400 text-center group-hover:text-gray-300 transition-colors duration-300 ease-out">
            {author}
          </p>
        )}
      </div>
    </div>
  );
}
