import React, { useState } from 'react';
import { DataItem } from '../types';
import { Trash2, RotateCcw, X, Folder, AlertTriangle, RefreshCw, Layers } from 'lucide-react';
import { restoreItem, restoreAllItems, permanentlyDeleteItem, emptyTrash } from '../services/firebase';

interface TrashModalProps {
  isOpen: boolean;
  onClose: () => void;
  deletedItems: DataItem[];
  allFolders: DataItem[];
}

export const TrashModal: React.FC<TrashModalProps> = ({ isOpen, onClose, deletedItems, allFolders }) => {
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [showConfirmEmpty, setShowConfirmEmpty] = useState(false);

  if (!isOpen) return null;

  // Filter items deleted in the last 30 days
  const THIRTY_DAYS_MS = 30 * 24 * 60 * 60 * 1000;
  const now = Date.now();
  const validDeletedItems = deletedItems.filter(item => {
    if (!item.deletedAt) return true;
    return (now - item.deletedAt) <= THIRTY_DAYS_MS;
  });

  const getFolderName = (parentId?: string | null) => {
    if (!parentId) return 'Raíz';
    const folder = allFolders.find(f => f.id === parentId);
    if (!folder) return 'Carpeta anterior';
    const raw = (folder.title || '').replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ').trim() || folder.title;
    return raw || 'Carpeta anterior';
  };

  const getTimeAgo = (timestamp?: number) => {
    if (!timestamp) return 'Recientemente';
    const diff = now - timestamp;
    const minutes = Math.floor(diff / (1000 * 60));
    const hours = Math.floor(diff / (1000 * 60 * 60));
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days > 0) return `Hace ${days} día${days > 1 ? 's' : ''}`;
    if (hours > 0) return `Hace ${hours} hora${hours > 1 ? 's' : ''}`;
    if (minutes > 0) return `Hace ${minutes} min`;
    return 'Hace un momento';
  };

  const getRemainingDays = (timestamp?: number) => {
    if (!timestamp) return 30;
    const diff = now - timestamp;
    const daysLeft = Math.max(0, 30 - Math.floor(diff / (1000 * 60 * 60 * 24)));
    return daysLeft;
  };

  const handleRestoreOne = async (item: DataItem) => {
    try {
      setLoadingAction(item.id);
      await restoreItem(item.id);
    } catch (e) {
      alert('Error al restaurar el elemento.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRestoreAll = async () => {
    if (validDeletedItems.length === 0) return;
    try {
      setLoadingAction('ALL');
      await restoreAllItems(validDeletedItems.map(i => i.id));
    } catch (e) {
      alert('Error al restaurar todos los elementos.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDeletePermanent = async (item: DataItem) => {
    if (!confirm(`¿Eliminar permanentemente "${item.title.replace(/<[^>]*>?/gm, '')}"? Esta acción no se puede deshacer.`)) return;
    try {
      setLoadingAction(item.id);
      await permanentlyDeleteItem(item.id);
    } catch (e) {
      alert('Error al eliminar el elemento.');
    } finally {
      setLoadingAction(null);
    }
  };

  const handleEmptyTrash = async () => {
    try {
      setLoadingAction('EMPTY');
      await emptyTrash(validDeletedItems.map(i => i.id));
      setShowConfirmEmpty(false);
    } catch (e) {
      alert('Error al vaciar la papelera.');
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200">
      <div className="bg-[#18181b] border border-white/10 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="p-6 border-b border-white/10 flex items-center justify-between bg-white/[0.02]">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400">
              <Trash2 size={24} />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white flex items-center gap-2">
                Papelera de Reciclaje
                <span className="text-xs px-2.5 py-0.5 rounded-full bg-red-500/20 text-red-300 font-semibold border border-red-500/30">
                  {validDeletedItems.length} {validDeletedItems.length === 1 ? 'elemento' : 'elementos'}
                </span>
              </h2>
              <p className="text-sm text-gray-400">
                Los elementos eliminados se conservan por 30 días antes de ser purgados.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-white rounded-lg hover:bg-white/10 transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        {/* Top Control Bar */}
        {validDeletedItems.length > 0 && (
          <div className="px-6 py-3 bg-white/[0.01] border-b border-white/5 flex items-center justify-between flex-wrap gap-3">
            <button
              onClick={handleRestoreAll}
              disabled={loadingAction === 'ALL'}
              className="flex items-center gap-2 px-4 py-2 bg-primary text-background font-semibold rounded-xl hover:bg-primary/90 transition-all shadow-md active:scale-95 disabled:opacity-50"
            >
              <RotateCcw size={16} />
              Restaurar Todo ({validDeletedItems.length})
            </button>

            <button
              onClick={() => setShowConfirmEmpty(true)}
              disabled={loadingAction === 'EMPTY'}
              className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 font-medium rounded-xl transition-all active:scale-95 disabled:opacity-50"
            >
              <Trash2 size={16} />
              Vaciar Papelera
            </button>
          </div>
        )}

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-3">
          {validDeletedItems.length === 0 ? (
            <div className="py-16 text-center flex flex-col items-center justify-center">
              <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center text-gray-500 mb-4 border border-white/5">
                <Trash2 size={32} />
              </div>
              <h3 className="text-lg font-semibold text-white mb-1">La papelera está vacía</h3>
              <p className="text-sm text-gray-400 max-w-sm">
                No hay elementos eliminados en los últimos 30 días. Todos tus archivos y voces se conservan en tus carpetas.
              </p>
            </div>
          ) : (
            validDeletedItems.map(item => {
              const cleanTitle = (item.title || '').replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ') || 'Sin título';
              const isFolder = item.isFolder;
              const folderName = getFolderName(item.parentId);
              const remainingDays = getRemainingDays(item.deletedAt);

              return (
                <div
                  key={item.id}
                  className="p-4 bg-surface hover:bg-white/[0.03] border border-white/5 hover:border-white/10 rounded-xl flex items-center justify-between gap-4 transition-all"
                >
                  <div className="flex items-center gap-3.5 min-w-0 flex-1">
                    <div className={`p-2.5 rounded-lg shrink-0 ${isFolder ? 'bg-primary/10 text-primary' : 'bg-white/5 text-gray-300'}`}>
                      {isFolder ? <Folder size={20} /> : <Layers size={20} />}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h4 className="font-semibold text-white truncate text-base" title={cleanTitle}>
                        {cleanTitle}
                      </h4>
                      <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5 flex-wrap">
                        <span className="flex items-center gap-1 text-gray-400">
                          📁 {folderName}
                        </span>
                        <span>•</span>
                        <span>{getTimeAgo(item.deletedAt)}</span>
                        <span>•</span>
                        <span className="text-amber-400/90 font-medium">
                          Expira en {remainingDays} día{remainingDays !== 1 ? 's' : ''}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Actions for single item */}
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => handleRestoreOne(item)}
                      disabled={loadingAction === item.id}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 rounded-lg font-medium text-xs transition-colors active:scale-95"
                    >
                      <RotateCcw size={14} />
                      Restaurar
                    </button>
                    <button
                      onClick={() => handleDeletePermanent(item)}
                      disabled={loadingAction === item.id}
                      className="p-1.5 text-gray-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                      title="Eliminar permanentemente"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-white/10 bg-white/[0.01] flex items-center justify-between text-xs text-gray-400">
          <span>Sistema de Recuperación Automática (30 días)</span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-surface hover:bg-white/10 text-white rounded-lg transition-colors font-medium text-xs"
          >
            Cerrar
          </button>
        </div>

      </div>

      {/* Confirmation Modal for Empty Trash */}
      {showConfirmEmpty && (
        <div className="fixed inset-0 z-[110] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[#18181b] border border-red-500/30 rounded-xl p-6 max-w-md w-full shadow-2xl animate-in zoom-in-95 duration-200 text-center">
            <div className="w-12 h-12 rounded-full bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center mx-auto mb-4">
              <AlertTriangle size={24} />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">¿Vaciar la papelera?</h3>
            <p className="text-sm text-gray-400 mb-6">
              Esta acción eliminará **permanentemente** todos los {validDeletedItems.length} elementos de la papelera. No podrás recuperarlos después.
            </p>
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={() => setShowConfirmEmpty(false)}
                className="px-4 py-2 bg-surface hover:bg-white/10 text-gray-300 rounded-xl font-medium text-sm transition-colors"
              >
                Cancelar
              </button>
              <button
                onClick={handleEmptyTrash}
                disabled={loadingAction === 'EMPTY'}
                className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-xl font-semibold text-sm transition-all shadow-lg active:scale-95"
              >
                Sí, vaciar permanentemente
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
