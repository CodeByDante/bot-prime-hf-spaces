import { useState } from 'react';
import { X, ExternalLink } from 'lucide-react';
import { toast } from 'sonner';
import { moveMangasToSection } from '../services/manga';
import { PatreonIcon } from './PatreonIcon';
import { OnlyFansIcon } from './OnlyFansIcon';
import { GrokIcon } from './GrokIcon';
import { Layers } from 'lucide-react';

interface MoveSectionModalProps {
  isOpen: boolean;
  onClose: () => void;
  selectedMangaIds: string[];
  onSaveComplete: () => void;
  currentSection: 'flow' | 'patreon' | 'onlyfans' | 'grok';
}

export function MoveSectionModal({ isOpen, onClose, selectedMangaIds, onSaveComplete, currentSection }: MoveSectionModalProps) {
  const [targetSection, setTargetSection] = useState<'flow' | 'patreon' | 'onlyfans' | 'grok'>(currentSection === 'flow' ? 'patreon' : 'flow');
  const [isSaving, setIsSaving] = useState(false);

  const handleMove = async () => {
    if (targetSection === currentSection) {
      toast.error('Gamba: Ya estás en esta sección');
      return;
    }

    try {
      setIsSaving(true);
      await moveMangasToSection(selectedMangaIds, targetSection);
      let targetName = 'Flow';
      if (targetSection === 'patreon') targetName = 'Patreon';
      if (targetSection === 'onlyfans') targetName = 'OnlyFans';
      if (targetSection === 'grok') targetName = 'Grok';
      toast.success(`${selectedMangaIds.length} elementos movidos a ${targetName}`);
      onSaveComplete();
      onClose();
    } catch (error) {
      console.error('Error moving section:', error);
      toast.error('Error al mover los elementos de sección');
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
            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
              <ExternalLink className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">Mover a Sección</h2>
              <p className="text-xs text-gray-400">{selectedMangaIds.length} elementos seleccionados</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-4">
          <p className="text-sm text-gray-300 text-center mb-4">¿A qué sección deseas enviar estos elementos?</p>
          
          <button
            onClick={() => setTargetSection('flow')}
            disabled={currentSection === 'flow'}
            className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
              currentSection === 'flow'
                ? 'border-gray-800 bg-[#121212] opacity-50 cursor-not-allowed'
                : targetSection === 'flow'
                  ? 'border-[#bb86fc] bg-[#bb86fc]/10 text-white'
                  : 'border-gray-700 bg-[#1a1a1a] text-gray-400 hover:border-gray-500'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${currentSection === 'flow' ? 'bg-gray-800 text-gray-500' : targetSection === 'flow' ? 'bg-[#bb86fc]/20 text-[#bb86fc]' : 'bg-gray-800 text-gray-400'}`}>
                <Layers className="w-5 h-5" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-sm">Flow</h3>
                <p className="text-xs opacity-70">Galería principal</p>
              </div>
            </div>
            {currentSection === 'flow' && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-gray-800 text-gray-400">Actual</span>
            )}
          </button>

          <button
            onClick={() => setTargetSection('patreon')}
            disabled={currentSection === 'patreon'}
            className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
              currentSection === 'patreon'
                ? 'border-gray-800 bg-[#121212] opacity-50 cursor-not-allowed'
                : targetSection === 'patreon'
                  ? 'border-[#f96854] bg-[#f96854]/10 text-white'
                  : 'border-gray-700 bg-[#1a1a1a] text-gray-400 hover:border-gray-500'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${currentSection === 'patreon' ? 'bg-gray-800 text-gray-500' : targetSection === 'patreon' ? 'bg-[#f96854]/20 text-[#f96854]' : 'bg-gray-800 text-gray-400'}`}>
                <PatreonIcon className="w-5 h-5" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-sm">Patreon</h3>
                <p className="text-xs opacity-70">Contenido exclusivo</p>
              </div>
            </div>
            {currentSection === 'patreon' && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-gray-800 text-gray-400">Actual</span>
            )}
          </button>

          <button
            onClick={() => setTargetSection('onlyfans')}
            disabled={currentSection === 'onlyfans'}
            className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
              currentSection === 'onlyfans'
                ? 'border-gray-800 bg-[#121212] opacity-50 cursor-not-allowed'
                : targetSection === 'onlyfans'
                  ? 'border-[#00AFF0] bg-[#00AFF0]/10 text-white'
                  : 'border-gray-700 bg-[#1a1a1a] text-gray-400 hover:border-gray-500'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${currentSection === 'onlyfans' ? 'bg-gray-800 text-gray-500' : targetSection === 'onlyfans' ? 'bg-[#00AFF0]/20 text-[#00AFF0]' : 'bg-gray-800 text-gray-400'}`}>
                <OnlyFansIcon className="w-5 h-5" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-sm">OnlyFans</h3>
                <p className="text-xs opacity-70">Contenido premium</p>
              </div>
            </div>
            {currentSection === 'onlyfans' && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-gray-800 text-gray-400">Actual</span>
            )}
          </button>

          <button
            onClick={() => setTargetSection('grok')}
            disabled={currentSection === 'grok'}
            className={`w-full flex items-center justify-between p-4 rounded-xl border transition-all ${
              currentSection === 'grok'
                ? 'border-gray-800 bg-[#121212] opacity-50 cursor-not-allowed'
                : targetSection === 'grok'
                  ? 'border-[#1D9BF0] bg-[#1D9BF0]/10 text-white'
                  : 'border-gray-700 bg-[#1a1a1a] text-gray-400 hover:border-gray-500'
            }`}
          >
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${currentSection === 'grok' ? 'bg-gray-800 text-gray-500' : targetSection === 'grok' ? 'bg-[#1D9BF0]/20 text-[#1D9BF0]' : 'bg-gray-800 text-gray-400'}`}>
                <GrokIcon className="w-5 h-5" />
              </div>
              <div className="text-left">
                <h3 className="font-semibold text-sm">Grok</h3>
                <p className="text-xs opacity-70">Contenido IA</p>
              </div>
            </div>
            {currentSection === 'grok' && (
              <span className="text-xs font-bold px-2 py-1 rounded bg-gray-800 text-gray-400">Actual</span>
            )}
          </button>

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
            onClick={handleMove}
            disabled={isSaving || targetSection === currentSection}
            className="bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed text-white px-6 py-2 rounded-lg text-sm font-bold shadow-lg shadow-indigo-500/20 transition-all flex items-center gap-2"
          >
            {isSaving ? 'Moviendo...' : 'Mover'}
          </button>
        </div>
      </div>
    </div>
  );
}
