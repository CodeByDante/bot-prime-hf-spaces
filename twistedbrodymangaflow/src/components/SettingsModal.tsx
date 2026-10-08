import { X, Trash2, Settings, Megaphone, Clock, Eye, Layers, Copy, Edit3, Tag, FolderPlus, Eraser, ExternalLink, Link } from 'lucide-react';
import { useState, useEffect } from 'react';
import { toast } from 'sonner';
import { saveAnnouncement } from '../services/announcement';
import { resetAllMangaViews } from '../services/manga';
import { reorderAllMangasPages } from '../services/reorderScript';

interface SettingsModalProps {
    isOpen: boolean;
    onClose: () => void;
    isAdmin: boolean;
    onAdminChange: (isAdmin: boolean) => void;
    isCategoryPlusEnabled: boolean;
    onCategoryPlusChange: (enabled: boolean) => void;
    isCopyIdsEnabled: boolean;
    onCopyIdsChange: (enabled: boolean) => void;
    isDeletePlusEnabled: boolean;
    onDeletePlusChange: (enabled: boolean) => void;
    isCategoryMinusEnabled: boolean;
    onCategoryMinusChange: (enabled: boolean) => void;
    isEditTitlePlusEnabled: boolean;
    onEditTitlePlusChange: (enabled: boolean) => void;
    isEtiquetadoraEnabled: boolean;
    onEtiquetadoraChange: (enabled: boolean) => void;
    isFolderPlusEnabled: boolean;
    onFolderPlusChange: (enabled: boolean) => void;
    isPortalPlusEnabled: boolean;
    onPortalPlusChange: (enabled: boolean) => void;
    isFolderAnimationEnabled: boolean;
    onFolderAnimationChange: (enabled: boolean) => void;
    isMergePlusEnabled: boolean;
    onMergePlusChange: (enabled: boolean) => void;
    isTransferPlusEnabled: boolean;
    onTransferPlusChange: (enabled: boolean) => void;
    onOpenTitleManager: () => void;
    onOpenFolderMap: () => void;
    onCleanKemonoTitles: () => void;
}

