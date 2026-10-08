import { useState } from 'react';
import { Menu, X, Layers } from 'lucide-react';
import { PatreonIcon } from './PatreonIcon';
import { OnlyFansIcon } from './OnlyFansIcon';
import { GrokIcon } from './GrokIcon';

interface NavigationDrawerProps {
  currentSection: 'flow' | 'patreon' | 'onlyfans' | 'grok' | 'favorites';
  onSectionChange: (section: 'flow' | 'patreon' | 'onlyfans' | 'grok' | 'favorites') => void;
}

export function NavigationDrawer({ currentSection, onSectionChange }: NavigationDrawerProps) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      <button onClick={() => setIsOpen(true)} className="p-2 sm:p-2.5 hover:bg-white/10 rounded-full text-white transition-colors flex-shrink-0">
        <Menu className="w-5 h-5 sm:w-6 sm:h-6" />
      </button>

      {/* Drawer Overlay */}
      <div 
        className={`fixed inset-0 bg-black/70 z-[45] transition-opacity duration-300 ${isOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}
        onClick={() => setIsOpen(false)}
      />

      {/* Drawer Sidebar */}
      <div className={`fixed inset-y-0 left-0 w-72 bg-[#1a1a1a] shadow-2xl border-r border-[#333] z-50 transform transition-transform duration-300 ease-out will-change-transform ${isOpen ? 'translate-x-0' : '-translate-x-full'}`}>
        <div className="p-4 sm:p-6 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src="/icons/icones.png" alt="Logo" className="w-8 h-8 sm:w-10 sm:h-10 object-contain" />
            <span className="font-bold text-white text-lg">Twisted Brody</span>
          </div>
          <button onClick={() => setIsOpen(false)} className="p-2 text-gray-400 hover:text-white rounded-full hover:bg-white/10 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-4 flex flex-col gap-2">
          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2 px-2">
            Navegación principal
          </div>
          <button 
            onClick={() => {
              onSectionChange('flow');
              setIsOpen(false);
            }}
            className={`flex items-center gap-3 w-full p-3 rounded-xl font-semibold transition-all active:scale-95 ${
              currentSection === 'flow'
                ? 'bg-[#bb86fc]/10 text-[#bb86fc] border border-[#bb86fc]/20 hover:bg-[#bb86fc]/20'
                : 'text-gray-300 hover:bg-white/5 border border-transparent'
            }`}
          >
            <Layers className="w-5 h-5" />
            Flow
          </button>

          <button 
            onClick={() => {
              onSectionChange('patreon');
              setIsOpen(false);
            }}
            className={`flex items-center gap-3 w-full p-3 rounded-xl font-semibold transition-all active:scale-95 ${
              currentSection === 'patreon'
                ? 'bg-[#f96854]/10 text-[#f96854] border border-[#f96854]/20 hover:bg-[#f96854]/20'
                : 'text-gray-300 hover:bg-white/5 border border-transparent'
            }`}
          >
            <PatreonIcon className="w-5 h-5" />
            Patreon
          </button>

          <button 
            onClick={() => {
              onSectionChange('onlyfans');
              setIsOpen(false);
            }}
            className={`flex items-center gap-3 w-full p-3 rounded-xl font-semibold transition-all active:scale-95 ${
              currentSection === 'onlyfans'
                ? 'bg-[#00AFF0]/10 text-[#00AFF0] border border-[#00AFF0]/20 hover:bg-[#00AFF0]/20'
                : 'text-gray-300 hover:bg-white/5 border border-transparent'
            }`}
          >
            <OnlyFansIcon className="w-5 h-5" />
            OnlyFans
          </button>

          <button 
            onClick={() => {
              onSectionChange('grok');
              setIsOpen(false);
            }}
            className={`flex items-center gap-3 w-full p-3 rounded-xl font-semibold transition-all active:scale-95 ${
              currentSection === 'grok'
                ? 'bg-[#1D9BF0]/10 text-[#1D9BF0] border border-[#1D9BF0]/20 hover:bg-[#1D9BF0]/20'
                : 'text-gray-300 hover:bg-white/5 border border-transparent'
            }`}
          >
            <GrokIcon className="w-5 h-5" />
            Grok
          </button>

          <div className="text-xs font-semibold text-gray-500 uppercase tracking-wider mt-4 mb-2 px-2">
            Personal
          </div>
          <button 
            onClick={() => {
              onSectionChange('favorites');
              setIsOpen(false);
            }}
            className={`flex items-center gap-3 w-full p-3 rounded-xl font-semibold transition-all active:scale-95 ${
              currentSection === 'favorites'
                ? 'bg-[#ff4b4b]/10 text-[#ff4b4b] border border-[#ff4b4b]/20 hover:bg-[#ff4b4b]/20'
                : 'text-gray-300 hover:bg-white/5 border border-transparent'
            }`}
          >
            <svg className="w-5 h-5" fill={currentSection === 'favorites' ? 'currentColor' : 'none'} viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
            </svg>
            Favoritos
          </button>
        </div>
      </div>
    </>
  );
}
