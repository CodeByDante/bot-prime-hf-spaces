import { useState, useEffect } from 'react';
import { X, ArrowRight, ArrowLeft, Save, Loader2, ImagePlus } from 'lucide-react';
import { toast } from 'sonner';
import { getMangaById, swapMangaPages } from '../services/manga';
import { Manga } from '../types/manga';

interface TransferPagesModalProps {
  isOpen: boolean;
  onClose: () => void;
  mangaIds: string[];
  onSaveComplete: () => void;
}

export function TransferPagesModal({ isOpen, onClose, mangaIds, onSaveComplete }: TransferPagesModalProps) {
  const [mangaA, setMangaA] = useState<Manga | null>(null);
  const [mangaB, setMangaB] = useState<Manga | null>(null);
  const [pagesA, setPagesA] = useState<string[]>([]);
  const [pagesB, setPagesB] = useState<string[]>([]);
  const [selectedA, setSelectedA] = useState<Set<number>>(new Set());
  const [selectedB, setSelectedB] = useState<Set<number>>(new Set());
  const [isSaving, setIsSaving] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const [isDragging, setIsDragging] = useState<{ active: boolean; selecting: boolean; source: 'A' | 'B' | null }>({ active: false, selecting: true, source: null });

  useEffect(() => {
    const handleMouseUp = () => setIsDragging({ active: false, selecting: true, source: null });
    window.addEventListener('mouseup', handleMouseUp);
    return () => window.removeEventListener('mouseup', handleMouseUp);
  }, []);

  useEffect(() => {
    if (isOpen && mangaIds.length === 2) {
      loadMangas();
    } else {
      setMangaA(null);
      setMangaB(null);
      setPagesA([]);
      setPagesB([]);
      setSelectedA(new Set());
      setSelectedB(new Set());
    }
  }, [isOpen, mangaIds]);

  const loadMangas = async () => {
    setIsLoading(true);
    try {
      const [mA, mB] = await Promise.all([
        getMangaById(mangaIds[0]),
        getMangaById(mangaIds[1])
      ]);
      setMangaA(mA);
      setMangaB(mB);

      let pA: string[] = [];
      mA?.chapters?.forEach(c => pA.push(...(c.pages || [])));
      setPagesA(pA);

      let pB: string[] = [];
      mB?.chapters?.forEach(c => pB.push(...(c.pages || [])));
      setPagesB(pB);
      
      setSelectedA(new Set());
      setSelectedB(new Set());
    } catch (e) {
      toast.error('Error al cargar los mangas');
    } finally {
      setIsLoading(false);
    }
  };

  const moveToB = () => {
    if (selectedA.size === 0) return;
    const sortedSelectedA = Array.from(selectedA).sort((a, b) => a - b);
    const pagesToMove = sortedSelectedA.map(i => pagesA[i]);
    const newPagesA = pagesA.filter((_, i) => !selectedA.has(i));
    
    setPagesA(newPagesA);
    setPagesB(prev => [...prev, ...pagesToMove]);
    setSelectedA(new Set());
  };

  const moveToA = () => {
    if (selectedB.size === 0) return;
    const sortedSelectedB = Array.from(selectedB).sort((a, b) => a - b);
    const pagesToMove = sortedSelectedB.map(i => pagesB[i]);
    const newPagesB = pagesB.filter((_, i) => !selectedB.has(i));
    
    setPagesB(newPagesB);
    setPagesA(prev => [...prev, ...pagesToMove]);
    setSelectedB(new Set());
  };

  const handleDragStart = (source: 'A' | 'B', index: number) => {
    const isCurrentlySelected = source === 'A' ? selectedA.has(index) : selectedB.has(index);
    setIsDragging({ active: true, selecting: !isCurrentlySelected, source });
    handleDragEnter(source, index, !isCurrentlySelected);
  };

  const handleDragEnter = (source: 'A' | 'B', index: number, forceSelecting?: boolean) => {
    if (!isDragging.active && forceSelecting === undefined) return;
    if (isDragging.source !== null && isDragging.source !== source && forceSelecting === undefined) return;

    const selecting = forceSelecting !== undefined ? forceSelecting : isDragging.selecting;
    
    if (source === 'A') {
      setSelectedA(prev => {
        const next = new Set(prev);
        if (selecting) next.add(index);
        else next.delete(index);
        return next;
      });
    } else {
      setSelectedB(prev => {
        const next = new Set(prev);
        if (selecting) next.add(index);
        else next.delete(index);
        return next;
      });
    }
  };

  const handleSelectAllA = () => {
    if (selectedA.size === pagesA.length) {
      setSelectedA(new Set());
    } else {
      setSelectedA(new Set(pagesA.map((_, i) => i)));
    }
  };

  const handleSelectAllB = () => {
    if (selectedB.size === pagesB.length) {
      setSelectedB(new Set());
    } else {
      setSelectedB(new Set(pagesB.map((_, i) => i)));
    }
  };

  const handleSave = async () => {
    if (!mangaA || !mangaB) return;
    setIsSaving(true);
    try {
      await swapMangaPages(mangaA.id, mangaB.id, pagesA, pagesB);
      toast.success('Páginas transferidas correctamente.');
      onSaveComplete();
      onClose();
    } catch (err) {
      console.error(err);
      toast.error('Ocurrió un error al guardar los cambios.');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[70] flex items-center justify-center p-4 sm:p-6 animate-in fade-in duration-200">
      <div className="bg-[#121212] border border-gray-700 w-full max-w-7xl h-[90vh] rounded-2xl shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-500/10 rounded-lg text-amber-500">
              <ImagePlus className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Transferencia de Páginas</h2>
              <p className="text-sm text-gray-400">Mueve páginas de un manga a otro</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={isSaving || isLoading}
              className="bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-emerald-500/20 flex items-center gap-2"
            >
              {isSaving ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Save className="w-4 h-4" />
              )}
              Guardar Cambios
            </button>
            <button 
              onClick={onClose} 
              className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-12 h-12 text-amber-500 animate-spin" />
          </div>
        ) : (
          <div className="flex-1 flex flex-col md:flex-row min-h-0">
            
            {/* Manga A Column */}
            <div className="flex-1 flex flex-col min-h-0 border-r border-gray-800 bg-[#151515]">
              <div className="p-4 border-b border-gray-800 bg-[#1a1a1a] shrink-0 sticky top-0 z-10 flex flex-col gap-2">
                <h3 className="font-bold text-lg text-amber-400 truncate" title={mangaA?.title}>
                  {mangaA?.title || 'Cargando...'}
                </h3>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">{pagesA.length} páginas</span>
                  <div className="flex items-center gap-3">
                    <button onClick={handleSelectAllA} className="text-xs text-blue-400 hover:text-blue-300">
                      {selectedA.size === pagesA.length && pagesA.length > 0 ? 'Deseleccionar todo' : 'Seleccionar todo'}
                    </button>
                    {selectedA.size > 0 && (
                      <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-bold">
                        {selectedA.size} sel.
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {pagesA.map((url, idx) => (
                    <div 
                      key={`a-${idx}`}
                      onMouseDown={(e) => { e.preventDefault(); handleDragStart('A', idx); }}
                      onMouseEnter={() => handleDragEnter('A', idx)}
                      className={`relative aspect-[2/3] rounded-lg overflow-hidden cursor-pointer border-2 transition-all group select-none ${
                        selectedA.has(idx) ? 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]' : 'border-transparent hover:border-gray-500 bg-gray-800'
                      }`}
                    >
                      <img src={url} alt={`A-${idx}`} className="w-full h-full object-cover" loading="lazy" />
                      <div className={`absolute top-2 right-2 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                        selectedA.has(idx) ? 'bg-amber-500 border-amber-500' : 'bg-black/50 border-gray-300 group-hover:border-amber-500/50'
                      }`}>
                         {selectedA.has(idx) && <div className="w-2.5 h-2.5 bg-white rounded-full"></div>}
                      </div>
                      <div className="absolute bottom-2 left-2 px-2 py-1 bg-black/70 text-xs font-bold text-white rounded backdrop-blur-md">
                        {idx + 1}
                      </div>
                    </div>
                  ))}
                  {pagesA.length === 0 && (
                    <div className="col-span-full h-32 flex items-center justify-center text-gray-500 text-sm italic">
                      Vacío
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Middle Controls */}
            <div className="w-full md:w-24 shrink-0 bg-[#0f0f0f] flex flex-row md:flex-col items-center justify-center gap-4 py-4 md:py-0 border-y md:border-y-0 border-gray-800">
              <button
                onClick={moveToB}
                disabled={selectedA.size === 0}
                className="w-14 h-14 rounded-full bg-[#1a1a1a] hover:bg-amber-600 disabled:opacity-50 disabled:hover:bg-[#1a1a1a] border border-gray-700 flex items-center justify-center transition-colors text-white disabled:text-gray-600 shadow-xl group"
                title="Mover selección a la derecha"
              >
                <ArrowRight className="w-6 h-6 hidden md:block group-hover:scale-110 transition-transform" />
                <ArrowRight className="w-6 h-6 block md:hidden rotate-90 group-hover:scale-110 transition-transform" />
              </button>
              
              <button
                onClick={moveToA}
                disabled={selectedB.size === 0}
                className="w-14 h-14 rounded-full bg-[#1a1a1a] hover:bg-amber-600 disabled:opacity-50 disabled:hover:bg-[#1a1a1a] border border-gray-700 flex items-center justify-center transition-colors text-white disabled:text-gray-600 shadow-xl group"
                title="Mover selección a la izquierda"
              >
                <ArrowLeft className="w-6 h-6 hidden md:block group-hover:scale-110 transition-transform" />
                <ArrowLeft className="w-6 h-6 block md:hidden rotate-90 group-hover:scale-110 transition-transform" />
              </button>
            </div>

            {/* Manga B Column */}
            <div className="flex-1 flex flex-col min-h-0 bg-[#151515]">
              <div className="p-4 border-b border-gray-800 bg-[#1a1a1a] shrink-0 sticky top-0 z-10 flex flex-col gap-2">
                <h3 className="font-bold text-lg text-amber-400 truncate" title={mangaB?.title}>
                  {mangaB?.title || 'Cargando...'}
                </h3>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">{pagesB.length} páginas</span>
                  <div className="flex items-center gap-3">
                    <button onClick={handleSelectAllB} className="text-xs text-blue-400 hover:text-blue-300">
                      {selectedB.size === pagesB.length && pagesB.length > 0 ? 'Deseleccionar todo' : 'Seleccionar todo'}
                    </button>
                    {selectedB.size > 0 && (
                      <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded-full font-bold">
                        {selectedB.size} sel.
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                <div className="grid grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
                  {pagesB.map((url, idx) => (
                    <div 
                      key={`b-${idx}`}
                      onMouseDown={(e) => { e.preventDefault(); handleDragStart('B', idx); }}
                      onMouseEnter={() => handleDragEnter('B', idx)}
                      className={`relative aspect-[2/3] rounded-lg overflow-hidden cursor-pointer border-2 transition-all group select-none ${
                        selectedB.has(idx) ? 'border-amber-500 shadow-[0_0_15px_rgba(245,158,11,0.4)]' : 'border-transparent hover:border-gray-500 bg-gray-800'
                      }`}
                    >
                      <img src={url} alt={`B-${idx}`} className="w-full h-full object-cover" loading="lazy" />
                      <div className={`absolute top-2 right-2 w-6 h-6 rounded-full border-2 flex items-center justify-center transition-colors ${
                        selectedB.has(idx) ? 'bg-amber-500 border-amber-500' : 'bg-black/50 border-gray-300 group-hover:border-amber-500/50'
                      }`}>
                         {selectedB.has(idx) && <div className="w-2.5 h-2.5 bg-white rounded-full"></div>}
                      </div>
                      <div className="absolute bottom-2 left-2 px-2 py-1 bg-black/70 text-xs font-bold text-white rounded backdrop-blur-md">
                        {idx + 1}
                      </div>
                    </div>
                  ))}
                  {pagesB.length === 0 && (
                    <div className="col-span-full h-32 flex items-center justify-center text-gray-500 text-sm italic">
                      Vacío
                    </div>
                  )}
                </div>
              </div>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
