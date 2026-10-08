import { X, Trash2, RefreshCw, Folder } from 'lucide-react';
import { Manga } from '../types/manga';
import { useState } from 'react';
import { toast } from 'sonner';

interface TrashModalProps {
  isOpen: boolean;
  onClose: () => void;
  deletedMangas: Manga[];
  onRestore: (id: string) => Promise<void>;
  onPermanentDelete: (id: string) => Promise<void>;
}

export function TrashModal({ isOpen, onClose, deletedMangas, onRestore, onPermanentDelete }: TrashModalProps) {
  const [loadingIds, setLoadingIds] = useState<Set<string>>(new Set());

  if (!isOpen) return null;

  const handleRestore = async (id: string) => {
    setLoadingIds(prev => new Set(prev).add(id));
    try {
      await onRestore(id);
      toast.success('Elemento restaurado. Sus hijos también fueron recuperados si era una carpeta.');
    } catch (err) {
      toast.error('Error al restaurar elemento');
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  const handlePermanentDelete = async (id: string) => {
    if (!window.confirm('¿ELIMINAR DEFINITIVAMENTE? Esta acción borrará el registro y los capítulos para siempre de la base de datos y no se puede deshacer.')) return;
    setLoadingIds(prev => new Set(prev).add(id));
    try {
      await onPermanentDelete(id);
      toast.success('Elemento purgado de la base de datos.');
    } catch (err) {
      toast.error('Error purgando elemento');
    } finally {
      setLoadingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4 sm:p-6 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-[#121212] rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl border border-gray-800 animate-[scaleIn_0.2s_ease-out] relative overflow-hidden">
        
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-5 border-b border-gray-800/50 bg-[#1a1a1a]">
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-red-500/10 rounded-xl text-red-500">
              <Trash2 className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
                Papelera de Reciclaje
              </h2>
              <p className="text-sm text-gray-400 mt-0.5">Estos elementos están ocultos a los usuarios.</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded-xl transition-colors shrink-0 group right-4 absolute md:relative top-4 md:top-0"
          >
            <X className="w-5 h-5 text-gray-400 group-hover:text-white" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-3 custom-scrollbar">
          {deletedMangas.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-gray-400 opacity-50">
              <Trash2 className="w-16 h-16 mb-4" />
              <p className="text-lg font-medium">La papelera está vacía</p>
            </div>
          ) : (
            deletedMangas.map(item => (
              <div key={item.id} className="flex flex-col sm:flex-row items-center gap-4 bg-gray-900/50 p-3 sm:p-4 rounded-xl border border-gray-800 hover:border-gray-700 transition-colors">
                <div className="w-16 h-16 shrink-0 bg-gray-800 rounded-lg overflow-hidden flex items-center justify-center">
                  {item.thumbnail_url || item.cover_url ? (
                    <img src={item.thumbnail_url || item.cover_url!} alt="" className="w-full h-full object-cover opacity-70 grayscale hover:grayscale-0 transition-all"/>
                  ) : item.is_folder ? (
                    <Folder className="w-8 h-8 text-gray-500" />
                  ) : (
                    <div className="w-6 h-6 bg-gray-700 rounded-sm"></div>
                  )}
                </div>
                
                <div className="flex-1 min-w-0 w-full text-center sm:text-left">
                  <div className="flex items-center gap-2 mb-1 justify-center sm:justify-start">
                    {item.is_folder && <Folder className="w-3.5 h-3.5 text-blue-400" />}
                    <h3 className="font-bold text-white truncate text-sm sm:text-base" title={item.title}>
                      {item.title}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-400 truncate">
                    {item.author || 'Sin autor'} • Eliminado el {new Date(item.updated_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center gap-2 w-full sm:w-auto">
                  <button
                    onClick={() => handleRestore(item.id)}
                    disabled={loadingIds.has(item.id)}
                    className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    Restaurar
                  </button>
                  <button
                    onClick={() => handlePermanentDelete(item.id)}
                    disabled={loadingIds.has(item.id)}
                    className="flex-1 sm:flex-none flex items-center justify-center gap-1.5 px-3 py-2 bg-red-500/10 hover:bg-red-500/20 text-red-500 rounded-lg text-xs font-semibold transition-colors disabled:opacity-50"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    Purgar
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
