import { X, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { useState, useEffect } from 'react';
import { Category, Manga } from '../types/manga';
import { updateManga, getMangaById } from '../services/manga';
import { LoadingSpinner } from './LoadingSpinner';

interface BulkRemoveCategoryModalProps {
    isOpen: boolean;
    onClose: () => void;
    selectedMangaIds: string[];
    onSaveComplete: () => void;
}

export function BulkRemoveCategoryModal({ isOpen, onClose, selectedMangaIds, onSaveComplete }: BulkRemoveCategoryModalProps) {
    const [availableCategories, setAvailableCategories] = useState<Category[]>([]);
    const [availableAuthors, setAvailableAuthors] = useState<string[]>([]);
    
    // The items the user selects TO REMOVE
    const [selectedCategoryIdsToRemove, setSelectedCategoryIdsToRemove] = useState<string[]>([]);
    const [selectedAuthorsToRemove, setSelectedAuthorsToRemove] = useState<string[]>([]);

    const [isSaving, setIsSaving] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (isOpen) {
            loadMangasData();
            setSelectedCategoryIdsToRemove([]);
            setSelectedAuthorsToRemove([]);
        }
    }, [isOpen]);

    const loadMangasData = async () => {
        try {
            setIsLoading(true);
            const mangasData: (Manga | null)[] = await Promise.all(
                selectedMangaIds.map(id => getMangaById(id).catch(() => null))
            );

            const validMangas = mangasData.filter(Boolean) as Manga[];
            
            const catMap = new Map<string, Category>();
            const authorSet = new Set<string>();

            validMangas.forEach(manga => {
                if (manga.author) authorSet.add(manga.author);
                if (manga.categories) {
                    manga.categories.forEach(cat => catMap.set(cat.id, cat));
                }
            });

            setAvailableCategories(Array.from(catMap.values()));
            setAvailableAuthors(Array.from(authorSet));

        } catch (error) {
            console.error('Error loading mangas data:', error);
            toast.error('Error al cargar datos de los mangas');
        } finally {
            setIsLoading(false);
        }
    };

    const toggleCategoryRemove = (id: string) => {
        setSelectedCategoryIdsToRemove(prev => 
            prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
        );
    };

    const toggleAuthorRemove = (author: string) => {
        setSelectedAuthorsToRemove(prev => 
            prev.includes(author) ? prev.filter(a => a !== author) : [...prev, author]
        );
    };

    const handleSave = async () => {
        if (selectedCategoryIdsToRemove.length === 0 && selectedAuthorsToRemove.length === 0) {
            toast.error('Selecciona al menos una categoría o autor para eliminar.');
            return;
        }

        setIsSaving(true);
        try {
            const updatePromises = selectedMangaIds.map(async (mangaId) => {
                try {
                    const manga = await getMangaById(mangaId);
                    if (!manga) return;

                    let needsUpdate = false;
                    const updateData: any = {
                        title: manga.title,
                        author: manga.author
                    };
                    
                    if (selectedAuthorsToRemove.includes(manga.author)) {
                        updateData.author = 'Desconocido';
                        needsUpdate = true;
                    }

                    if (manga.categories && manga.categories.length > 0) {
                        const existingIds = manga.categories.map(c => c.id);
                        const newIds = existingIds.filter(id => !selectedCategoryIdsToRemove.includes(id));
                        
                        if (newIds.length !== existingIds.length) {
                            updateData.categoryIds = newIds;
                            needsUpdate = true;
                        } else {
                            updateData.categoryIds = existingIds;
                        }
                    } else {
                         updateData.categoryIds = [];
                    }

                    if (needsUpdate) {
                        await updateManga(mangaId, updateData);
                    }
                } catch (err) {
                    console.error(`Error updating manga ${mangaId}`, err);
                }
            });

            await Promise.all(updatePromises);
            toast.success('Categorías eliminadas de los mangas correctamente.');
            onSaveComplete();
            onClose();

        } catch (error) {
            console.error('Error bulk updating mangas:', error);
            toast.error('Error al aplicar cambios.');
        } finally {
            setIsSaving(false);
        }
    };

    if (!isOpen) return null;

    const renderCategorySection = (type: 'character' | 'series' | 'genre' | 'tag', title: string, colorClass: string) => {
        const typeCategories = availableCategories.filter(c => c.type === type);
        if (typeCategories.length === 0) return null;

        return (
            <div className="bg-[#1f1f1f] p-4 rounded-xl border border-gray-800 space-y-3">
                <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">{title}</span>
                <div className="flex flex-wrap gap-2">
                    {typeCategories.map(cat => {
                        const isSelected = selectedCategoryIdsToRemove.includes(cat.id);
                        return (
                            <button
                                key={cat.id}
                                onClick={() => toggleCategoryRemove(cat.id)}
                                className={`px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-2 border transition-all ${
                                    isSelected 
                                    ? 'bg-red-500/20 text-red-500 border-red-500/50 hover:bg-red-500/30' 
                                    : `bg-[#1a1a1a] ${colorClass} border-gray-700 hover:border-gray-500`
                                }`}
                            >
                                {cat.name}
                                {isSelected && <Trash2 className="w-3.5 h-3.5" />}
                            </button>
                        );
                    })}
                </div>
            </div>
        );
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
                    <h2 className="text-xl font-bold text-white flex items-center gap-2">
                        <Trash2 className="w-5 h-5 text-red-500"/>
                        Remover Categorías en {selectedMangaIds.length} Mangas
                    </h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {isLoading ? (
                        <div className="flex flex-col items-center justify-center py-12 gap-4">
                            <LoadingSpinner size={32} />
                            <p className="text-gray-400 text-sm">Escaneando mangas seleccionados...</p>
                        </div>
                    ) : availableCategories.length === 0 && availableAuthors.length === 0 ? (
                        <div className="flex flex-col items-center justify-center py-12 text-center">
                            <Trash2 className="w-12 h-12 text-gray-600 mb-3" />
                            <h3 className="text-lg font-semibold text-white">Sin categorías</h3>
                            <p className="text-gray-400 text-sm max-w-sm mt-1">Los mangas seleccionados no tienen autores ni categorías para remover.</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            <p className="text-sm text-gray-400">
                                Selecciona los autores y categorías que deseas <b className="text-red-400">eliminar</b> de los mangas seleccionados.
                            </p>

                            {/* Autores */}
                            {availableAuthors.length > 0 && (
                                <div className="bg-[#1f1f1f] p-4 rounded-xl border border-gray-800 space-y-3">
                                    <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Autor</span>
                                    <div className="flex flex-wrap gap-2">
                                        {availableAuthors.map(author => {
                                            const isSelected = selectedAuthorsToRemove.includes(author);
                                            return (
                                                <button
                                                    key={author}
                                                    onClick={() => toggleAuthorRemove(author)}
                                                    className={`px-3 py-1.5 rounded-full text-sm font-medium flex items-center gap-2 border transition-all ${
                                                        isSelected 
                                                        ? 'bg-red-500/20 text-red-500 border-red-500/50 hover:bg-red-500/30' 
                                                        : 'bg-[#1a1a1a] text-purple-400 border-gray-700 hover:border-gray-500'
                                                    }`}
                                                >
                                                    {author}
                                                    {isSelected && <Trash2 className="w-3.5 h-3.5" />}
                                                </button>
                                            );
                                        })}
                                    </div>
                                    <p className="text-xs text-red-500/80 mt-2">* Remover al autor lo dejará como "Desconocido".</p>
                                </div>
                            )}

                            {/* Categorías */}
                            {renderCategorySection('character', 'Personajes', 'text-blue-400')}
                            {renderCategorySection('series', 'Series', 'text-green-400')}
                            {renderCategorySection('genre', 'Géneros', 'text-purple-400')}
                            {renderCategorySection('tag', 'Etiquetas', 'text-pink-400')}
                        </div>
                    )}
                </div>

                <div className="p-6 border-t border-gray-800 flex justify-end gap-3 bg-[#1a1a1a]">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:text-white transition-colors"
                    >
                        Cancelar
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving || (selectedCategoryIdsToRemove.length === 0 && selectedAuthorsToRemove.length === 0)}
                        className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-red-600/20 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isSaving ? (
                            <>
                                <LoadingSpinner size={16} />
                                Eliminando...
                            </>
                        ) : (
                            <>
                                <Trash2 className="w-4 h-4" />
                                Remover Selección
                            </>
                        )}
                    </button>
                </div>

            </div>
        </div>
    );
}
