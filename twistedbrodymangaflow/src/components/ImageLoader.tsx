import { useState, useEffect } from 'react';
import { RotateCcw, AlertCircle } from 'lucide-react';

// Caché global en memoria para recordar qué URLs absolutas ya se cargaron exitosamente
// durante esta sesión del navegador.
const loadedImagesCache = new Set<string>();

interface ImageLoaderProps {
  src: string;
  alt: string;
  className?: string;
  imgClassName?: string;
  objectFit?: 'cover' | 'contain' | 'fill' | 'none' | 'scale-down';
  aspectRatio?: string;
  loading?: 'lazy' | 'eager';
  showPlaceholder?: boolean;
  draggable?: boolean;
  showControls?: boolean;
}

export function ImageLoader({
  src,
  alt,
  className = '',
  imgClassName = '',
  objectFit = 'contain',
  aspectRatio,
  loading,
  draggable,
  showControls = false
}: ImageLoaderProps) {
  // Si la imagen ya está en caché, inicializamos isLoaded en true instantáneamente
  const isAlreadyLoaded = loadedImagesCache.has(src);
  
  // 1. Estados para controlar qué mostrar
  const [isLoaded, setIsLoaded] = useState(isAlreadyLoaded);
  const [hasError, setHasError] = useState(false);
  const [retryCount, setRetryCount] = useState(0);

  // Reiniciar estados si cambia la fuente (por ejemplo, al cambiar de capítulo)
  useEffect(() => {
    if (loadedImagesCache.has(src)) {
      setIsLoaded(true);
      setHasError(false);
    } else {
      setIsLoaded(false);
      setHasError(false);
    }
    setRetryCount(0);
  }, [src]);

  const handleRetry = () => {
    setHasError(false);
    setIsLoaded(false);
    setRetryCount(prev => prev + 1);
  };

  const handleLoadSuccess = () => {
    setIsLoaded(true);
    setHasError(false);
    // Añadimos a la caché global
    loadedImagesCache.add(src);
  };

  // Añadimos un timestamp o contador falso a la query string para esquivar el caché del navegador
  // si es que ya hay reintentos.
  const currentSrc = retryCount > 0 
    ? `${src}${src.includes('?') ? '&' : '?'}retry=${retryCount}` 
    : src;

  const isVideo = currentSrc.includes('format=mp4') || currentSrc.toLowerCase().endsWith('.mp4') || currentSrc.toLowerCase().endsWith('.webm');


  return (
    <div
      className={`relative w-full h-full overflow-hidden ${hasError ? 'bg-[#1a1a1a]/50 rounded-lg min-h-[300px]' : ''} ${className}`}
      style={aspectRatio && aspectRatio !== 'auto' ? { aspectRatio } : undefined}
    >

      {/* 2. EL SPINNER (Círculo de carga) o ESTADO DE ERROR 
                Se muestra solo si NO ha terminado de cargar (!isLoaded).
                Cuando carga, se vuelve invisible (opacity-0).
            */}
      <div className={`absolute inset-0 flex items-center justify-center transition-opacity duration-500 ${isLoaded ? 'opacity-0 pointer-events-none' : 'opacity-100'
        }`}>
        {hasError ? (
          <div className="flex flex-col items-center justify-center p-6 text-center max-w-sm w-full h-full">
            <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-3">
              <AlertCircle className="w-6 h-6 text-red-500" />
            </div>
            <p className="text-sm text-gray-400 mb-4">La imagen no cargó. El servidor podría tener problemas.</p>
            <button 
              onClick={handleRetry}
              className="flex items-center justify-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-white rounded-lg transition-colors border border-gray-700 w-full max-w-[200px]"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Reintentar ({retryCount})</span>
            </button>
          </div>
        ) : (
          <div className="w-8 h-8 border-2 border-[#bb86fc] border-t-transparent rounded-full animate-spin"></div>
        )}
      </div>

      {/* 3. LA IMAGEN REAL 
                Empieza invisible (opacity-0).
                Cuando se dispara onLoad, pasa a 'opacity-100' creando la animación de aparición.
            */}
      {!hasError && (
        isVideo ? (
          <video
            src={currentSrc}
            autoPlay={!showControls}
            loop={!showControls}
            muted={!showControls}
            playsInline
            controls={showControls}
            className={`w-full h-full object-${objectFit} transition-all duration-1000 ease-linear ${imgClassName} ${isLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoadedData={handleLoadSuccess}
            onError={() => {
              setHasError(true);
              setIsLoaded(false);
            }}
          />
        ) : (
          <img
            src={currentSrc}
            alt={alt}
            loading={loading}
            draggable={draggable}
            className={`w-full h-full object-${objectFit} transition-all duration-1000 ease-linear ${imgClassName} ${isLoaded ? 'opacity-100' : 'opacity-0'
              }`}
            onLoad={handleLoadSuccess}
            onError={() => {
              setHasError(true);
              setIsLoaded(false);
            }}
          />
        )
      )}

    </div>
  );
}
