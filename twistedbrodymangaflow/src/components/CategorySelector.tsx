import { useState, useRef, useEffect, useMemo } from 'react';
import { toast } from 'sonner';
import { X, Plus, Trash2, Check } from 'lucide-react';
import { Category } from '../types/manga';

interface CategorySelectorProps {
    label: string;
    type: 'character' | 'series' | 'genre' | 'tag';
    categories: Category[];
    selectedIds: string[];
    onSelect: (id: string) => void;
    onRemove: (id: string) => void;
    onCreate: (name: string) => void;
    onDeleteCategory: (id: string) => void;
    colorClass: string; // e.g., 'text-blue-400', 'bg-blue-500'
    placeholder?: string;
}

export function CategorySelector({
    label,
    type,
    categories,
    selectedIds,
    onSelect,
    onRemove,
    onCreate,
    onDeleteCategory,
    colorClass,
    placeholder = 'Añadir...'
}: CategorySelectorProps) {
    const [inputValue, setInputValue] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Filter categories by type
    const typeCategories = useMemo(() =>
        categories.filter(c => c.type === type || (!c.type && type === 'genre')),
        [categories, type]);

    // Filter suggestions based on input
    const suggestions = useMemo(() => {
        if (!inputValue.trim()) return typeCategories;
        return typeCategories.filter(c =>
            c.name.toLowerCase().includes(inputValue.toLowerCase())
        );
    }, [typeCategories, inputValue]);

    // Handle click outside to close dropdown
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            handleAction();
        }
    };

    const handleAction = () => {
        if (!inputValue.trim()) return;

        // Check for exact match (case insensitive)
        const existing = typeCategories.find(
            c => c.name.toLowerCase() === inputValue.trim().toLowerCase()
        );

        if (existing) {
            if (!selectedIds.includes(existing.id)) {
                onSelect(existing.id);
            }
        } else {
            onCreate(inputValue.trim());
        }
        setInputValue('');
        setIsOpen(false);
    };

    const handleDeleteClick = (e: React.MouseEvent, catId: string) => {
        e.stopPropagation();
        toast('¿Eliminar esta categoría permanentemente?', {
            description: 'Esta acción no se puede deshacer.',
            action: {
                label: 'Eliminar',
                onClick: () => onDeleteCategory(catId),
            },
            cancel: {
                label: 'Cancelar',
                onClick: () => { },
            },
            duration: 5000,
        });
    };

    // Get color classes
    const getColors = () => {
        if (colorClass.includes('blue')) return { bg: 'bg-blue-500/20', text: 'text-blue-300', border: 'border-blue-500/30' };
        if (colorClass.includes('green')) return { bg: 'bg-green-500/20', text: 'text-green-300', border: 'border-green-500/30' };
        if (colorClass.includes('purple')) return { bg: 'bg-purple-500/20', text: 'text-purple-300', border: 'border-purple-500/30' };
        if (colorClass.includes('pink')) return { bg: 'bg-pink-500/20', text: 'text-pink-300', border: 'border-pink-500/30' };
        return { bg: 'bg-gray-500/20', text: 'text-gray-300', border: 'border-gray-500/30' };
    };

    const colors = getColors();

    return (
        <div className="space-y-3 mb-6" ref={containerRef}>
            <label className={`text-xs uppercase font-bold tracking-wider ${colorClass}`}>{label}</label>

            <div className="relative">
                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => {
                                setInputValue(e.target.value);
                                setIsOpen(true);
                            }}
                            onFocus={() => setIsOpen(true)}
                            onKeyDown={handleKeyDown}
                            placeholder={placeholder}
                            className="w-full bg-[#1a1a1a] border border-gray-600/50 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#bb86fc] transition-all"
                        />
                        {inputValue && (
                            <button
                                onClick={() => setInputValue('')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                            >
                                <X className="w-3 h-3" />
                            </button>
                        )}
                    </div>
                    <button
                        onClick={handleAction}
                        disabled={!inputValue.trim()}
                        className="bg-[#bb86fc]/20 hover:bg-[#bb86fc]/30 text-[#bb86fc] px-3 rounded-lg transition-all"
                    >
                        <Plus className="w-5 h-5" />
                    </button>
                </div>

                {/* Dropdown Suggestions */}
                {isOpen && (suggestions.length > 0 || inputValue) && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-[#1a1a1a] border border-gray-700/50 rounded-lg shadow-xl z-50 max-h-60 overflow-y-auto w-full custom-scrollbar">
                        {suggestions.length > 0 ? (
                            suggestions.map(cat => {
                                const isSelected = selectedIds.includes(cat.id);
                                return (
                                    <div
                                        key={cat.id}
                                        className="flex items-center justify-between px-4 py-2 hover:bg-white/5 cursor-pointer group"
                                        onClick={() => {
                                            if (!isSelected) {
                                                onSelect(cat.id);
                                                setInputValue('');
                                                setIsOpen(false);
                                            }
                                        }}
                                    >
                                        <span className={`text-sm ${isSelected ? 'text-[#bb86fc]' : 'text-gray-300'}`}>
                                            {cat.name}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            {isSelected && <Check className="w-4 h-4 text-[#bb86fc]" />}
                                            <button
                                                onClick={(e) => handleDeleteClick(e, cat.id)}
                                                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 text-gray-500 hover:text-red-400 rounded transition-all"
                                                title="Eliminar permanentemente"
                                            >
                                                <Trash2 className="w-3.5 h-3.5" />
                                            </button>
                                        </div>
                                    </div>
                                );
                            })
                        ) : (
                            <div className="px-4 py-3 text-center">
                                <p className="text-gray-400 text-xs mb-2">No encontrado.</p>
                                <button
                                    onClick={handleAction}
                                    className="text-xs text-[#bb86fc] hover:underline font-semibold"
                                >
                                    Crear "{inputValue}"
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Selected Tags */}
            <div className="flex gap-2 flex-wrap">
                {selectedIds.map(catId => {
                    const category = categories.find(c => c.id === catId);
                    // Only show if it matches the current selector type
                    if (!category || (category.type !== type && !(type === 'genre' && !category.type))) return null;

                    return (
                        <span key={catId} className={`px-3 py-1 ${colors.bg} ${colors.text} text-xs rounded-full border ${colors.border} flex items-center gap-2`}>
                            {category.name}
                            <button onClick={() => onRemove(catId)} className="hover:text-white"><X className="w-3 h-3" /></button>
                        </span>
                    );
                })}
            </div>
        </div>
    );
}
