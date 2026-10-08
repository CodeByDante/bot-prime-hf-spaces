import { useState, useMemo, useEffect } from 'react';
import { X, Search, Save, Edit3 } from 'lucide-react';
import { Manga } from '../types/manga';
import { toast } from 'sonner';
import { updateMangaTitles } from '../services/manga';
import { getThumbnailUrl } from '../utils/imageUtils';

interface BulkEditTitleModalProps {
  isOpen: boolean;
  onClose: () => void;
  mangas: Manga[];
  selectedMangaIds: string[];
  onSaveComplete: () => void;
}

export function BulkEditTitleModal({ isOpen, onClose, mangas, selectedMangaIds, onSaveComplete }: BulkEditTitleModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [bulkName, setBulkName] = useState('');
  const [edits, setEdits] = useState<Record<string, string>>({});
  const [isSaving, setIsSaving] = useState(false);

  useEffect(() => {
    if (isOpen) {
      setSearchTerm('');
      setBulkName('');
      setEdits({});
    }
  }, [isOpen]);

  const handleApplyBulkName = () => {
    if (!bulkName.trim()) return;
    const newEdits = { ...edits };
    mangas.filter(m => selectedMangaIds.includes(m.id)).forEach(m => {
      newEdits[m.id] = bulkName;
    });
    setEdits(newEdits);
    toast.success(`Nombre aplicado a ${selectedMangaIds.length} mangas localmente`);
  };

  const sortedAndFilteredMangas = useMemo(() => {
    let result = mangas.filter(m => selectedMangaIds.includes(m.id));
    if (searchTerm) {
      const lowerQuery = searchTerm.toLowerCase();
      result = result.filter(m => m.title.toLowerCase().includes(lowerQuery));
    }
    return result.sort((a, b) => a.title.localeCompare(b.title));
  }, [mangas, selectedMangaIds, searchTerm]);

  const handleTitleChange = (id: string, newTitle: string) => {
    setEdits(prev => ({
      ...prev,
      [id]: newTitle
    }));
  };

  const handleSave = async () => {
    const modifications = Object.entries(edits).filter(([id, newTitle]) => {
      const originalManga = mangas.find(m => m.id === id);
      return originalManga && originalManga.title !== newTitle.trim() && newTitle.trim() !== '';
    });

    if (modifications.length === 0) {
      toast.info('No hay cambios para guardar');
      return;
    }

    try {
      setIsSaving(true);
      const updates = modifications.map(([id, title]) => ({ id, title: title.trim() }));
      await updateMangaTitles(updates);
      toast.success(`Se actualizaron ${updates.length} nombres correctamente`);
      onSaveComplete();
      onClose();
    } catch (error) {
      console.error('Error saving titles:', error);
      toast.error('Error al guardar los cambios');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[60] p-4 animate-in fade-in duration-200">
      <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[85vh]">
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10 flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-pink-500/10 rounded-lg text-pink-400">
              <Edit3 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Editar Nombres</h2>
              <p className="text-xs text-gray-400">Edita los títulos de los {selectedMangaIds.length} mangas seleccionados</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-gray-800 bg-[#121212] flex-shrink-0 space-y-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Filtrar manga por título..."
              className="w-full bg-[#1a1a1a] border border-gray-700 rounded-xl pl-10 pr-4 py-3 text-sm text-white focus:outline-none focus:border-pink-500 transition-colors"
            />
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              value={bulkName}
              onChange={(e) => setBulkName(e.target.value)}
              placeholder="Pon un nombre para aplicar a todos los seleccionados (Opcional)"
              className="flex-1 bg-[#1a1a1a] border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-pink-500 transition-colors"
            />
            <button
               onClick={handleApplyBulkName}
               className="bg-gray-800 hover:bg-gray-700 text-white px-6 py-3 rounded-xl text-sm font-medium transition-colors whitespace-nowrap"
            >
               Aplicar a todos
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar">
          {sortedAndFilteredMangas.map((manga) => {
            const originalSrc = manga.cover_url || manga.thumbnail_url;
            const optimizedSrc = originalSrc ? getThumbnailUrl(originalSrc) : undefined;
            return (
            <div key={manga.id} className="flex items-center gap-3 bg-[#1a1a1a] p-3 rounded-lg border border-gray-800/50 hover:border-gray-700 transition-colors">
              {optimizedSrc ? (
                <img 
                  src={optimizedSrc} 
                  alt="" 
                  className="w-10 h-10 rounded object-cover"
                />
              ) : (
                <div className="w-10 h-10 rounded bg-gray-800 flex items-center justify-center">
                  <span className="text-xs text-gray-500 text-center">Sin img</span>
                </div>
              )}
              <div className="flex-1">
                 <input
                   type="text"
                   value={edits[manga.id] !== undefined ? edits[manga.id] : manga.title}
                   onChange={(e) => handleTitleChange(manga.id, e.target.value)}
                   className={`w-full bg-transparent border-b pl-2 py-1 text-sm focus:outline-none transition-colors ${
                     edits[manga.id] !== undefined && edits[manga.id].trim() !== manga.title
                      ? 'border-pink-500 text-pink-300' 
                      : 'border-transparent hover:border-gray-700 text-white focus:border-gray-600'
                   }`}
                   placeholder="Título del manga"
                 />
              </div>
            </div>
            );
          })}
          {sortedAndFilteredMangas.length === 0 && (
            <div className="text-center py-8 text-gray-500">
              No se encontraron mangas con ese nombre en la selección
            </div>
          )}
        </div>

        <div className="bg-[#1a1a1a] border-t border-gray-800 px-6 py-4 flex justify-between items-center sticky bottom-0 flex-shrink-0">
           <span className="text-sm text-gray-400">
             {Object.keys(edits).filter(id => edits[id].trim() !== mangas.find(m => m.id === id)?.title).length} cambios pendientes
           </span>
           <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-semibold text-gray-300 hover:text-white transition-colors"
              disabled={isSaving}
            >
              Cancelar
            </button>
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="bg-pink-600 hover:bg-pink-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg text-sm font-bold shadow-lg shadow-pink-500/20 transition-all flex items-center gap-2"
            >
              {isSaving ? (
                <>
                   <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                   Guardando...
                </>
              ) : (
                <>
                  <Save className="w-4 h-4" />
                  Guardar Cambios
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
