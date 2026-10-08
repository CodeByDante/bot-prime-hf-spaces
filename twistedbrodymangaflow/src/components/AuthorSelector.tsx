import { useState, useRef, useEffect, useMemo } from 'react';
import { X, Check, User, Trash2, Plus } from 'lucide-react';

interface AuthorSelectorProps {
    label: string;
    authors: string[];
    value: string[];
    onChange: (authors: string[]) => void;
    onDelete?: (author: string) => void;
    placeholder?: string;
    colorClass?: string;
}

export function AuthorSelector({
    label,
    authors,
    value,
    onChange,
    onDelete,
    placeholder = 'Añadir autor...',
    colorClass = 'text-gray-400'
}: AuthorSelectorProps) {
    const [inputValue, setInputValue] = useState('');
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);

    // Filter suggestions based on input
    const suggestions = useMemo(() => {
        if (!inputValue.trim()) return authors;
        return authors.filter(author =>
            author.toLowerCase().includes(inputValue.toLowerCase())
        );
    }, [authors, inputValue]);

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
        const _val = inputValue.trim();
        if (!_val) return;
        
        if (!value.includes(_val)) {
            onChange([...value, _val]);
        }
        
        setInputValue('');
        setIsOpen(false);
    };

    const handleSelect = (authorName: string) => {
        const trimmed = authorName.trim();
        if (trimmed && !value.includes(trimmed)) {
            onChange([...value, trimmed]);
        }
        setInputValue('');
        setIsOpen(false);
    };

    const handleRemove = (authorName: string) => {
        onChange(value.filter(a => a !== authorName));
    };

    const handleDeleteClick = (e: React.MouseEvent, author: string) => {
        e.stopPropagation();
        e.preventDefault();
        if (onDelete) {
            onDelete(author);
        }
    };

    return (
        <div className="space-y-3 mb-6" ref={containerRef}>
            <label className={`text-xs uppercase font-bold tracking-wider ${colorClass}`}>{label}</label>

            <div className="relative">
                <div className="flex gap-2">
                    <div className="relative flex-1">
                        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                            <User className="h-4 w-4 text-gray-500" />
                        </div>
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
                            className="w-full bg-[#1a1a1a] border border-gray-600/50 rounded-lg pl-10 pr-10 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#bb86fc] transition-all"
                        />
                        {inputValue && (
                            <button
                                onClick={() => setInputValue('')}
                                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                            >
                                <X className="w-3.5 h-3.5" />
                            </button>
                        )}
                    </div>
                    <button
                        onClick={handleAction}
                        disabled={!inputValue.trim()}
                        className="bg-[#bb86fc]/20 hover:bg-[#bb86fc]/30 text-[#bb86fc] px-4 rounded-lg flex items-center justify-center transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Plus className="w-5 h-5" />
                    </button>
                </div>

                {/* Dropdown Suggestions */}
                {isOpen && (suggestions.length > 0 || inputValue) && (
                    <div className="absolute top-full left-0 right-0 mt-1 bg-[#1a1a1a] border border-gray-700/50 rounded-lg shadow-xl z-50 max-h-60 overflow-y-auto w-full custom-scrollbar">
                        {suggestions.length > 0 ? (
                            suggestions.map((author, index) => {
                                const isSelected = value.includes(author);
                                return (
                                    <div
                                        key={index}
                                        className="flex items-center justify-between px-4 py-2.5 hover:bg-white/5 cursor-pointer group"
                                        onMouseDown={(e) => {
                                            e.preventDefault();
                                            handleSelect(author);
                                        }}
                                    >
                                        <span className={`text-sm ${isSelected ? 'text-[#bb86fc]' : 'text-gray-300'}`}>
                                            {author}
                                        </span>
                                        <div className="flex items-center gap-2">
                                            {isSelected && <Check className="w-4 h-4 text-[#bb86fc]" />}
                                            {onDelete && (
                                                <button
                                                    onMouseDown={(e) => handleDeleteClick(e, author)}
                                                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 text-gray-500 hover:text-red-400 rounded transition-all"
                                                    title="Eliminar autor de todos los mangas"
                                                >
                                                    <Trash2 className="w-3.5 h-3.5" />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })
                        ) : (
                            <div className="px-4 py-3 text-center">
                                <p className="text-gray-400 text-xs mb-2">No encontrado.</p>
                                <button
                                    onMouseDown={(e) => { e.preventDefault(); handleAction(); }}
                                    className="text-xs text-[#bb86fc] hover:underline font-semibold"
                                >
                                    Añadir "{inputValue}"
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>

            {/* Selected Tags */}
            <div className="flex gap-2 flex-wrap mt-3">
                {value.map((author, idx) => (
                    <span key={idx} className="px-3 py-1 bg-[#2a2a2a] text-[#bb86fc] text-xs rounded-full border border-gray-600/50 flex items-center gap-2">
                        {author}
                        <button onClick={() => handleRemove(author)} className="hover:text-white"><X className="w-3 h-3" /></button>
                    </span>
                ))}
            </div>

            {/* Helper text */}
            <p className="text-[10px] text-gray-500 mt-2">
                {value.length > 0 ? `Autores seleccionados: ${value.join(', ')}` : 'Deja en blanco para no modificar el autor.'}
            </p>
        </div>
    );
}
