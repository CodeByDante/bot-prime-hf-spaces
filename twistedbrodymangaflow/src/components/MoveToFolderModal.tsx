import { useState, useMemo } from 'react';
import { X, FolderInput, Search, Trash2, ChevronRight, ChevronDown } from 'lucide-react';
import { toast } from 'sonner';
import { moveToFolder, deleteManga } from '../services/manga';
import { Manga } from '../types/manga';

interface MoveToFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedMangaIds: string[];
  mangas: Manga[];
  onSaveComplete: () => void;
}

export function MoveToFolderModal({ isOpen, onClose, selectedMangaIds, mangas, onSaveComplete }: MoveToFolderModalProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [folderToDelete, setFolderToDelete] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());

  const toggleExpand = (e: React.MouseEvent, folderId: string) => {
    e.stopPropagation();
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(folderId)) {
        next.delete(folderId);
      } else {
        next.add(folderId);
      }
      return next;
    });
  };

  const folderTree = useMemo(() => {
    const allAvailableFolders = mangas.filter(
      (m) => m.is_folder && !selectedMangaIds.includes(m.id)
    );

    interface FolderNode {
      folder: Manga;
      children: FolderNode[];
    }

    const nodeMap = new Map<string, FolderNode>();
    allAvailableFolders.forEach((f) => {
      nodeMap.set(f.id, { folder: f, children: [] });
    });

    const roots: FolderNode[] = [];
    
    allAvailableFolders.forEach((f) => {
      const node = nodeMap.get(f.id)!;
      if (f.folder_id && nodeMap.has(f.folder_id)) {
        nodeMap.get(f.folder_id)!.children.push(node);
      } else {
        roots.push(node);
      }
    });

    const sortNodes = (nodes: FolderNode[]) => {
      nodes.sort((a, b) => a.folder.title.localeCompare(b.folder.title));
      nodes.forEach((n) => sortNodes(n.children));
    };

    sortNodes(roots);
    return roots;
  }, [mangas, selectedMangaIds]);

  const visibleFolders = useMemo(() => {
    const result: { folder: Manga; level: number; hasChildren: boolean }[] = [];
    const searchLower = searchTerm.toLowerCase();

    const nodeMatchesSearch = (node: { folder: Manga; children: any[] }): boolean => {
      if (!searchLower) return true;
      if (node.folder.title.toLowerCase().includes(searchLower)) return true;
      return node.children.some(nodeMatchesSearch);
    };

    const traverse = (nodes: { folder: Manga; children: any[] }[], level: number, forceExpand: boolean) => {
      nodes.forEach((node) => {
        const matches = nodeMatchesSearch(node);
        if (matches) {
          result.push({
            folder: node.folder,
            level,
            hasChildren: node.children.length > 0,
          });

          const isExpanded = forceExpand || expandedFolders.has(node.folder.id);
          if (node.children.length > 0 && isExpanded) {
             traverse(node.children, level + 1, forceExpand);
          }
        }
      });
    };

    traverse(folderTree, 0, !!searchLower);
    return result;
  }, [folderTree, expandedFolders, searchTerm]);

  const handleMove = async (folderId: string | null) => {
    try {
      setIsSaving(true);

      const selectedFolderIds = new Set(
        mangas.filter(m => selectedMangaIds.includes(m.id) && m.is_folder).map(f => f.id)
      );

      const isDescendantOfSelectedFolder = (mangaId: string): boolean => {
        let current = mangas.find(m => m.id === mangaId)?.folder_id;
        let depth = 0;
        while (current && depth < 20) {
          if (selectedFolderIds.has(current)) {
            return true;
          }
          current = mangas.find(m => m.id === current)?.folder_id;
          depth++;
        }
        return false;
      };

      const topLevelIdsToMove = selectedMangaIds.filter(id => !isDescendantOfSelectedFolder(id));

      await moveToFolder(topLevelIdsToMove, folderId);
      if (folderId) {
        toast.success(`Movido exitosamente a la carpeta.`);
      } else {
        toast.success(`Removido de la carpeta exitosamente.`);
      }
      onSaveComplete();
      onClose();
    } catch (error) {
      console.error('Error moving to folder:', error);
      toast.error('Error al mover a la carpeta');
    } finally {
      setIsSaving(false);
    }
  };

  const executeDeleteFolder = async (folderId: string) => {
    try {
      setIsSaving(true);
      await deleteManga(folderId);
      toast.success('Carpeta eliminada correctamente');
      setFolderToDelete(null);
      onSaveComplete();
    } catch (error) {
      console.error('Error deleting folder:', error);
      toast.error('Error al eliminar la carpeta');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[70] p-4 animate-in fade-in duration-200">
      <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] min-h-[60vh]">
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10 flex-shrink-0">
          <div className="flex items-center gap-3">
             <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
              <FolderInput className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Mover a Carpeta</h2>
              <p className="text-xs text-gray-400">Selecciona la carpeta de destino</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-4 border-b border-gray-800 bg-[#121212] flex-shrink-0">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Buscar carpeta..."
              className="w-full bg-[#1a1a1a] border border-gray-700 rounded-xl pl-10 pr-4 py-3 text-sm text-white focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2 custom-scrollbar overscroll-contain" style={{ contain: 'content' }}>
          <button
             onClick={() => handleMove(null)}
             disabled={isSaving}
             className="w-full flex items-center gap-3 p-3 rounded-xl border border-dashed border-gray-700 hover:border-blue-500 hover:bg-blue-500/5 transition-colors text-left group"
          >
             <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center group-hover:bg-blue-500/20 transition-colors">
               <span className="text-lg">🏠</span>
             </div>
             <div className="flex-1">
               <h3 className="text-sm font-semibold text-white">Raíz (Pantalla principal)</h3>
               <p className="text-xs text-gray-400 border-gray-700">Sacar de cualquier carpeta</p>
             </div>
          </button>
          
          <div className="h-px bg-gray-800 my-4" />

          {visibleFolders.map(({ folder, level, hasChildren }) => {
             const isExpanded = !!searchTerm || expandedFolders.has(folder.id);
             return (
               <div
                 key={folder.id}
                 className="w-full flex items-center gap-2"
                 style={{ contentVisibility: 'auto', containIntrinsicSize: '0 64px' }}
               >
                 <div style={{ width: `${level * 1.5}rem` }} className="flex-shrink-0" />
                 <div className="w-6 flex items-center justify-center flex-shrink-0">
                   {hasChildren && (
                     <button
                       onClick={(e) => toggleExpand(e, folder.id)}
                       className="p-1 rounded hover:bg-gray-700 text-gray-400 hover:text-white transition-colors"
                     >
                       {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                     </button>
                   )}
                 </div>
                 <button
                   onClick={() => handleMove(folder.id)}
                   disabled={isSaving}
                   className="flex-1 flex items-center gap-3 p-3 rounded-xl border border-gray-800 bg-[#1a1a1a] hover:border-blue-500 transition-colors text-left group"
                 >
                   <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center overflow-hidden flex-shrink-0">
                      <FolderInput className="w-5 h-5 text-gray-400 group-hover:text-blue-400 transition-colors" />
                   </div>
                   <div className="flex-1 min-w-0">
                     <h3 className="text-sm font-semibold text-white group-hover:text-blue-400 transition-colors truncate">{folder.title}</h3>
                     <p className="text-xs text-gray-400">Carpeta</p>
                   </div>
                 </button>
                 <button
                   onClick={(e) => {
                     e.stopPropagation();
                     setFolderToDelete(folder.id);
                   }}
                   disabled={isSaving}
                   className="p-3 rounded-xl border border-gray-800 bg-[#1a1a1a] hover:bg-red-600 hover:border-red-500 transition-colors text-gray-400 hover:text-white flex items-center justify-center flex-shrink-0"
                   title="Eliminar carpeta"
                 >
                   <Trash2 className="w-5 h-5" />
                 </button>
               </div>
             );
          })}

          {visibleFolders.length === 0 && (
             <div className="text-center py-8 text-gray-500">
                No hay carpetas disponibles
             </div>
          )}
        </div>

        {folderToDelete && (
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center gap-4 rounded-2xl z-[80] animate-in fade-in duration-200">
            <p className="text-white text-base font-semibold text-center px-6">
              ¿Seguro que deseas eliminar esta carpeta?<br/>
              <span className="text-gray-400 text-sm font-normal mt-2 block">
                Los cómics dentro de ella volverán a la vista principal.
              </span>
            </p>
            <div className="flex gap-3">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setFolderToDelete(null);
                }}
                disabled={isSaving}
                className="bg-gray-700 hover:bg-gray-600 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 transform hover:scale-105 active:scale-95"
              >
                Cancelar
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  executeDeleteFolder(folderToDelete);
                }}
                disabled={isSaving}
                className="bg-red-600 hover:bg-red-700 text-white px-5 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200 transform hover:scale-105 active:scale-95"
              >
                {isSaving ? 'Eliminando...' : 'Eliminar'}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
