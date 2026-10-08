import { useState } from 'react';
import { X, FolderPlus } from 'lucide-react';
import { toast } from 'sonner';
import { createFolderAndMove } from '../services/manga';

interface CreateFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedMangaIds: string[];
  onSaveComplete: () => void;
  currentFolderId?: string | null;
  currentSection: 'flow' | 'patreon' | 'onlyfans' | 'grok';
}

export function CreateFolderModal({ isOpen, onClose, selectedMangaIds, onSaveComplete, currentFolderId, currentSection }: CreateFolderModalProps) {
  const [folderName, setFolderName] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = async () => {
    if (!folderName.trim()) {
      toast.error('Gamba: Escribe un nombre para la carpeta');
      return;
    }

    try {
      setIsSaving(true);
      await createFolderAndMove(folderName.trim(), selectedMangaIds, currentFolderId, currentSection);
      toast.success(`Carpeta "${folderName}" creada exitosamente.`);
      onSaveComplete();
      onClose();
      setFolderName('');
    } catch (error) {
      console.error('Error creating folder:', error);
      toast.error('Error al crear la carpeta');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-[70] p-4 animate-in fade-in duration-200">
      <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-sm shadow-2xl overflow-hidden flex flex-col">
        <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
              <FolderPlus className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Crear Carpeta</h2>
              <p className="text-xs text-gray-400">{selectedMangaIds.length} elementos seleccionados</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6">
          <input
            type="text"
            value={folderName}
            onChange={(e) => setFolderName(e.target.value)}
            placeholder="Nombre de la nueva carpeta"
            className="w-full bg-[#1a1a1a] border border-gray-700 rounded-xl px-4 py-3 text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            autoFocus
          />
        </div>

        <div className="bg-[#1a1a1a] border-t border-gray-800 px-6 py-4 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-semibold text-gray-300 hover:text-white transition-colors"
            disabled={isSaving}
          >
            Cancelar
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving || !folderName.trim()}
            className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg text-sm font-bold shadow-lg shadow-purple-500/20 transition-all flex items-center gap-2"
          >
            {isSaving ? 'Creando...' : 'Crear'}
          </button>
        </div>
      </div>
    </div>
  );
}
