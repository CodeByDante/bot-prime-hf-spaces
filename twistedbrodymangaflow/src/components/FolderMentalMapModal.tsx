import { X, Network, Folder, Image as ImageIcon } from 'lucide-react';
import { useMemo } from 'react';
import { Manga } from '../types/manga';

interface FolderMentalMapModalProps {
  isOpen: boolean;
  onClose: () => void;
  mangas: Manga[];
}

interface TreeNode {
  item: Manga;
  children: TreeNode[];
}

export function FolderMentalMapModal({ isOpen, onClose, mangas }: FolderMentalMapModalProps) {
  const tree = useMemo(() => {
    // Both folders and comics so we get a full map
    const nodeMap = new Map<string, TreeNode>();
    
    // Initialize nodes
    mangas.forEach(m => {
      nodeMap.set(m.id, { item: m, children: [] });
    });

    const roots: TreeNode[] = [];

    // Build hierarchy
    mangas.forEach(m => {
      const node = nodeMap.get(m.id)!;
      if (m.folder_id && nodeMap.has(m.folder_id)) {
        nodeMap.get(m.folder_id)!.children.push(node);
      } else {
        roots.push(node);
      }
    });

    return roots;
  }, [mangas]);

  if (!isOpen) return null;

  const renderTree = (nodes: TreeNode[], level: number = 0) => {
    if (nodes.length === 0) return null;

    // Sort: Folders first, then alphabetically
    const sortedNodes = [...nodes].sort((a, b) => {
      if (a.item.is_folder && !b.item.is_folder) return -1;
      if (!a.item.is_folder && b.item.is_folder) return 1;
      return a.item.title.localeCompare(b.item.title);
    });

    return (
      <div className="flex flex-col gap-3 relative" style={{ marginLeft: level > 0 ? '2.5rem' : '0' }}>
        {level > 0 && (
          <div className="absolute -left-6 top-0 bottom-6 w-px bg-gray-700/50" />
        )}
        {sortedNodes.map((node, index) => {
          const isLast = index === sortedNodes.length - 1;
          const isRootLevelFolder = level === 0 && node.item.is_folder;
          
          return (
            <div key={node.item.id} className="relative">
              {level > 0 && (
                <div className="absolute -left-6 top-6 w-6 h-px bg-gray-700/50" />
              )}
              {level > 0 && isLast && (
                <div className="absolute -left-6 top-6 bottom-0 w-px bg-[#1a1a1a]" />
              )}
              <div className={`p-4 rounded-xl border flex flex-col gap-3 transition-colors ${
                node.item.is_folder 
                  ? isRootLevelFolder 
                    ? 'bg-purple-900/10 border-purple-500/30' 
                    : 'bg-blue-900/10 border-blue-500/20'
                  : 'bg-gray-800/40 border-gray-700/50'
              }`}>
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${
                    node.item.is_folder 
                      ? isRootLevelFolder ? 'bg-purple-500/20 text-purple-400' : 'bg-blue-500/20 text-blue-400' 
                      : 'bg-emerald-500/10 text-emerald-500'
                  }`}>
                    {node.item.is_folder ? <Folder className="w-5 h-5" /> : <ImageIcon className="w-5 h-5" />}
                  </div>
                  <div className="flex-1">
                    <h4 className="text-sm font-bold text-white whitespace-normal">{node.item.title}</h4>
                    <span className="text-xs text-gray-500">
                      {node.item.is_folder 
                        ? `Carpeta (${node.children.length} elementos)`
                        : `Manga (${node.item.chapters?.length || 0} caps)`}
                    </span>
                  </div>
                </div>
                
                {node.children.length > 0 && (
                  <div className="mt-2">
                    {renderTree(node.children, level + 1)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-[80] p-4 animate-in fade-in duration-200">
      <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-6xl shadow-2xl overflow-hidden flex flex-col h-[90vh]">
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10 flex-shrink-0">
          <div className="flex items-center gap-3">
             <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
              <Network className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Mapa Mental de Organización</h2>
              <p className="text-xs text-gray-400">Vista general de toda tu estructura de carpetas y mangas</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg border border-transparent hover:border-gray-700">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-8 custom-scrollbar relative bg-[url('data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+PGNpcmNsZSBjeD0iMSIgY3k9IjEiIHI9IjEiIGZpbGw9IiMzMzMiLz48L3N2Zz4=')]">
           <div className="max-w-4xl mx-auto">
             {renderTree(tree)}
           </div>
        </div>
      </div>
    </div>
  );
}
