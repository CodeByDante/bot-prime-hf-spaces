import { X, Search, Check, Filter } from 'lucide-react';
import { useState, useMemo } from 'react';
import { Category } from '../types/manga';

interface CategoryFilterModalProps {
    isOpen: boolean;
    onClose: () => void;
    categories: Category[];
    selectedCategories: string[];
    onToggleCategory: (categoryName: string) => void;
    onClearFilters: () => void;
    filterDecensored: boolean;
    setFilterDecensored: (val: boolean) => void;
    filterBN: boolean;
    setFilterBN: (val: boolean) => void;
    filterColor: boolean;
    setFilterColor: (val: boolean) => void;
}

const CATEGORY_TYPE_ORDER = ['series', 'character', 'genre', 'tag', 'other'];
const TYPE_LABELS: Record<string, string> = {
    series: 'Series',
    character: 'Personajes',
    genre: 'Géneros',
    tag: 'Etiquetas',
    other: 'Otros',
};

export function CategoryFilterModal({
    isOpen,
    onClose,
    categories,
    selectedCategories,
    onToggleCategory,
    onClearFilters,
    filterDecensored,
    setFilterDecensored,
    filterBN,
    setFilterBN,
    filterColor,
    setFilterColor,
}: CategoryFilterModalProps) {
    const [searchTerm, setSearchTerm] = useState('');

    const groupedCategories = useMemo(() => {
        const filtered = categories.filter(c =>
            c.name.toLowerCase().includes(searchTerm.toLowerCase())
        );

        const groups: Record<string, Category[]> = {};

        // Initialize groups
        CATEGORY_TYPE_ORDER.forEach(type => {
            groups[type] = [];
        });
        groups['other'] = []; // Ensure 'other' exists

        filtered.forEach(cat => {
            const type = cat.type || 'other';
            if (!groups[type]) {
                groups[type] = [];
            }
            groups[type].push(cat);
        });

        return groups;
    }, [categories, searchTerm]);

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div
                className="bg-[#1a1a1a] w-full max-w-4xl max-h-[85vh] rounded-2xl border border-gray-800 shadow-2xl flex flex-col overflow-hidden animate-in zoom-in-95 duration-200"
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-4 sm:p-6 border-b border-gray-800 flex items-center justify-between bg-[#1a1a1a]">
                    <div className="flex items-center gap-3">
                        <div className="bg-purple-500/20 p-2 rounded-lg">
                            <Filter className="w-5 h-5 text-purple-400" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-white">Filtrar por Categorías</h2>
                            <p className="text-sm text-gray-400">Selecciona múltiples opciones para refinar tu búsqueda</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white hover:bg-gray-800 p-2 rounded-lg transition-all"
                    >
                        <X className="w-5 h-5" />
                    </button>
                </div>

                {/* Search Bar */}
                <div className="p-4 border-b border-gray-800 bg-[#151515]">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Buscar categorías..."
                            value={searchTerm}
                            onChange={(e) => setSearchTerm(e.target.value)}
                            className="w-full bg-[#0f0f0f] border border-gray-700/50 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all"
                        />
                    </div>
                </div>

                {/* Categories Content */}
                <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-8 custom-scrollbar">
                    {/* Special Filters */}
                    <div className="animate-in slide-in-from-bottom-2 duration-300">
                        <h3 className="text-sm font-bold text-purple-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                            <span className="w-1 h-4 bg-purple-500 rounded-full"></span>
                            Propiedades Especiales
                        </h3>
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-8">
                            <button
                                onClick={() => setFilterDecensored(!filterDecensored)}
                                className={`relative group flex flex-col p-3 rounded-lg text-left transition-all duration-200 border ${filterDecensored ? 'bg-purple-500/20 border-purple-500/50 shadow-[0_0_15px_-3px_rgba(168,85,247,0.3)]' : 'bg-[#252525] border-transparent hover:bg-[#2a2a2a] hover:border-gray-700'}`}
                            >
                                <div className="flex items-center justify-between w-full mb-1">
                                    <span className="font-bold text-white text-sm">Sin censura</span>
                                    <div className={`w-8 h-4 rounded-full transition-colors ${filterDecensored ? 'bg-purple-500' : 'bg-gray-600'} relative`}>
                                        <div className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200 ${filterDecensored ? 'translate-x-4' : 'translate-x-0'}`} />
                                    </div>
                                </div>
                                <span className="text-xs text-gray-400">Mostrar solo contenido sin censura</span>
                            </button>

                            <button
                                onClick={() => setFilterBN(!filterBN)}
                                className={`relative group flex flex-col p-3 rounded-lg text-left transition-all duration-200 border ${filterBN ? 'bg-purple-500/20 border-purple-500/50 shadow-[0_0_15px_-3px_rgba(168,85,247,0.3)]' : 'bg-[#252525] border-transparent hover:bg-[#2a2a2a] hover:border-gray-700'}`}
                            >
                                <div className="flex items-center justify-between w-full mb-1">
                                    <span className="font-bold text-white text-sm">B/N</span>
                                    <div className={`w-8 h-4 rounded-full transition-colors ${filterBN ? 'bg-purple-500' : 'bg-gray-600'} relative`}>
                                        <div className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200 ${filterBN ? 'translate-x-4' : 'translate-x-0'}`} />
                                    </div>
                                </div>
                                <span className="text-xs text-gray-400">Mostrar solo Blanco y Negro</span>
                            </button>

                            <button
                                onClick={() => setFilterColor(!filterColor)}
                                className={`relative group flex flex-col p-3 rounded-lg text-left transition-all duration-200 border ${filterColor ? 'bg-purple-500/20 border-purple-500/50 shadow-[0_0_15px_-3px_rgba(168,85,247,0.3)]' : 'bg-[#252525] border-transparent hover:bg-[#2a2a2a] hover:border-gray-700'}`}
                            >
                                <div className="flex items-center justify-between w-full mb-1">
                                    <span className="font-bold text-white text-sm">A color</span>
                                    <div className={`w-8 h-4 rounded-full transition-colors ${filterColor ? 'bg-purple-500' : 'bg-gray-600'} relative`}>
                                        <div className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform duration-200 ${filterColor ? 'translate-x-4' : 'translate-x-0'}`} />
                                    </div>
                                </div>
                                <span className="text-xs text-gray-400">Mostrar solo contenido a color</span>
                            </button>
                        </div>
                    </div>

                    {CATEGORY_TYPE_ORDER.map((type) => {
                        const groupCategories = groupedCategories[type];
                        if (!groupCategories || groupCategories.length === 0) return null;

                        return (
                            <div key={type} className="animate-in slide-in-from-bottom-2 duration-300">
                                <h3 className="text-sm font-bold text-purple-400 uppercase tracking-wider mb-3 flex items-center gap-2">
                                    <span className="w-1 h-4 bg-purple-500 rounded-full"></span>
                                    {TYPE_LABELS[type] || type}
                                </h3>
                                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2">
                                    {groupCategories.sort((a, b) => a.name.localeCompare(b.name)).map((category) => {
                                        const isSelected = selectedCategories.includes(category.name);
                                        return (
                                            <button
                                                key={category.id}
                                                onClick={() => onToggleCategory(category.name)}
                                                className={`
                          relative group flex items-center justify-between px-3 py-2 rounded-lg text-sm text-left transition-all duration-200 border
                          ${isSelected
                                                        ? 'bg-purple-500/20 border-purple-500/50 text-purple-100 shadow-[0_0_15px_-3px_rgba(168,85,247,0.3)]'
                                                        : 'bg-[#252525] border-transparent text-gray-300 hover:bg-[#2a2a2a] hover:border-gray-700'
                                                    }
                        `}
                                            >
                                                <span className="truncate mr-2 font-medium">{category.name}</span>
                                                {isSelected && (
                                                    <div className="bg-purple-500 rounded-full p-0.5 animate-in zoom-in duration-200">
                                                        <Check className="w-3 h-3 text-white" />
                                                    </div>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}

                    {/* Show message if no results logic could be added here if needed */}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-800 bg-[#1a1a1a] flex items-center justify-between">
                    <div className="text-sm text-gray-400">
                        {selectedCategories.length + (filterDecensored ? 1 : 0) + (filterBN ? 1 : 0) + (filterColor ? 1 : 0)} filtros activos
                    </div>
                    <div className="flex items-center gap-3">
                        {(selectedCategories.length > 0 || filterDecensored || filterBN || filterColor) && (
                            <button
                                onClick={onClearFilters}
                                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
                            >
                                Limpiar todo
                            </button>
                        )}
                        <button
                            onClick={onClose}
                            className="px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg text-sm font-semibold shadow-lg shadow-purple-900/20 transition-all hover:scale-105 active:scale-95"
                        >
                            Listo
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