export function SettingsModal({ 
    isOpen, 
    onClose, 
    isAdmin,
    onAdminChange,
    isCategoryPlusEnabled, 
    onCategoryPlusChange,
    isCopyIdsEnabled,
    onCopyIdsChange,
    isDeletePlusEnabled,
    onDeletePlusChange,
    isCategoryMinusEnabled,
    onCategoryMinusChange,
    isEditTitlePlusEnabled,
    onEditTitlePlusChange,
    isEtiquetadoraEnabled,
    onEtiquetadoraChange,
    isFolderPlusEnabled,
    onFolderPlusChange,
    isPortalPlusEnabled,
    onPortalPlusChange,
    isFolderAnimationEnabled,
    onFolderAnimationChange,
    isMergePlusEnabled,
    onMergePlusChange,
    isTransferPlusEnabled,
    onTransferPlusChange,
    onOpenTitleManager,
    onOpenFolderMap,
    onCleanKemonoTitles
}: SettingsModalProps) {
    // Announcement State
    const [announcementText, setAnnouncementText] = useState('');
    const [durationValue, setDurationValue] = useState(24);
    const [durationUnit, setDurationUnit] = useState<'seconds' | 'minutes' | 'hours' | 'days'>('hours');
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    // Reorder State
    const [isReordering, setIsReordering] = useState(false);
    const [reorderProgress, setReorderProgress] = useState({ current: 0, total: 0, title: '' });

    // Reset state when modal opens
    useEffect(() => {
        if (isOpen) {
            // Add any future initialization logic here
        }
    }, [isOpen]);



    const handlePublishAnnouncement = async () => {
        if (!announcementText.trim()) {
            toast.error('El texto del anuncio no puede estar vacío');
            return;
        }

        let durationMs = 0;
        if (durationUnit === 'seconds') durationMs = durationValue * 1000;
        if (durationUnit === 'minutes') durationMs = durationValue * 60 * 1000;
        if (durationUnit === 'hours') durationMs = durationValue * 60 * 60 * 1000;
        if (durationUnit === 'days') durationMs = durationValue * 24 * 60 * 60 * 1000;

        try {
            await saveAnnouncement(announcementText, durationMs);
            toast.success('Anuncio publicado exitosamente');
            setAnnouncementText('');
            onClose();
        } catch (err) {
            console.error(err);
            toast.error('Error al publicar el anuncio');
        }
    };

    const handleDeleteAnnouncement = async () => {
        try {
            await saveAnnouncement('', null);
            setAnnouncementText('');
            setShowDeleteConfirm(false);
            toast.success('Anuncio eliminado.');
        } catch (e) {
            console.error(e);
            toast.error('Error al eliminar');
        }
    };

    const handleReorderPages = async () => {
        if (window.confirm('¿Seguro que quieres reordenar automáticamente TODAS las páginas de todos los mangas? Este proceso puede tardar un par de minutos.')) {
            setIsReordering(true);
            setReorderProgress({ current: 0, total: 0, title: 'Iniciando...' });
            try {
                const result = await reorderAllMangasPages((currentManga, current, total) => {
                    setReorderProgress({ current, total, title: currentManga });
                });
                toast.success(`Se reordenaron las páginas correctamente en ${result.updated} mangas (Errores: ${result.errors}).`);
            } catch (err) {
                console.error(err);
                toast.error('Ocurrió un error al reordenar las páginas.');
            } finally {
                setIsReordering(false);
            }
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4 animate-in fade-in duration-200">
            <div className="bg-[#121212] rounded-2xl border border-gray-800 w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">

                {/* Header */}
                <div className="bg-[#1a1a1a] border-b border-gray-800 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-[#bb86fc]/10 rounded-lg text-[#bb86fc]">
                            <Settings className="w-5 h-5" />
                        </div>
                        <h2 className="text-xl font-bold text-white">Ajustes de Administrador</h2>
                    </div>
                    <button onClick={onClose} className="text-gray-400 hover:text-white transition-colors p-2 hover:bg-white/5 rounded-lg">
                        <X className="w-5 h-5" />
                    </button>
                </div>

                <div className="p-6 space-y-8 overflow-y-auto custom-scrollbar">

                    {/* Category Plus Toggle */}
                    <section className="space-y-4">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isCategoryPlusEnabled ? 'bg-purple-500/10 text-purple-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Layers className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Categorías Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección múltiple y edición masiva</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isCategoryPlusEnabled}
                                    onChange={(e) => onCategoryPlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-purple-300 dark:peer-focus:ring-purple-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-[#bb86fc]"></div>
                            </label>
                        </div>
                    </section>

                    {/* Folder Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isFolderPlusEnabled ? 'bg-indigo-500/10 text-indigo-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <FolderPlus className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Carpetas Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección para crear carpetas y agrupar mangas</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isFolderPlusEnabled}
                                    onChange={(e) => onFolderPlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-indigo-300 dark:peer-focus:ring-indigo-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-indigo-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Portal Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isPortalPlusEnabled ? 'bg-cyan-500/10 text-cyan-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <ExternalLink className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Portal Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección masiva para cambiar de sección (Patreon, OnlyFans, Flow)</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isPortalPlusEnabled}
                                    onChange={(e) => onPortalPlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-cyan-300 dark:peer-focus:ring-cyan-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-cyan-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Merge Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isMergePlusEnabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Link className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Unir Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección de múltiples mangas para unirlos en uno</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isMergePlusEnabled}
                                    onChange={(e) => onMergePlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-emerald-300 dark:peer-focus:ring-emerald-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-emerald-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Transfer Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isTransferPlusEnabled ? 'bg-amber-500/10 text-amber-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Layers className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Transferencia Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección de dos mangas para transferir páginas entre ellos</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isTransferPlusEnabled}
                                    onChange={(e) => onTransferPlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-amber-300 dark:peer-focus:ring-amber-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-amber-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Category Minus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isCategoryMinusEnabled ? 'bg-orange-500/10 text-orange-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Layers className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Categorías Minus</h3>
                                    <p className="text-xs text-gray-400">Habilitar eliminación masiva de categorías en mangas seleccionados</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isCategoryMinusEnabled}
                                    onChange={(e) => onCategoryMinusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-orange-300 dark:peer-focus:ring-orange-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-orange-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Edit Title Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isEditTitlePlusEnabled ? 'bg-pink-500/10 text-pink-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Edit3 className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Nombres Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección masiva para editar títulos</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isEditTitlePlusEnabled}
                                    onChange={(e) => onEditTitlePlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-pink-300 dark:peer-focus:ring-pink-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-pink-500"></div>
                            </label>
                        </div>
                    </section>

                    {/* Etiquetadora Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isEtiquetadoraEnabled ? 'bg-[#bb86fc]/10 text-[#bb86fc]' : 'bg-gray-800 text-gray-400'}`}>
                                    <Tag className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Etiquetadora Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección masiva para etiquetar clasificaciones (Sin censura, B/N, a color)</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isEtiquetadoraEnabled}
                                    onChange={(e) => onEtiquetadoraChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-[#bb86fc]/30 dark:peer-focus:ring-[#bb86fc]/80 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-[#bb86fc]"></div>
                            </label>
                        </div>
                    </section>

                    {/* Copy IDs Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isCopyIdsEnabled ? 'bg-blue-500/10 text-blue-400' : 'bg-gray-800 text-gray-400'}`}>
                                    <Copy className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Copiar IDs Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección masiva para copiar IDs</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isCopyIdsEnabled}
                                    onChange={(e) => onCopyIdsChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-blue-300 dark:peer-focus:ring-blue-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-blue-500"></div>
                            </label>
                        </div>
                    </section>
                    
                    {/* Delete Plus Toggle */}
                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                                <div className={`p-2 rounded-lg ${isDeletePlusEnabled ? 'bg-red-500/10 text-red-500' : 'bg-gray-800 text-gray-400'}`}>
                                    <Trash2 className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="text-sm font-semibold text-white">Eliminar Plus</h3>
                                    <p className="text-xs text-gray-400">Habilitar selección masiva para eliminar mangas</p>
                                </div>
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    className="sr-only peer"
                                    checked={isDeletePlusEnabled}
                                    onChange={(e) => onDeletePlusChange(e.target.checked)}
                                />
                                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-red-300 dark:peer-focus:ring-red-800 rounded-full peer dark:bg-gray-700 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all dark:border-gray-600 peer-checked:bg-red-500"></div>
                            </label>
                        </div>
                    </section>

                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-red-500/10 rounded-lg text-red-500">
                                <Eye className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="tex-sm font-semibold text-white">Gestión de Vistas</h3>
                                <p className="text-xs text-gray-400">Restablecer contadores de visualización</p>
                            </div>
                        </div>

                        <button
                            onClick={async () => {
                                if (window.confirm('¿Seguro que quieres reiniciar las vistas de TODOS los mangas a 0? Esta acción no se puede deshacer.')) {
                                    try {
                                        await resetAllMangaViews();
                                        toast.success('Vistas reiniciadas correctamente.');
                                    } catch (e) {
                                        console.error(e);
                                        toast.error('Error al reiniciar vistas.');
                                    }
                                }
                            }}
                            className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-500 py-2.5 rounded-lg font-semibold text-sm transition-all border border-red-500/20 hover:border-red-500/40"
                        >
                            Reiniciar Vistas a 0
                        </button>
                    </section>

                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-blue-500/10 rounded-lg text-blue-400">
                                <Edit3 className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="tex-sm font-semibold text-white">Gestor de Nombres</h3>
                                <p className="text-xs text-gray-400">Edición masiva rápida de títulos alfabéticamente</p>
                            </div>
                        </div>

                        <button
                            onClick={() => {
                                onClose();
                                onOpenTitleManager();
                            }}
                            className="w-full bg-blue-500/10 hover:bg-blue-500/20 text-blue-500 py-2.5 rounded-lg font-semibold text-sm transition-all border border-blue-500/20 hover:border-blue-500/40 flex items-center justify-center gap-2"
                        >
                            <Edit3 className="w-4 h-4"/>
                            Abrir Gestor de Nombres
                        </button>
                    </section>



                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                                <Layers className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="tex-sm font-semibold text-white">Mapa Mental de Carpetas</h3>
                                <p className="text-xs text-gray-400">Observa toda tu estructura de carpetas y cómics en un formato de mapa mental interconectado</p>
                            </div>
                        </div>

                        <button
                            onClick={() => {
                                onClose();
                                onOpenFolderMap();
                            }}
                            className="w-full bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 py-2.5 rounded-lg font-semibold text-sm transition-all border border-indigo-500/20 hover:border-indigo-500/40 flex items-center justify-center gap-2"
                        >
                            <Layers className="w-4 h-4"/>
                            Abrir Mapa Mental
                        </button>
                    </section>

                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-yellow-500/10 rounded-lg text-yellow-500">
                                <Eraser className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="tex-sm font-semibold text-white">Limpiador Kemono</h3>
                                <p className="text-xs text-gray-400">Elimina el patrón [12345] del final de todos los nombres en la base de datos automáticamente</p>
                            </div>
                        </div>

                        <button
                            onClick={onCleanKemonoTitles}
                            className="w-full bg-yellow-500/10 hover:bg-yellow-500/20 text-yellow-500 py-2.5 rounded-lg font-semibold text-sm transition-all border border-yellow-500/20 hover:border-yellow-500/40 flex items-center justify-center gap-2"
                        >
                            <Eraser className="w-4 h-4"/>
                            Limpiar IDs [Numeros]
                        </button>
                    </section>

                    <section className="space-y-4 pt-4 border-t border-gray-800">
                        <div className="flex items-center gap-3 mb-2">
                            <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-500">
                                <Layers className="w-5 h-5" />
                            </div>
                            <div>
                                <h3 className="tex-sm font-semibold text-white">Ordenar Páginas Plus</h3>
                                <p className="text-xs text-gray-400">Reordena las páginas desordenadas analizando los archivos originales.</p>
                            </div>
                        </div>

                        <button
                            onClick={handleReorderPages}
                            disabled={isReordering}
                            className={`w-full py-2.5 rounded-lg font-semibold text-sm transition-all border flex items-center justify-center gap-2 ${
                                isReordering 
                                ? 'bg-emerald-500/5 text-emerald-500/50 border-emerald-500/10 cursor-not-allowed'
                                : 'bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-500 border-emerald-500/20 hover:border-emerald-500/40'
                            }`}
                        >
                            {isReordering ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin"></div>
                                    Procesando {reorderProgress.current} / {reorderProgress.total} - {reorderProgress.title.substring(0, 20)}...
                                </>
                            ) : (
                                'Reordenar Todas Las Páginas Automáticamente'
                            )}
                        </button>
                    </section>
                    
                    <>
                        <div className="h-px bg-gray-800" />
                        <section className="space-y-4">
                            <div className="flex items-center gap-3 mb-2">
                                <div className="p-2 bg-purple-500/10 rounded-lg text-purple-400">
                                    <Megaphone className="w-5 h-5" />
                                </div>
                                <div>
                                    <h3 className="tex-sm font-semibold text-white">Publicar Anuncio</h3>
                                    <p className="text-xs text-gray-400">Visible para todos los usuarios</p>
                                </div>
                            </div>

                            <div className="space-y-3">
                                <textarea
                                    value={announcementText}
                                    onChange={(e) => setAnnouncementText(e.target.value)}
                                    placeholder="Escribe el mensaje del anuncio..."
                                    className="w-full bg-[#1a1a1a] border border-gray-700 rounded-lg px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-[#bb86fc] min-h-[100px] resize-none"
                                />

                                <div className="flex gap-3">
                                    <div className="flex-1 bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 flex items-center gap-2">
                                        <Clock className="w-4 h-4 text-gray-400" />
                                        <input
                                            type="number"
                                            min="1"
                                            value={durationValue}
                                            onChange={(e) => setDurationValue(Number(e.target.value))}
                                            className="bg-transparent text-white text-sm w-full focus:outline-none"
                                        />
                                    </div>
                                    <select
                                        value={durationUnit}
                                        onChange={(e) => setDurationUnit(e.target.value as any)}
                                        className="bg-[#1a1a1a] border border-gray-700 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-[#bb86fc]"
                                    >
                                        <option value="seconds">Segundos</option>
                                        <option value="minutes">Minutos</option>
                                        <option value="hours">Horas</option>
                                        <option value="days">Días</option>
                                    </select>
                                </div>

                                <div className="flex gap-2">
                                    <button
                                        onClick={() => setShowDeleteConfirm(true)}
                                        className="px-4 py-2.5 rounded-lg font-semibold text-sm bg-red-500/10 text-red-500 border border-red-500/20 hover:bg-red-500/20 transition-colors"
                                        title="Eliminar anuncio"
                                    >
                                        <Trash2 className="w-5 h-5" />
                                    </button>
                                    <button
                                        onClick={handlePublishAnnouncement}
                                        className="flex-1 bg-gradient-to-r from-[#bb86fc] to-[#9966dd] hover:from-[#9966dd] hover:to-[#7744cc] text-white py-2.5 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-[#bb86fc]/20"
                                    >
                                        Publicar Anuncio
                                    </button>
                                </div>
                            </div>
                        </section>
                    </>



                </div>

                {/* Confirm Delete Overlay */}
                {showDeleteConfirm && (
                    <div className="absolute inset-0 bg-black/80 backdrop-blur-sm flex items-center justify-center z-50 p-6 animate-in fade-in duration-200">
                        <div className="bg-[#1a1a1a] border border-gray-700 w-full max-w-sm rounded-xl shadow-2xl p-6 transform scale-100 animate-in zoom-in-95 duration-200">
                            <div className="flex flex-col items-center text-center gap-4">
                                <div className="p-3 bg-red-500/10 rounded-full text-red-500">
                                    <Trash2 className="w-8 h-8" />
                                </div>
                                <div>
                                    <h3 className="text-lg font-bold text-white mb-1">¿Eliminar anuncio?</h3>
                                    <p className="text-sm text-gray-400">
                                        Esta acción eliminará el anuncio actual inmediatamente. No se puede deshacer.
                                    </p>
                                </div>
                                <div className="flex gap-3 w-full mt-2">
                                    <button
                                        onClick={() => setShowDeleteConfirm(false)}
                                        className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold text-gray-300 hover:bg-gray-800 transition-colors"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={handleDeleteAnnouncement}
                                        className="flex-1 px-4 py-2 rounded-lg text-sm font-semibold bg-red-500 hover:bg-red-600 text-white transition-colors shadow-lg shadow-red-500/20"
                                    >
                                        Eliminar
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

            </div>
        </div>
    );
}

