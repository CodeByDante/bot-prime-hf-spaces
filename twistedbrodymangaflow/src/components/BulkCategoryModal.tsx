import { X, Save } from 'lucide-react';
import { toast } from 'sonner';
import { useState, useEffect } from 'react';
import { Category } from '../types/manga';
import { createCategory, getAllCategories, updateManga, getMangaById, deleteCategory, getAllAuthors, deleteAuthorByName } from '../services/manga';
import { LoadingSpinner } from './LoadingSpinner';
import { CategorySelector } from './CategorySelector';
import { AuthorSelector } from './AuthorSelector';

interface BulkCategoryModalProps {
    isOpen: boolean;
    onClose: () => void;
    selectedMangaIds: string[];
    onSaveComplete: () => void;
}

export function BulkCategoryModal({ isOpen, onClose, selectedMangaIds, onSaveComplete }: BulkCategoryModalProps) {
    const [categories, setCategories] = useState<Category[]>([]);
    const [selectedCategories, setSelectedCategories] = useState<string[]>([]);

    // Author state
    const [authors, setAuthors] = useState<string[]>([]);
    const [selectedAuthors, setSelectedAuthors] = useState<string[]>([]);

    const [applyDecensored, setApplyDecensored] = useState(false);
    const [applyBn, setApplyBn] = useState(false);
    const [applyColor, setApplyColor] = useState(false);

    const [isSaving, setIsSaving] = useState(false);
    const [isLoading, setIsLoading] = useState(false);

    useEffect(() => {
        if (isOpen) {
            loadCategories();
            setSelectedCategories([]); // Reset selection on open
            setSelectedAuthors([]); // Reset author on open
            setApplyDecensored(false);
            setApplyBn(false);
            setApplyColor(false);
        }
    }, [isOpen]);

    const loadCategories = async () => {
        try {
            setIsLoading(true);
            const data = await getAllCategories();
            setCategories(data);

            // Load authors - Optimized call
            const uniqueAuthors = await getAllAuthors();
            setAuthors(uniqueAuthors);
        } catch (error) {
            console.error('Error loading categories:', error);
        } finally {
            setIsLoading(false);
        }
    };

    const handleCreateCategory = async (name: string, type: 'character' | 'series' | 'genre' | 'tag') => {
        if (!name.trim()) return;

        // Special handling for tags: split by space
        if (type === 'tag') {
            const tagNames = name.split(' ').map(t => t.trim()).filter(t => t.length > 0);

            // Allow multiple creations in parallel or sequential. 
            for (const tagName of tagNames) {
                await processSingleCategory(tagName, type);
            }
            return;
        }

        await processSingleCategory(name, type);
    };

    const processSingleCategory = async (name: string, type: 'character' | 'series' | 'genre' | 'tag') => {
        try {
            const existingCategory = categories.find(
                cat => cat.name.toLowerCase() === name.trim().toLowerCase() && cat.type === type
            );

            if (existingCategory) {
                setSelectedCategories(prev => {
                    if (!prev.includes(existingCategory.id)) return [...prev, existingCategory.id];
                    return prev;
                });
            } else {
                const newCategory = await createCategory(name.trim(), type);
                setCategories(prev => {
                    if (prev.find(c => c.id === newCategory.id)) return prev;
                    return [...prev, newCategory];
                });
                setSelectedCategories(prev => {
                    if (!prev.includes(newCategory.id)) return [...prev, newCategory.id];
                    return prev;
                });
            }
        } catch (error) {
            console.error('Error creating category:', error);
        }
    };

    const handleRemoveCategory = (categoryId: string) => {
        setSelectedCategories(prev => prev.filter(id => id !== categoryId));
    };

    const handleDeleteCategory = async (id: string) => {
        try {
            await deleteCategory(id);
            setCategories(prev => prev.filter(c => c.id !== id));
            // Also remove from selection if selected
            setSelectedCategories(prev => prev.filter(catId => catId !== id));
        } catch (error) {
            console.error('Error deleting category:', error);
            toast.error('Error al eliminar la categoría');
        }
    };

    const handleDeleteAuthor = (authorName: string) => {
        toast(`¿Eliminar al autor "${authorName}" permanentemente?`, {
            description: 'Se eliminará este autor de TODOS los mangas. Esta acción no se puede deshacer.',
            action: {
                label: 'Eliminar',
                onClick: async () => {
                    try {
                        setIsLoading(true); // Show loading state
                        await deleteAuthorByName(authorName);
                        toast.success(`Autor "${authorName}" eliminado correctamente.`);

                        // Refresh authors list
                        setAuthors(prev => prev.filter(a => a !== authorName));
                        if (selectedAuthors.includes(authorName)) {
                            setSelectedAuthors(prev => prev.filter(a => a !== authorName));
                        }

                    } catch (error) {
                        console.error('Error deleting author:', error);
                        toast.error('Error al eliminar el autor.');
                    } finally {
                        setIsLoading(false);
                    }
                },
            },
            cancel: {
                label: 'Cancelar',
                onClick: () => { },
            },
            duration: 5000,
        });
    };

    const handleSave = async () => {
        if (selectedCategories.length === 0 && selectedAuthors.length === 0 && !applyDecensored && !applyBn && !applyColor) {
            toast.error('Selecciona al menos una categoría, autor o clasificación para aplicar.');
            return;
        }

        setIsSaving(true);
        try {
            // Process all mangas
            // Strategy: Fetch current manga data (to get existing categories), append new ones unique, update.
            // This ensures we don't overwrite existing categories that are NOT in the selection.

            const updatePromises = selectedMangaIds.map(async (mangaId) => {
                try {
                    const manga = await getMangaById(mangaId);
                    if (!manga) return;

                    const existingIds = manga.categories?.map(c => c.id) || [];
                    // Merge existing with selected, avoid duplicates
                    const mergedIds = Array.from(new Set([...existingIds, ...selectedCategories]));

                    const updateData: any = {
                        title: manga.title,
                        author: manga.author,
                        categoryIds: mergedIds
                    };

                    // Update author if selected
                    if (selectedAuthors.length > 0) {
                        updateData.author = selectedAuthors.join(', ');
                    }

                    if (applyDecensored) updateData.is_decensored = true;
                    if (applyBn) {
                        updateData.is_bn = true;
                        updateData.is_color = false;
                    }
                    if (applyColor) {
                        updateData.is_color = true;
                        updateData.is_bn = false;
                    }

                    await updateManga(mangaId, updateData);
                } catch (err) {
                    console.error(`Error updating manga ${mangaId}`, err);
                }
            });

            await Promise.all(updatePromises);
            toast.success('Categorías aplicadas correctamente.');
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

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
                    <h2 className="text-xl font-bold text-white">
                        Aplicar Categorías a {selectedMangaIds.length} Mangas
                    </h2>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 overflow-y-auto custom-scrollbar flex-1">
                    {isLoading ? (
                        <div className="flex justify-center p-8">
                            <LoadingSpinner size={32} />
                        </div>
                    ) : (
                        <div className="space-y-6">
                            {/* Autores */}
                            <div className="bg-[#1f1f1f] p-4 rounded-xl border border-gray-800">
                                <AuthorSelector
                                    label="Autor"
                                    authors={authors}
                                    value={selectedAuthors}
                                    onChange={setSelectedAuthors}
                                    onDelete={handleDeleteAuthor}
                                    placeholder="Seleccionar o escribir autor..."
                                />
                            </div>

                            {/* Clasificaciones */}
                            <div className="bg-[#1f1f1f] p-4 rounded-xl border border-gray-800 space-y-4">
                               <div className="flex items-center justify-between">
                                  <div>
                                    <h4 className="text-sm font-semibold text-white">Sin censura</h4>
                                    <p className="text-xs text-gray-400">Marcar todos como sin censura</p>
                                  </div>
                                  <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                      type="checkbox"
                                      className="sr-only peer"
                                      checked={applyDecensored}
                                      onChange={(e) => setApplyDecensored(e.target.checked)}
                                    />
                                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                                  </label>
                                </div>

                                <div className="flex items-center justify-between">
                                  <div>
                                    <h4 className="text-sm font-semibold text-white">B/N</h4>
                                    <p className="text-xs text-gray-400">Marcar todos como Blanco y Negro</p>
                                  </div>
                                  <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                      type="checkbox"
                                      className="sr-only peer"
                                      checked={applyBn}
                                      onChange={(e) => {
                                        setApplyBn(e.target.checked);
                                        if (e.target.checked) setApplyColor(false);
                                      }}
                                    />
                                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                                  </label>
                                </div>

                                <div className="flex items-center justify-between">
                                  <div>
                                    <h4 className="text-sm font-semibold text-white">a color</h4>
                                    <p className="text-xs text-gray-400">Marcar todos como a color</p>
                                  </div>
                                  <label className="relative inline-flex items-center cursor-pointer">
                                    <input
                                      type="checkbox"
                                      className="sr-only peer"
                                      checked={applyColor}
                                      onChange={(e) => {
                                        setApplyColor(e.target.checked);
                                        if (e.target.checked) setApplyBn(false);
                                      }}
                                    />
                                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                                  </label>
                                </div>
                            </div>

                            {/* Personajes */}
                            <CategorySelector
                                label="Personajes"
                                type="character"
                                categories={categories}
                                selectedIds={selectedCategories}
                                onSelect={(id) => {
                                    if (!selectedCategories.includes(id)) {
                                        setSelectedCategories(prev => [...prev, id]);
                                    }
                                }}
                                onRemove={handleRemoveCategory}
                                onCreate={(name) => handleCreateCategory(name, 'character')}
                                onDeleteCategory={handleDeleteCategory}
                                colorClass="text-blue-400"
                                placeholder="Añadir personaje..."
                            />

                            {/* Series */}
                            <CategorySelector
                                label="Series"
                                type="series"
                                categories={categories}
                                selectedIds={selectedCategories}
                                onSelect={(id) => {
                                    if (!selectedCategories.includes(id)) {
                                        setSelectedCategories(prev => [...prev, id]);
                                    }
                                }}
                                onRemove={handleRemoveCategory}
                                onCreate={(name) => handleCreateCategory(name, 'series')}
                                onDeleteCategory={handleDeleteCategory}
                                colorClass="text-green-400"
                                placeholder="Añadir serie..."
                            />

                            {/* Géneros */}
                            <CategorySelector
                                label="Géneros"
                                type="genre"
                                categories={categories}
                                selectedIds={selectedCategories}
                                onSelect={(id) => {
                                    if (!selectedCategories.includes(id)) {
                                        setSelectedCategories(prev => [...prev, id]);
                                    }
                                }}
                                onRemove={handleRemoveCategory}
                                onCreate={(name) => handleCreateCategory(name, 'genre')}
                                onDeleteCategory={handleDeleteCategory}
                                colorClass="text-purple-400"
                                placeholder="Añadir género..."
                            />

                            {/* Etiquetas */}
                            <CategorySelector
                                label="Etiquetas"
                                type="tag"
                                categories={categories}
                                selectedIds={selectedCategories}
                                onSelect={(id) => {
                                    if (!selectedCategories.includes(id)) {
                                        setSelectedCategories(prev => [...prev, id]);
                                    }
                                }}
                                onRemove={handleRemoveCategory}
                                onCreate={(name) => handleCreateCategory(name, 'tag')}
                                onDeleteCategory={handleDeleteCategory}
                                colorClass="text-pink-400"
                                placeholder="Añadir etiqueta..."
                            />
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
                        disabled={isSaving || (selectedCategories.length === 0 && selectedAuthors.length === 0 && !applyDecensored && !applyBn && !applyColor)}
                        className="bg-[#bb86fc] hover:bg-[#9966dd] text-white px-6 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-[#bb86fc]/20 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isSaving ? (
                            <>
                                <LoadingSpinner size={16} />
                                Guardando...
                            </>
                        ) : (
                            <>
                                <Save className="w-4 h-4" />
                                Aplicar Cambios
                            </>
                        )}
                    </button>
                </div>

            </div>
        </div>
    );
}
