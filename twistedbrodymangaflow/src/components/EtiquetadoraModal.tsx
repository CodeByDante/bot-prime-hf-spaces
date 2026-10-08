import { X, Save, Tag } from 'lucide-react';
import { toast } from 'sonner';
import { useState, useEffect } from 'react';
import { getMangaById, updateManga } from '../services/manga';
import { LoadingSpinner } from './LoadingSpinner';

interface MangaToggles {
  id: string;
  title: string;
  is_decensored: boolean;
  is_bn: boolean;
  is_color: boolean;
  hasChanged: boolean;
}

interface EtiquetadoraModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedMangaIds: string[];
  onSaveComplete: () => void;
}

export function EtiquetadoraModal({ isOpen, onClose, selectedMangaIds, onSaveComplete }: EtiquetadoraModalProps) {
  const [mangas, setMangas] = useState<MangaToggles[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Global toggle states
  const [globalDecensored, setGlobalDecensored] = useState(false);
  const [globalBn, setGlobalBn] = useState(false);
  const [globalColor, setGlobalColor] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadMangas();
      setGlobalDecensored(false);
      setGlobalBn(false);
      setGlobalColor(false);
    }
  }, [isOpen, selectedMangaIds]);

  const loadMangas = async () => {
    setIsLoading(true);
    try {
      const loaded = await Promise.all(
        selectedMangaIds.map(async (id) => {
          const manga = await getMangaById(id);
          if (!manga) return null;
          return {
            id: manga.id,
            title: manga.title,
            is_decensored: !!manga.is_decensored,
            is_bn: !!manga.is_bn,
            is_color: !!manga.is_color,
            hasChanged: false,
          } as MangaToggles;
        })
      );
      setMangas(loaded.filter(m => m !== null) as MangaToggles[]);
    } catch (error) {
      console.error('Error loading mangas:', error);
      toast.error('Error al cargar la información de los mangas');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGlobalDecensored = (checked: boolean) => {
    setGlobalDecensored(checked);
    setMangas(prev => prev.map(m => ({ ...m, is_decensored: checked, hasChanged: true })));
  };

  const handleGlobalBn = (checked: boolean) => {
    setGlobalBn(checked);
    if (checked) setGlobalColor(false);
    setMangas(prev => prev.map(m => ({ 
      ...m, 
      is_bn: checked, 
      is_color: checked ? false : m.is_color, 
      hasChanged: true 
    })));
  };

  const handleGlobalColor = (checked: boolean) => {
    setGlobalColor(checked);
    if (checked) setGlobalBn(false);
    setMangas(prev => prev.map(m => ({ 
      ...m, 
      is_color: checked, 
      is_bn: checked ? false : m.is_bn, 
      hasChanged: true 
    })));
  };

  const handleIndividualToggle = (id: string, field: 'is_decensored' | 'is_bn' | 'is_color', value: boolean) => {
    setMangas(prev => prev.map(m => {
      if (m.id !== id) return m;
      
      const newM = { ...m, [field]: value, hasChanged: true };
      
      if (field === 'is_bn' && value) newM.is_color = false;
      if (field === 'is_color' && value) newM.is_bn = false;
      
      return newM;
    }));
  };

  const handleSave = async () => {
    const changedMangas = mangas.filter(m => m.hasChanged);
    
    if (changedMangas.length === 0) {
      toast.info('No hay cambios para guardar');
      onClose();
      return;
    }

    setIsSaving(true);
    try {
      const promises = changedMangas.map(manga => 
        updateManga(manga.id, {
          is_decensored: manga.is_decensored,
          is_bn: manga.is_bn,
          is_color: manga.is_color
        })
      );
      
      await Promise.all(promises);
      toast.success(`Se actualizaron las etiquetas de ${changedMangas.length} mangas`);
      onSaveComplete();
      onClose();
    } catch (error) {
      console.error('Error updating mangas:', error);
      toast.error('Ocurrió un error al guardar los cambios');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
      <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-[#bb86fc]/10 rounded-lg text-[#bb86fc]">
              <Tag className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-white">
              Etiquetadora ({selectedMangaIds.length} mangas)
            </h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto custom-scrollbar flex-1 space-y-6">
          {isLoading ? (
            <div className="flex justify-center p-8">
              <LoadingSpinner size={32} />
            </div>
          ) : (
            <>
              {/* Global Toggles */}
              <div className="bg-[#1f1f1f] p-5 rounded-xl border border-gray-700 shadow-lg">
                <h3 className="text-md font-bold text-white mb-4 flex items-center gap-2">
                  <Tag className="w-4 h-4 text-[#bb86fc]" /> Opciones Generales
                </h3>
                <div className="flex flex-col sm:flex-row gap-6">
                  <div className="flex items-center gap-3">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={globalDecensored}
                        onChange={(e) => handleGlobalDecensored(e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                    </label>
                    <div>
                      <span className="text-sm font-semibold text-white">Sin censura (Todos)</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={globalBn}
                        onChange={(e) => handleGlobalBn(e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                    </label>
                    <div>
                      <span className="text-sm font-semibold text-white">B/N (Todos)</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-3">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={globalColor}
                        onChange={(e) => handleGlobalColor(e.target.checked)}
                      />
                      <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                    </label>
                    <div>
                      <span className="text-sm font-semibold text-white">a color (Todos)</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Individual Manga List */}
              <div className="space-y-3">
                <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider px-2">
                  Mangas Individuales ({mangas.length})
                </h3>
                <div className="bg-[#1a1a1a] rounded-xl border border-gray-800 divide-y divide-gray-800">
                  {mangas.map((manga) => (
                    <div key={manga.id} className={`p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 transition-colors ${manga.hasChanged ? 'bg-[#bb86fc]/5' : 'hover:bg-[#1f1f1f]'}`}>
                      <div className="flex-1 min-w-0 pr-4">
                        <h4 className="text-sm font-semibold text-white truncate" title={manga.title}>
                          {manga.title}
                        </h4>
                        {manga.hasChanged && (
                          <span className="text-[10px] text-[#bb86fc] uppercase tracking-widest font-bold">Modificado</span>
                        )}
                      </div>
                      
                      <div className="flex items-center gap-4 sm:gap-6 shrink-0">
                        <div className="flex flex-col items-center gap-1">
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={manga.is_decensored}
                              onChange={(e) => handleIndividualToggle(manga.id, 'is_decensored', e.target.checked)}
                            />
                            <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                          </label>
                          <span className="text-[10px] text-gray-400 font-medium">Sin censura</span>
                        </div>

                        <div className="flex flex-col items-center gap-1">
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={manga.is_bn}
                              onChange={(e) => handleIndividualToggle(manga.id, 'is_bn', e.target.checked)}
                            />
                            <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                          </label>
                          <span className="text-[10px] text-gray-400 font-medium">B/N</span>
                        </div>

                        <div className="flex flex-col items-center gap-1">
                          <label className="relative inline-flex items-center cursor-pointer">
                            <input
                              type="checkbox"
                              className="sr-only peer"
                              checked={manga.is_color}
                              onChange={(e) => handleIndividualToggle(manga.id, 'is_color', e.target.checked)}
                            />
                            <div className="w-9 h-5 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                          </label>
                          <span className="text-[10px] text-gray-400 font-medium">a color</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>

        <div className="p-6 border-t border-gray-800 flex justify-end gap-3 bg-[#1a1a1a]">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:text-white transition-colors"
          >
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || isLoading || mangas.filter(m => m.hasChanged).length === 0}
            className="bg-[#bb86fc] hover:bg-[#9966dd] text-white px-6 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-[#bb86fc]/20 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? (
              <>
                <LoadingSpinner size={16} />
                Guardando...
              </>
            ) : (
              <>
                <Save className="w-4 h-4" />
                Guardar Cambios ({mangas.filter(m => m.hasChanged).length})
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
