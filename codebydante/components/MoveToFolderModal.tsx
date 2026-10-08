import React, { useState, useMemo } from 'react';
import { Button } from './Button';
import { FolderPlus, Folder, X, Search, MoveUp } from 'lucide-react';
import { DataItem } from '../types';

interface MoveToFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectionCount: number;
  folders: DataItem[];
  currentFolderId: string | null;
  onMoveToFolder: (folderId: string | null) => Promise<void>;
  onCreateFolder: (name: string) => Promise<string>;
}

export const MoveToFolderModal: React.FC<MoveToFolderModalProps> = ({
  isOpen,
  onClose,
  selectionCount,
  folders,
  currentFolderId,
  onMoveToFolder,
  onCreateFolder,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [newFolderName, setNewFolderName] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  // Filter folders to not include the current one if we want to prevent moving to same folder
  // Actually, we can move to any folder.
  // Construir mapa jerárquico recursivo de carpetas o filtrar de forma plana si hay búsqueda
  const filteredFolders = useMemo(() => {
    if (searchQuery.trim() !== '') {
      return folders
        .filter(f => (f.title || '').toLowerCase().includes(searchQuery.toLowerCase()))
        .map(f => ({ folder: f, depth: 0 }));
    }

    const buildTree = (parentId: string | null = null, depth: number = 0, seenIds = new Set<string>()): { folder: DataItem, depth: number }[] => {
      const children = folders.filter(f => (f.parentId || null) === parentId);
      children.sort((a, b) => (a.title || '').localeCompare(b.title || ''));
      
      let result: { folder: DataItem, depth: number }[] = [];
      for (const child of children) {
        if (seenIds.has(child.id)) continue; // Prevent infinite loops
        seenIds.add(child.id);
        result.push({ folder: child, depth });
        result = result.concat(buildTree(child.id, depth + 1, new Set(seenIds)));
      }
      return result;
    };

    return buildTree(null, 0);
  }, [folders, searchQuery]);

  if (!isOpen) return null;

  const handleCreateAndMove = async () => {
    if (!newFolderName.trim() || isProcessing) return;
    setIsProcessing(true);
    try {
      const newFolderId = await onCreateFolder(newFolderName.trim());
      await onMoveToFolder(newFolderId);
      onClose();
    } catch(e) {
      console.error(e);
      alert("Error al crear carpeta");
    } finally {
      setIsProcessing(false);
    }
  };

  const handleMove = async (folderId: string | null) => {
    if (isProcessing) return;
    setIsProcessing(true);
    try {
      await onMoveToFolder(folderId);
      onClose();
    } catch(e) {
      console.error(e);
      alert("Error al mover");
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <>
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />
      
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-[#1a1a1a] shadow-[0_0_50px_rgba(0,0,0,0.5)] z-50 rounded-2xl flex flex-col max-h-[85vh] border border-white/10 animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-white/5">
          <div>
            <h2 className="text-xl font-bold text-white tracking-tight">Mover a...</h2>
            <p className="text-sm text-gray-400 mt-1">{selectionCount} elementos seleccionados</p>
          </div>
          <button 
            onClick={onClose}
            className="p-2 bg-white/5 hover:bg-white/10 rounded-full transition-colors text-gray-400 hover:text-white"
          >
            <X size={20} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 overflow-y-auto flex-1 custom-scrollbar">
          
          {/* Create new folder inline */}
          <div className="bg-surface border border-white/5 rounded-xl p-4 mb-6">
            <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
              <FolderPlus size={16} className="text-primary"/> Nueva Carpeta
            </h3>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="Nombre de la carpeta"
                value={newFolderName}
                onChange={(e) => setNewFolderName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    handleCreateAndMove();
                  }
                }}
                className="flex-1 bg-[#121212] border border-white/10 focus:border-primary rounded-lg px-3 py-2 text-sm outline-none transition-colors"
                disabled={isProcessing}
              />
              <Button 
                onClick={handleCreateAndMove}
                disabled={!newFolderName.trim() || isProcessing}
                className="!py-2 !px-4 whitespace-nowrap"
              >
                Crear y Mover
              </Button>
            </div>
          </div>

          {/* Search folders */}
          <div className="mb-4 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
            <input
              type="text"
              placeholder="Buscar carpeta..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#121212] border border-white/10 focus:border-primary rounded-lg py-2.5 pl-10 pr-4 text-sm outline-none transition-colors"
            />
          </div>

          {/* Folder List */}
          <div className="space-y-2">
            {currentFolderId !== null && !searchQuery && (
               <button
                 onClick={() => handleMove(null)}
                 disabled={isProcessing}
                 className="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-white/5 transition-colors text-left group"
               >
                 <div className="p-2 bg-white/5 rounded-lg text-gray-400 group-hover:text-white transition-colors">
                   <MoveUp size={18} />
                 </div>
                 <span className="font-medium text-gray-300 group-hover:text-white transition-colors">Volver a la Raíz</span>
               </button>
            )}

            {filteredFolders.length === 0 ? (
              <p className="text-center text-sm text-gray-500 py-6">No se encontraron carpetas.</p>
            ) : (
              filteredFolders.map(({ folder, depth }) => (
                <button
                  key={folder.id}
                  onClick={() => handleMove(folder.id)}
                  disabled={isProcessing || folder.id === currentFolderId}
                  className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left group border border-transparent hover:border-white/5 ${
                    folder.id === currentFolderId ? 'opacity-50 cursor-not-allowed bg-white/5' : 'hover:bg-white/5'
                  }`}
                >
                  {/* Espaciador de profundidad para simular el mapa/árbol */}
                  {depth > 0 && (
                    <div style={{ width: `${depth * 20}px` }} className="h-full border-l border-white/10 ml-2" />
                  )}
                  
                  <div className="p-2 bg-primary/10 rounded-lg text-primary">
                    <Folder size={18} />
                  </div>
                  <div className="flex-1 overflow-hidden">
                     <span className="font-medium text-gray-300 group-hover:text-white transition-colors truncate block">
                       {folder.title}
                       {folder.id === currentFolderId && <span className="ml-2 text-xs text-primary font-normal">(Ubicación actual)</span>}
                     </span>
                  </div>
                </button>
              ))
            )}
          </div>
          
        </div>
      </div>
    </>
  );
};
