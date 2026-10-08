import { BookOpen, X, Image as ImageIcon, Trash2, GripVertical, Settings2, Plus } from 'lucide-react';
import { useState, useEffect } from 'react';
import { processImage, OptimizedImage } from '../utils/imageOptimization';
import { uploadImage, uploadMultipleImages } from '../services/upload';
import { createManga, updateManga, getAllCategories, createCategory, createChapter, deleteCategory } from '../services/manga';
import { Category, Manga } from '../types/manga';
import { CategorySelector } from './CategorySelector';
import { LoadingSpinner } from './LoadingSpinner';
import { ImageLoader } from './ImageLoader';
import { db } from '../lib/firebase';
import { doc, updateDoc, Timestamp } from 'firebase/firestore';
import { getBatchSize, saveBatchSize } from '../utils/batchSizeManager';
import { parseLinkText } from '../utils/linkParser';
import { ConfirmModal } from './ConfirmModal';

interface NewMangaModalProps {
  currentSection: 'flow' | 'patreon' | 'onlyfans' | 'grok';
  isOpen: boolean;
  onClose: () => void;
  onMangaCreated: (mangaId?: string) => void;
  editingManga?: Manga | null;
  onDelete?: (mangaId: string) => void;
}

export function NewMangaModal({ currentSection, isOpen, onClose, onMangaCreated, editingManga, onDelete }: NewMangaModalProps) {
  const [formData, setFormData] = useState({
    title: '',
    name: '',
    description: '',
    selectedCategories: [] as string[],
    is_decensored: false,
    is_bn: false,
    is_color: false,
  });

  const [optimizedImage, setOptimizedImage] = useState<OptimizedImage | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  // Removed unused state variables for individual inputs
  const [isCreating, setIsCreating] = useState(false);
  const [chapterPages, setChapterPages] = useState<OptimizedImage[]>([]);
  const [isProcessingPages, setIsProcessingPages] = useState(false);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingImages, setUploadingImages] = useState(false);
  const [currentUploadingImage, setCurrentUploadingImage] = useState(0);
  const [totalImagesToUpload, setTotalImagesToUpload] = useState(0);
  const [bulkStatus, setBulkStatus] = useState<{
    uploading: boolean;
    current: number;
    total: number;
    currentName: string;
    errors: string[];
  } | null>(null);


  const [showCoverSelector, setShowCoverSelector] = useState(false);
  const [selectedCoverPageIndex, setSelectedCoverPageIndex] = useState<number | null>(null);
  const [coverFromExistingPage, setCoverFromExistingPage] = useState<{ thumbnail: string; original: string } | null>(null);
  const [showBatchSizeModal, setShowBatchSizeModal] = useState(false);
  const [batchSize, setBatchSize] = useState(getBatchSize());
  const [pendingBulkFiles, setPendingBulkFiles] = useState<File[] | null>(null);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const isEditMode = !!editingManga;
  const isFolderMode = isEditMode && editingManga?.is_folder;

  useEffect(() => {
    if (isOpen) {
      loadCategories();
      if (editingManga) {
        setFormData({
          title: editingManga.title,
          name: editingManga.author,
          description: editingManga.description || '',
          selectedCategories: editingManga.categories?.map(c => (typeof c === 'string' ? c : c.id)) || [],
          is_decensored: !!editingManga.is_decensored,
          is_bn: !!editingManga.is_bn,
          is_color: !!editingManga.is_color,
        });

        if (editingManga.thumbnail_url) {
          setPreviewUrl(editingManga.thumbnail_url);
        }

        const firstChapter = editingManga.chapters?.[0];
        if (firstChapter?.pages && firstChapter.pages.length > 0) {
          const pageUrls = firstChapter.pages;
          const originalPageUrls = firstChapter.original_pages || [];
          const optimizedPages: OptimizedImage[] = pageUrls.map((url, idx) => ({
            thumbnail: url,
            original: originalPageUrls[idx] || url,
            webpDisplay: url,
            webpCover: url,
            originalFormat: firstChapter.page_formats?.[idx] || 'jpg',
            originalBase64: '',
            originalUnmodified: '',
          }));
          setChapterPages(optimizedPages);
        }
      }
    }
  }, [isOpen, editingManga]);

  useEffect(() => {
    if (chapterPages.length > 0 && selectedCoverPageIndex === null && !optimizedImage && !coverFromExistingPage && !previewUrl) {
      handleSetCoverFromPage(0);
    }
  }, [chapterPages]);

  async function loadCategories() {
    try {
      const data = await getAllCategories();
      setCategories(data);
    } catch (error) {
      console.error('Error loading categories:', error);
    }
  }

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };





  const handleRemoveCategory = (categoryId: string) => {
    setFormData(prev => ({
      ...prev,
      selectedCategories: prev.selectedCategories.filter(id => id !== categoryId),
    }));
  };

  const handleCreateCategory = async (name: string, type: 'character' | 'series' | 'genre' | 'tag') => {
    if (!name.trim()) return;

    // Special handling for tags
    if (type === 'tag') {
      const tagNames = name.split(' ').map(t => t.trim()).filter(t => t.length > 0);
      for (const tagName of tagNames) {
        await processSingleCategory(tagName, type);
      }
      return;
    }

    await processSingleCategory(name, type);
  };

  const processSingleCategory = async (name: string, type: 'character' | 'series' | 'genre' | 'tag') => {
    try {
      // Check if it already exists
      const existingCategory = categories.find(
        cat => cat.name.toLowerCase() === name.trim().toLowerCase() && cat.type === type
      );

      if (existingCategory) {
        setFormData(prev => {
          if (!prev.selectedCategories.includes(existingCategory.id)) {
            return {
              ...prev,
              selectedCategories: [...prev.selectedCategories, existingCategory.id]
            };
          }
          return prev;
        });
      } else {
        const newCategory = await createCategory(name.trim(), type);
        setCategories(prev => {
          if (prev.find(c => c.id === newCategory.id)) return prev;
          return [...prev, newCategory];
        });
        setFormData(prev => {
          if (!prev.selectedCategories.includes(newCategory.id)) {
            return {
              ...prev,
              selectedCategories: [...prev.selectedCategories, newCategory.id]
            };
          }
          return prev;
        });
      }
    } catch (error) {
      console.error('Error creating category:', error);
      // alert('Error al crear la categoría');
    }
  };

  const handleDeleteCategory = async (id: string) => {
    try {
      await deleteCategory(id);
      setCategories(prev => prev.filter(c => c.id !== id));
      // Also remove from selection if selected
      setFormData(prev => ({
        ...prev,
        selectedCategories: prev.selectedCategories.filter(catId => catId !== id)
      }));
    } catch (error) {
      console.error('Error deleting category:', error);
      alert('Error al eliminar la categoría');
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setIsProcessing(true);

    try {
      const processed = await processImage(file);
      setOptimizedImage(processed);
      setPreviewUrl(processed.originalUnmodified);
    } catch (error) {
      console.error('Error processing image:', error);
      alert('Error al procesar la imagen. Intenta con otro archivo.');
    } finally {
      setIsProcessing(false);
    }
  };

  const handleChapterPagesChange = async (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    let text = '';
    
    if (e.target instanceof HTMLInputElement && e.target.files && e.target.files.length > 0) {
      const files = Array.from(e.target.files);
      
      if (files.length > 1) {
        setPendingBulkFiles(files);
        return;
      }

      const file = files[0];
      
      // Auto-populate title from filename if not in edit mode or title is empty
      if (!isEditMode || !formData.title.trim()) {
        const fileName = file.name.split('.').slice(0, -1).join('.');
        const cleanName = fileName.replace(/[_-]/g, ' ').trim();
        setFormData(prev => ({ ...prev, title: cleanName }));
      }

      try {
        text = await file.text();
      } catch (err) {
        console.error('Error reading text file:', err);
        alert('Error al leer el archivo de texto.');
        return;
      }
    } else if (e.target instanceof HTMLTextAreaElement) {
      text = e.target.value;
    }

    if (!text.trim()) return;

    setIsProcessingPages(true);

    try {
      const parsedPages = parseLinkText(text);
      
      if (parsedPages.length === 0) {
        alert('No se encontraron enlaces válidos en el texto provisto. Asegúrate de copiar el formato correcto.');
        return;
      }

      setChapterPages(prev => [...prev, ...parsedPages]);

    } catch (error) {
      console.error('Error parsing pages from text:', error);
      alert('Error al procesar los enlaces.');
    } finally {
      setIsProcessingPages(false);
      if (e.target instanceof HTMLInputElement) {
        e.target.value = '';
      }
    }
  };



  const handleBulkUpload = async (files: File[]) => {
    if (isEditMode) {
      alert('La subida masiva solo está disponible al crear nuevos mangas.');
      return;
    }

    setBulkStatus({
      uploading: true,
      current: 0,
      total: files.length,
      currentName: '',
      errors: []
    });

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const fileName = file.name.split('.').slice(0, -1).join('.');
        const cleanTitle = fileName.replace(/[_-]/g, ' ').trim();
        
        setBulkStatus(prev => prev ? { ...prev, current: i + 1, currentName: cleanTitle } : null);

        try {
          const text = await file.text();
          const parsedPages = parseLinkText(text);

          if (parsedPages.length === 0) {
            throw new Error('No se encontraron enlaces válidos.');
          }

          // Create Manga
          const mangaPayload: any = {
            title: cleanTitle,
            author: formData.name?.trim() || 'Anónimo',
            categoryIds: formData.selectedCategories,
            is_decensored: formData.is_decensored,
            is_bn: formData.is_bn,
            is_color: formData.is_color,
            section: currentSection,
          };

          if (formData.description?.trim()) {
            mangaPayload.description = formData.description.trim();
          }

          // Set cover from first page
          if (parsedPages.length > 0) {
            mangaPayload.thumbnail_url = parsedPages[0].webpDisplay;
            mangaPayload.cover_url = parsedPages[0].originalUnmodified;
          }

          const manga = await createManga(mangaPayload);

          // Create Chapter
          await createChapter({
            manga_id: manga.id,
            number: 1,
            title: 'Páginas',
            pages: parsedPages.map(p => p.webpDisplay),
            page_formats: parsedPages.map(p => p.originalFormat),
            original_pages: parsedPages.map(p => p.original),
          });

        } catch (err: any) {
          console.error(`Error processing ${file.name}:`, err);
          setBulkStatus(prev => prev ? { 
            ...prev, 
            errors: [...prev.errors, `${file.name}: ${err.message || 'Error desconocido'}`] 
          } : null);
        }
      }

      setBulkStatus(prev => prev ? { ...prev, currentName: '¡Completado!' } : null);
      
      setTimeout(() => {
        setBulkStatus(null);
        handleClose();
        onMangaCreated();
      }, 2000);

    } catch (error) {
      console.error('Error general en subida masiva:', error);
      alert('Ocurrió un error inesperado durante la subida masiva.');
      setBulkStatus(null);
    }
  };

  const handleRemovePage = (index: number) => {
    setChapterPages(prev => prev.filter((_, i) => i !== index));
  };

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newPages = [...chapterPages];
    const draggedPage = newPages[draggedIndex];

    newPages.splice(draggedIndex, 1);
    newPages.splice(index, 0, draggedPage);

    setChapterPages(newPages);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleCreateManga = async () => {
    if (!formData.title || !formData.title.trim()) {
      alert('El título es requerido');
      return;
    }

    setIsCreating(true);

    try {
      // Auto-category creation logic removed
      let categoriesToAdd = [...formData.selectedCategories];

      let thumbnailUrl: string | undefined = editingManga?.thumbnail_url || undefined;
      let coverUrl: string | undefined = editingManga?.cover_url || undefined;

      if (coverFromExistingPage) {
        thumbnailUrl = coverFromExistingPage.thumbnail;
        coverUrl = coverFromExistingPage.original;
      } else if (optimizedImage) {
        if (optimizedImage.originalBase64 === '') {
           thumbnailUrl = optimizedImage.thumbnail;
           coverUrl = optimizedImage.originalUnmodified;
        } else {
           try {
             setUploadingImages(true);
             setTotalImagesToUpload(2);
             setCurrentUploadingImage(1);
             setUploadProgress(0);

             const thumbnailResponse = await uploadImage(optimizedImage.thumbnail, `${formData.title}_thumb`);
             setUploadProgress(50);
             setCurrentUploadingImage(2);

             const coverResponse = await uploadImage(optimizedImage.originalUnmodified, `${formData.title}_cover`);
             setUploadProgress(100);

             thumbnailUrl = thumbnailResponse.data.url;
             coverUrl = coverResponse.data.url;
           } catch (error: any) {
             console.error('Error uploading cover images:', error);
             alert('Error al subir la portada. Continuar sin portada.');
           } finally {
             setUploadingImages(false);
             setUploadProgress(0);
           }
        }
      } else if (chapterPages.length > 0) {
        thumbnailUrl = chapterPages[0].webpDisplay;
        coverUrl = chapterPages[0].originalUnmodified;
      }

      if (isEditMode && editingManga) {
        const updateData: any = {
          title: formData.title.trim(),
          author: formData.name?.trim() || '',
          description: formData.description?.trim() || '',
          categoryIds: categoriesToAdd,
          is_decensored: formData.is_decensored,
          is_bn: formData.is_bn,
          is_color: formData.is_color,
        };

        if (thumbnailUrl) {
          updateData.thumbnail_url = thumbnailUrl;
        }

        if (coverUrl) {
          updateData.cover_url = coverUrl;
        }

        await updateManga(editingManga.id, updateData);

        if (chapterPages.length > 0) {
          // FIX: Always update if there are pages (handles reordering/deletions), or if there are new pages.
          // Previously it only acted if hasNewPages was true.
          if (chapterPages.length > 0) {
            try {
              setUploadingImages(true);
              const newPagesToUpload = chapterPages.filter(page => page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash='));
              
              let newPageUrls: string[] = [];
              let newOriginalPageUrls: string[] = [];

              if (newPagesToUpload.length > 0) {
                setTotalImagesToUpload(newPagesToUpload.length * 2);
                setCurrentUploadingImage(0);
                setUploadProgress(0);

                const webpImages = newPagesToUpload.map(page => page.webpDisplay);
                const originalImages = newPagesToUpload.map(page => page.originalUnmodified);
                
                const webpResponses = await uploadMultipleImages(
                  webpImages,
                  `${formData.title}_updated_webp`,
                  (current, _) => {
                    setCurrentUploadingImage(current);
                    setUploadProgress(Math.round((current / (newPagesToUpload.length * 2)) * 100));
                  }
                );

                const originalResponses = await uploadMultipleImages(
                  originalImages,
                  `${formData.title}_updated_original`,
                  (current, _) => {
                    setCurrentUploadingImage(newPagesToUpload.length + current);
                    setUploadProgress(Math.round(((newPagesToUpload.length + current) / (newPagesToUpload.length * 2)) * 100));
                  }
                );

                newPageUrls = webpResponses.map(res => res.data.url);
                newOriginalPageUrls = originalResponses.map(res => res.data.url);
              }

              // Mix the uploaded ones with the text parsed ones
              let uploadedIndex = 0;
              const allPageUrls = chapterPages.map(page => {
                 if (page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash=')) {
                    return newPageUrls[uploadedIndex++];
                 }
                 return page.webpDisplay; // Either existing or text mapped
              });

              uploadedIndex = 0;
              const allOriginalPageUrls = chapterPages.map(page => {
                 if (page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash=')) {
                    return newOriginalPageUrls[uploadedIndex++];
                 }
                 return page.original;
              });

              const allFormats = chapterPages.map(page => page.originalFormat);

              setUploadingImages(false);
              setUploadProgress(0);

              const firstChapter = editingManga.chapters?.[0];
              if (firstChapter) {
                await updateDoc(doc(db, 'chapters', firstChapter.id), {
                  pages: allPageUrls,
                  page_formats: allFormats,
                  original_pages: allOriginalPageUrls,
                  updated_at: Timestamp.now(),
                });
              } else {
                await createChapter({
                  manga_id: editingManga.id,
                  number: 1,
                  title: 'Páginas',
                  pages: allPageUrls,
                  page_formats: allFormats,
                  original_pages: allOriginalPageUrls,
                });
              }
            } catch (error: any) {
              console.error('Error updating chapter:', error);
              alert('Error al actualizar las páginas.');
            }
          }
        }

        onMangaCreated(editingManga.id);
      } else {
        const mangaPayload: any = {
          title: formData.title.trim(),
          author: formData.name?.trim() || '',
          categoryIds: categoriesToAdd,
          is_decensored: formData.is_decensored,
          is_bn: formData.is_bn,
          is_color: formData.is_color,
          section: currentSection,
        };

        if (formData.description?.trim()) {
          mangaPayload.description = formData.description.trim();
        }

        if (thumbnailUrl) {
          mangaPayload.thumbnail_url = thumbnailUrl;
        }

        if (coverUrl) {
          mangaPayload.cover_url = coverUrl;
        }

        const manga = await createManga(mangaPayload);

        if (!manga.id) {
          throw new Error('No se pudo obtener el ID del manga creado');
        }

        const mangaId = manga.id;

        if (chapterPages.length > 0) {
          try {
            setUploadingImages(true);
            const newPagesToUpload = chapterPages.filter(page => page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash='));
            
            let newPageUrls: string[] = [];
            let newOriginalPageUrls: string[] = [];

            if (newPagesToUpload.length > 0) {
              setTotalImagesToUpload(newPagesToUpload.length * 2);
              setCurrentUploadingImage(0);
              setUploadProgress(0);

              const webpImages = newPagesToUpload.map(page => page.webpDisplay);
              const originalImages = newPagesToUpload.map(page => page.originalUnmodified);

              const webpResponses = await uploadMultipleImages(
                webpImages,
                `${formData.title}_ch1_webp`,
                (current, _) => {
                  setCurrentUploadingImage(current);
                  setUploadProgress(Math.round((current / (newPagesToUpload.length * 2)) * 100));
                }
              );

              const originalResponses = await uploadMultipleImages(
                originalImages,
                `${formData.title}_ch1_original`,
                (current, _) => {
                  setCurrentUploadingImage(newPagesToUpload.length + current);
                  setUploadProgress(Math.round(((newPagesToUpload.length + current) / (newPagesToUpload.length * 2)) * 100));
                }
              );

              newPageUrls = webpResponses.map(res => res.data.url);
              newOriginalPageUrls = originalResponses.map(res => res.data.url);
            }

            let uploadedIndex = 0;
            const finalPageUrls = chapterPages.map(page => {
                 if (page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash=')) {
                    return newPageUrls[uploadedIndex++];
                 }
                 return page.webpDisplay;
            });

            uploadedIndex = 0;
            const finalOriginalPageUrls = chapterPages.map(page => {
                 if (page.originalBase64 !== '' && !page.original.includes('/stream/') && !page.original.includes('hash=')) {
                    return newOriginalPageUrls[uploadedIndex++];
                 }
                 return page.original;
            });

            const pageFormats = chapterPages.map(page => page.originalFormat);

            setUploadingImages(false);
            setUploadProgress(0);

            await createChapter({
              manga_id: mangaId,
              number: 1,
              title: 'Páginas',
              pages: finalPageUrls,
              page_formats: pageFormats,
              original_pages: finalOriginalPageUrls,
            });
          } catch (error: any) {
            console.error('Error creating chapter:', error);
            alert('Error al crear el capítulo. Por favor intenta de nuevo.');
          }
        }

        onMangaCreated(mangaId);
      }

      handleClose();
    } catch (error: any) {
      console.error('Error creating/updating manga:', error);

      let errorMessage = 'Error al guardar el manga. ';

      if (error.message) {
        errorMessage += error.message;
      } else if (error.code) {
        switch (error.code) {
          case 'permission-denied':
            errorMessage += 'No tienes permisos para realizar esta operación.';
            break;
          case 'unavailable':
            errorMessage += 'El servicio no está disponible. Verifica tu conexión.';
            break;
          case 'invalid-argument':
            errorMessage += 'Algunos datos no son válidos. Revisa el formulario.';
            break;
          default:
            errorMessage += `Código de error: ${error.code}`;
        }
      } else {
        errorMessage += 'Por favor intenta de nuevo.';
      }

      alert(errorMessage);
    } finally {
      setIsCreating(false);
      setUploadingImages(false);
      setUploadProgress(0);
    }
  };


  const handleSetCoverFromPage = (index: number) => {
    const page = chapterPages[index];
    const isExistingPage = !page.originalBase64;

    if (isExistingPage) {
      setCoverFromExistingPage({
        thumbnail: page.thumbnail,
        original: page.original,
      });
      setOptimizedImage(null);
    } else {
      const coverImage: OptimizedImage = {
        thumbnail: page.thumbnail,
        original: page.originalUnmodified,
        webpDisplay: page.originalUnmodified,
        webpCover: page.originalUnmodified,
        originalFormat: page.originalFormat,
        originalBase64: page.originalBase64,
        originalUnmodified: page.originalUnmodified,
      };
      setOptimizedImage(coverImage);
      setCoverFromExistingPage(null);
    }
    setPreviewUrl(page.thumbnail);

    setSelectedCoverPageIndex(index);
    setShowCoverSelector(false);
  };

  const handleClose = () => {
    setFormData({
      title: '',
      name: '',
      description: '',
      selectedCategories: [],
      is_decensored: false,
      is_bn: false,
      is_color: false,
    });
    setOptimizedImage(null);
    setCoverFromExistingPage(null);
    setPreviewUrl(null);
    setChapterPages([]);
    setUploadProgress(0);
    setUploadingImages(false);
    setCurrentUploadingImage(0);
    setTotalImagesToUpload(0);
    setShowCoverSelector(false);
    setSelectedCoverPageIndex(null);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-gradient-to-b from-[#1f1f1f] to-[#121212] rounded-2xl border border-gray-700/40 w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl">
        <div className="sticky top-0 bg-gradient-to-b from-[#2a2a2a] to-[#1f1f1f] border-b border-gray-700/30 px-8 py-6 flex items-center justify-between z-10">
          <div>
            <h2 className="text-2xl font-bold flex items-center gap-3">
              <div className="p-2 bg-gradient-to-br from-[#bb86fc] to-[#9966dd] rounded-lg shadow-lg shadow-[#bb86fc]/30">
                <BookOpen className="w-5 h-5 text-white" />
              </div>
              {isFolderMode ? 'Editar Carpeta' : isEditMode ? (currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? 'Editar Galería' : 'Editar Manga') : (currentSection === 'patreon' ? 'Subir Imágenes' : currentSection === 'onlyfans' ? 'Subir Only' : currentSection === 'grok' ? 'Subir Grok' : 'Crear Manga')}
            </h2>
            <p className="text-sm text-gray-400 mt-1.5">
              {isFolderMode ? 'Actualiza el nombre de la carpeta' : isEditMode ? (currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? 'Actualiza los detalles de la galería' : 'Actualiza los detalles de tu obra') : (currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? 'Sube nuevas imágenes exclusivas' : 'Comparte tu historia con el mundo')}
            </p>
          </div>
          <button onClick={handleClose} className="text-gray-500 hover:text-white hover:bg-white/10 transition-all p-2 rounded-lg">
            <X className="w-6 h-6" />
          </button>
        </div>

        <div className="p-8 space-y-5">
          <div className="bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-6 border border-gray-700/40 shadow-lg hover:border-gray-700/60 transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-1 h-5 bg-gradient-to-b from-[#bb86fc] to-[#7744cc] rounded-full"></div>
              <h3 className="text-sm font-semibold text-white tracking-wide uppercase">Información Principal</h3>
            </div>
            <div className="space-y-3.5">
              <div>
                <label className="block text-xs font-semibold text-gray-200 mb-2">
                  {isFolderMode ? 'Nombre de la Carpeta' : (currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? 'Título de la Galería' : 'Título del Manga')} <span className="text-red-400 font-bold">*</span>
                </label>
                <input
                  type="text"
                  name="title"
                  placeholder={currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? "Nombre de la sesión o imágenes" : "El nombre de tu obra maestra"}
                  value={formData.title}
                  onChange={handleInputChange}
                  onKeyPress={(e) => e.key === 'Enter' && isEditMode && !isCreating && handleCreateManga()}
                  className="w-full bg-[#1a1a1a] border border-gray-600/50 rounded-lg px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#bb86fc] focus:ring-2 focus:ring-[#bb86fc]/30 transition-all shadow-md hover:border-gray-600/70"
                />
              </div>
              
              {!isFolderMode && (
                <>
                  <div>
                    <label className="block text-xs font-semibold text-gray-200 mb-2">
                      Autor <span className="text-gray-500 font-normal">(opcional)</span>
                    </label>
                    <input
                      type="text"
                      name="name"
                      placeholder="Tu nombre o seudónimo"
                      value={formData.name}
                      onChange={handleInputChange}
                      onKeyPress={(e) => e.key === 'Enter' && isEditMode && !isCreating && handleCreateManga()}
                      className="w-full bg-[#1a1a1a] border border-gray-600/50 rounded-lg px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#bb86fc] focus:ring-2 focus:ring-[#bb86fc]/30 transition-all shadow-md hover:border-gray-600/70"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-200 mb-2">
                      Sinopsis <span className="text-gray-500 font-normal">(opcional)</span>
                    </label>
                    <textarea
                      name="description"
                      placeholder={currentSection === 'patreon' || currentSection === 'onlyfans' || currentSection === 'grok' ? "Cuéntanos detalles de estas imágenes..." : "Cuéntanos de qué trata tu manga, qué lo hace especial..."}
                      value={formData.description}
                      onChange={handleInputChange}
                      onKeyDown={(e) => e.key === 'Enter' && e.ctrlKey && isEditMode && !isCreating && handleCreateManga()}
                      rows={3}
                      className="w-full bg-[#1a1a1a] border border-gray-600/50 rounded-lg px-4 py-3 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-[#bb86fc] focus:ring-2 focus:ring-[#bb86fc]/30 transition-all shadow-md hover:border-gray-600/70 resize-none"
                    />
                  </div>
                </>
              )}
            </div>
          </div>

          {!isFolderMode && (
            <div className="bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-6 border border-gray-700/40 shadow-lg hover:border-gray-700/60 transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-1 h-5 bg-gradient-to-b from-[#bb86fc] to-[#7744cc] rounded-full"></div>
              <h3 className="text-sm font-semibold text-white tracking-wide uppercase">Clasificación</h3>
            </div>

            {/* Personajes */}
            <CategorySelector
              label="Personajes"
              type="character"
              categories={categories}
              selectedIds={formData.selectedCategories}
              onSelect={(id) => {
                if (!formData.selectedCategories.includes(id)) {
                  setFormData(prev => ({ ...prev, selectedCategories: [...prev.selectedCategories, id] }));
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
              selectedIds={formData.selectedCategories}
              onSelect={(id) => {
                if (!formData.selectedCategories.includes(id)) {
                  setFormData(prev => ({ ...prev, selectedCategories: [...prev.selectedCategories, id] }));
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
              selectedIds={formData.selectedCategories}
              onSelect={(id) => {
                if (!formData.selectedCategories.includes(id)) {
                  setFormData(prev => ({ ...prev, selectedCategories: [...prev.selectedCategories, id] }));
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
              selectedIds={formData.selectedCategories}
              onSelect={(id) => {
                if (!formData.selectedCategories.includes(id)) {
                  setFormData(prev => ({ ...prev, selectedCategories: [...prev.selectedCategories, id] }));
                }
              }}
              onRemove={handleRemoveCategory}
              onCreate={(name) => handleCreateCategory(name, 'tag')}
              onDeleteCategory={handleDeleteCategory}
              colorClass="text-pink-400"
              placeholder="Añadir etiqueta..."
            />

            {/* Clasificaciones Adicionales */}
            <div className="mt-6 pt-5 border-t border-gray-700/50 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-white">Sin censura</h4>
                  <p className="text-xs text-gray-400">Marcar como contenido sin censura</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={!!formData.is_decensored}
                    onChange={(e) => setFormData(prev => ({ ...prev, is_decensored: e.target.checked }))}
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-white">B/N</h4>
                  <p className="text-xs text-gray-400">Marcar como contenido Blanco y Negro</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={!!formData.is_bn}
                    onChange={(e) => {
                      const isChecked = e.target.checked;
                      setFormData(prev => ({ 
                        ...prev, 
                        is_bn: isChecked,
                        ...(isChecked ? { is_color: false } : {})
                      }));
                    }}
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                </label>
              </div>

              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-white">a color</h4>
                  <p className="text-xs text-gray-400">Marcar como contenido a color</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={!!formData.is_color}
                    onChange={(e) => {
                      const isChecked = e.target.checked;
                      setFormData(prev => ({ 
                        ...prev, 
                        is_color: isChecked,
                        ...(isChecked ? { is_bn: false } : {})
                      }));
                    }}
                  />
                  <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#bb86fc]"></div>
                </label>
              </div>
            </div>
          </div>
          )}

          {!isFolderMode && (
            <div className="bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-6 border border-gray-700/40 shadow-lg hover:border-gray-700/60 transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-1 h-5 bg-gradient-to-b from-[#bb86fc] to-[#7744cc] rounded-full"></div>
              <h3 className="text-sm font-semibold text-white tracking-wide uppercase">Portada</h3>
              <span className="text-xs text-gray-500 ml-auto">Opcional</span>
            </div>

            {isProcessing && (
              <div className="mb-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[#bb86fc]">Procesando portada...</span>
                </div>
                <div className="w-full bg-gray-700/40 rounded-full h-2 overflow-hidden border border-[#bb86fc]/30">
                  <div className="bg-gradient-to-r from-[#bb86fc] to-[#9966dd] h-full transition-all duration-300 ease-out animate-pulse" style={{ width: '100%' }} />
                </div>
              </div>
            )}

            {previewUrl && !isProcessing && (
              <div className="mb-4 relative group max-w-xs mx-auto">
                <ImageLoader
                  src={previewUrl}
                  alt="Preview"
                  aspectRatio="3/4"
                  objectFit="cover"
                  loading="eager"
                  className="rounded-xl border border-gray-600 shadow-2xl shadow-[#bb86fc]/20"
                />
                <div className="absolute inset-0 rounded-xl bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button
                    onClick={() => {
                      setOptimizedImage(null);
                      setPreviewUrl(null);
                      setSelectedCoverPageIndex(null);
                    }}
                    className="bg-red-600/80 hover:bg-red-600 text-white p-2 rounded-lg transition-all shadow-lg"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
                {selectedCoverPageIndex !== null && (
                  <div className="absolute bottom-2 left-2 bg-green-600/90 text-white text-xs px-2.5 py-1 rounded-lg font-semibold">
                    Página {selectedCoverPageIndex + 1}
                  </div>
                )}
              </div>
            )}

            <div className="flex gap-3 mb-4">
              <label className="flex-1 border-2 border-dashed border-gray-600/50 rounded-xl p-6 cursor-pointer hover:border-[#bb86fc]/50 hover:bg-[#bb86fc]/5 transition-all block group">
                <div className="flex flex-col items-center gap-2">
                  <div className="w-12 h-12 bg-gradient-to-br from-[#bb86fc] to-[#9966dd] rounded-xl flex items-center justify-center shadow-lg shadow-[#bb86fc]/40 group-hover:scale-110 group-hover:shadow-[#bb86fc]/60 transition-all">
                    {isProcessing ? (
                      <LoadingSpinner size={24} borderWidth={2} />
                    ) : (
                      <Plus className="w-6 h-6 text-white" />
                    )}
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-white mb-0.5">
                      {isProcessing ? 'Procesando...' : 'Subir portada'}
                    </p>
                    <p className="text-xs text-gray-400">Archivo</p>
                  </div>
                </div>
                <input
                  type="file"
                  accept="image/*"
                  onChange={handleFileChange}
                  disabled={isProcessing}
                  className="hidden"
                />
              </label>

              {chapterPages.length > 0 && (
                <button
                  onClick={() => setShowCoverSelector(!showCoverSelector)}
                  className="flex-1 border-2 border-dashed border-gray-600/50 rounded-xl p-6 hover:border-[#bb86fc]/50 hover:bg-[#bb86fc]/5 transition-all group flex flex-col items-center justify-center gap-2 bg-gradient-to-br from-[#1a1a1a] to-[#0f0f0f]"
                >
                  <div className="w-12 h-12 bg-gradient-to-br from-[#9966dd] to-[#bb86fc] rounded-xl flex items-center justify-center shadow-lg shadow-[#bb86fc]/40 group-hover:scale-110 group-hover:shadow-[#bb86fc]/60 transition-all">
                    <ImageIcon className="w-6 h-6 text-white" />
                  </div>
                  <div className="text-center">
                    <p className="text-xs font-semibold text-white mb-0.5">
                      Elegir página
                    </p>
                    <p className="text-xs text-gray-400">{chapterPages.length} disponibles</p>
                  </div>
                </button>
              )}
            </div>
          </div>
          )}

          {!isFolderMode && (
            <div className="bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-6 border border-gray-700/40 shadow-lg hover:border-gray-700/60 transition-all">
            <div className="flex items-center gap-3 mb-5">
              <div className="w-1 h-5 bg-gradient-to-b from-[#bb86fc] to-[#7744cc] rounded-full"></div>
              <h3 className="text-sm font-semibold text-white tracking-wide uppercase">Páginas del Capítulo</h3>
              <span className="text-xs text-gray-500 ml-auto">Opcional</span>
              <button
                onClick={() => setShowBatchSizeModal(true)}
                className="bg-[#1a1a1a] hover:bg-[#242424] border border-gray-600/50 hover:border-[#bb86fc]/50 text-gray-300 hover:text-[#bb86fc] p-2 rounded-lg transition-all flex items-center gap-1.5 text-xs font-medium"
                title="Configurar tamaño de lote de subida"
              >
                <Settings2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Subida: {batchSize === 0 ? 'Sin límite' : `${batchSize} por lote`}</span>
              </button>
            </div>

            {isProcessingPages && (
              <div className="mb-5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs font-semibold text-[#bb86fc]">
                    Procesando enlaces...
                  </span>
                </div>
                <div className="w-full bg-gray-700/40 rounded-full h-2 overflow-hidden border border-[#bb86fc]/30">
                  <div
                    className="bg-gradient-to-r from-[#bb86fc] to-[#9966dd] h-full transition-all duration-300 ease-out animate-pulse"
                    style={{ width: `100%` }}
                  />
                </div>
              </div>
            )}

            {chapterPages.length > 0 && !isProcessingPages && (
              <div className="mb-5">
                <div className="flex items-center gap-2 mb-3">
                  <GripVertical className="w-3.5 h-3.5 text-gray-500" />
                  <p className="text-xs text-gray-400">
                    {chapterPages.length} página{chapterPages.length !== 1 ? 's' : ''} • Arrastra para reordenar
                  </p>
                </div>
                <div className="grid grid-cols-4 gap-2">
                  {chapterPages.map((page, index) => (
                    <div
                      key={index}
                      draggable
                      onDragStart={() => handleDragStart(index)}
                      onDragOver={(e) => handleDragOver(e, index)}
                      onDragEnd={handleDragEnd}
                      style={{
                        animationDelay: `${index * 40}ms`,
                      }}
                      className={`relative group cursor-move opacity-0 animate-[fadeIn_0.7s_ease-out_forwards] ${draggedIndex === index ? 'opacity-50 scale-95' : 'hover:scale-105'
                        } transition-all duration-200`}
                    >
                      <div className="relative overflow-hidden w-full aspect-[3/4] rounded-lg border border-gray-600/50 shadow-md bg-black">
                        <div className="absolute inset-0 flex items-center justify-center z-10 transition-opacity duration-300">
                          <div
                            className="rounded-full animate-spin"
                            style={{
                              width: '24px',
                              height: '24px',
                              borderWidth: '2px',
                              borderStyle: 'solid',
                              borderColor: 'rgba(187, 134, 252, 0.2)',
                              borderTopColor: '#bb86fc',
                              animation: 'spin 0.6s linear infinite',
                            }}
                          />
                        </div>
                        <img
                          src={page.thumbnail}
                          alt={`Página ${index + 1}`}
                          className="w-full h-full object-cover transition-all duration-700 ease-out transform-gpu group-hover:scale-[1.08] group-hover:shadow-[#bb86fc]/30 opacity-0 scale-95"
                          onLoad={(e) => {
                            e.currentTarget.classList.remove('opacity-0', 'scale-95');
                            e.currentTarget.classList.add('opacity-100', 'scale-100');
                            const spinner = e.currentTarget.parentElement?.querySelector('div:nth-child(1)');
                            if (spinner) spinner.classList.add('opacity-0', 'pointer-events-none');
                          }}
                        />
                      </div>
                      <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
                        <GripVertical className="w-4 h-4 text-white/70" />
                        <button
                          onClick={() => handleRemovePage(index)}
                          className="bg-red-600/80 hover:bg-red-600 text-white p-1.5 rounded-lg transition-all shadow-lg"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                      <div className="absolute top-1.5 left-1.5 bg-black/80 text-white text-xs px-2 py-0.5 rounded-md font-semibold">
                        {index + 1}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {chapterPages.length === 0 && (
              <label className="border-2 border-dashed border-gray-600/50 rounded-xl p-8 text-center hover:border-[#bb86fc]/50 hover:bg-[#bb86fc]/5 transition-all block group">
                <div className="w-14 h-14 bg-gradient-to-br from-[#bb86fc] to-[#9966dd] rounded-xl flex items-center justify-center mx-auto mb-4 shadow-lg shadow-[#bb86fc]/40 group-hover:scale-110 group-hover:shadow-[#bb86fc]/60 transition-all">
                  {isProcessingPages ? (
                    <LoadingSpinner size={24} borderWidth={2} />
                  ) : (
                    <ImageIcon className="w-7 h-7 text-white" />
                  )}
                </div>
                <p className="text-sm font-semibold text-white mb-2">
                  {isProcessingPages ? `Procesando...` : 'Sube tu archivo TXT'}
                </p>
                
                <div className="flex flex-col gap-4 max-w-lg mx-auto mt-4">
                  <div className="relative">
                    <span className="bg-[#1a1a1a] hover:bg-[#242424] border border-gray-600/50 text-white px-4 py-2 rounded-lg text-sm font-medium transition-all block w-max mx-auto cursor-pointer relative z-10">
                      Seleccionar Archivo .txt
                    </span>
                    <input
                      type="file"
                      accept=".txt"
                      multiple
                      onChange={handleChapterPagesChange}
                      disabled={isProcessingPages || (bulkStatus?.uploading ?? false)}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-20"
                    />
                  </div>
                </div>
              </label>
            )}
          </div>
          )}

          {bulkStatus?.uploading && (
            <div className="mb-6 bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-5 border border-[#bb86fc]/30 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <LoadingSpinner size={16} borderWidth={2} />
                  <span className="text-sm font-semibold text-white">
                    Subida Masiva: {bulkStatus.current} de {bulkStatus.total}
                  </span>
                </div>
                <span className="text-sm font-bold text-[#bb86fc]">
                  {Math.round((bulkStatus.current / bulkStatus.total) * 100)}%
                </span>
              </div>
              <div className="w-full bg-gray-700/40 rounded-full h-3 overflow-hidden border border-[#bb86fc]/40 shadow-inner">
                <div
                  className="bg-gradient-to-r from-[#bb86fc] via-[#9966dd] to-[#bb86fc] h-full transition-all duration-500 ease-out relative overflow-hidden"
                  style={{ width: `${(bulkStatus.current / bulkStatus.total) * 100}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
                </div>
              </div>
              <p className="text-xs text-[#bb86fc] mt-2 font-medium">
                {bulkStatus.currentName}
              </p>
              {bulkStatus.errors.length > 0 && (
                <div className="mt-3 text-[10px] text-red-400 max-h-20 overflow-y-auto bg-black/20 p-2 rounded border border-red-500/20">
                  <p className="font-bold mb-1">Errores ({bulkStatus.errors.length}):</p>
                  {bulkStatus.errors.map((err, i) => (
                    <div key={i}>• {err}</div>
                  ))}
                </div>
              )}
              <p className="text-xs text-gray-400 mt-2 text-center">
                Procesando archivos... Por favor espera.
              </p>
            </div>
          )}

          {uploadingImages && (
            <div className="mb-6 bg-gradient-to-br from-[#242424] to-[#1a1a1a] rounded-xl p-5 border border-[#bb86fc]/30 shadow-xl">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <LoadingSpinner size={16} borderWidth={2} />
                  <span className="text-sm font-semibold text-white">
                    Subiendo imagen {currentUploadingImage} de {totalImagesToUpload}
                  </span>
                </div>
                <span className="text-sm font-bold text-[#bb86fc]">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-700/40 rounded-full h-3 overflow-hidden border border-[#bb86fc]/40 shadow-inner">
                <div
                  className="bg-gradient-to-r from-[#bb86fc] via-[#9966dd] to-[#bb86fc] h-full transition-all duration-500 ease-out relative overflow-hidden"
                  style={{ width: `${uploadProgress}%` }}
                >
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-pulse" />
                </div>
              </div>
              <p className="text-xs text-gray-400 mt-2 text-center">
                Por favor no cierres esta ventana...
              </p>
            </div>
          )}

          <div className="flex gap-3 pt-6 border-t border-gray-700/50">
            {isEditMode && onDelete && (
              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 text-red-500 px-4 py-3 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 mr-auto"
              >
                <Trash2 className="w-4 h-4" />
                Eliminar
              </button>
            )}
            <button
              onClick={handleClose}
              disabled={isCreating || uploadingImages}
              className="flex-1 bg-[#1a1a1a] border border-gray-600/50 hover:border-gray-500 hover:bg-[#242424] text-white px-5 py-3 rounded-lg font-semibold text-sm transition-all shadow-md disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Cancelar
            </button>
            <button
              onClick={handleCreateManga}
              disabled={isCreating || uploadingImages || !formData.title.trim()}
            >
              {uploadingImages ? 'Subiendo imágenes...' : isCreating ? (isEditMode ? 'Actualizando...' : 'Creando...') : (isEditMode ? 'Guardar Cambios' : 'Crear Manga')}
            </button>
          </div>
        </div>
      </div>

      {showCoverSelector && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-b from-[#1f1f1f] to-[#121212] rounded-2xl border border-gray-700/40 w-full max-w-2xl max-h-[80vh] shadow-2xl overflow-hidden flex flex-col">
            <div className="bg-gradient-to-b from-[#2a2a2a]/80 to-[#1f1f1f]/80 border-b border-gray-700/30 px-6 py-4 flex items-center justify-between flex-shrink-0">
              <div>
                <h2 className="text-xl font-bold text-white">Selecciona portada</h2>
                <p className="text-xs text-gray-400 mt-1">Elige una página para usar como portada del manga</p>
              </div>
              <button
                onClick={() => setShowCoverSelector(false)}
                className="text-gray-500 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/10 flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto flex-1 p-6">
              <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                {chapterPages.map((page, index) => (
                  <button
                    key={index}
                    onClick={() => handleSetCoverFromPage(index)}
                    className={`group relative aspect-[3/4] rounded-lg overflow-hidden transition-all duration-300 hover:scale-105 border-2 ${selectedCoverPageIndex === index
                      ? 'border-green-500 shadow-lg shadow-green-500/40'
                      : 'border-gray-600/50 hover:border-[#bb86fc]/50'
                      }`}
                  >
                    <div className="absolute inset-0 overflow-hidden bg-black flex items-center justify-center">
                      <div className="absolute inset-0 flex items-center justify-center z-10 transition-opacity duration-300">
                        <div
                          className="rounded-full animate-spin"
                          style={{
                            width: '20px',
                            height: '20px',
                            borderWidth: '2px',
                            borderStyle: 'solid',
                            borderColor: 'rgba(187, 134, 252, 0.2)',
                            borderTopColor: '#bb86fc',
                            animation: 'spin 0.6s linear infinite',
                          }}
                        />
                      </div>
                      <img
                        src={page.thumbnail}
                        alt={`Página ${index + 1}`}
                        className="w-full h-full object-cover transition-all duration-700 ease-out transform-gpu group-hover:scale-[1.10] opacity-0 scale-95"
                        onLoad={(e) => {
                          e.currentTarget.classList.remove('opacity-0', 'scale-95');
                          e.currentTarget.classList.add('opacity-100', 'scale-100');
                          const spinner = e.currentTarget.parentElement?.querySelector('div:nth-child(1)');
                          if (spinner) spinner.classList.add('opacity-0', 'pointer-events-none');
                        }}
                      />
                    </div>
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                      <div className="bg-[#bb86fc]/90 text-white px-3 py-1.5 rounded-lg font-semibold text-sm">
                        Seleccionar
                      </div>
                    </div>
                    <div className="absolute bottom-2 left-2 bg-black/80 text-white text-xs px-2 py-1 rounded-md font-semibold">
                      {index + 1}
                    </div>
                    {selectedCoverPageIndex === index && (
                      <div className="absolute top-2 right-2 bg-green-600/90 text-white px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 font-semibold text-xs">
                        <div className="w-2 h-2 bg-white rounded-full"></div>
                        Seleccionado
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-gradient-to-b from-[#1f1f1f]/80 to-[#1a1a1a]/80 border-t border-gray-700/30 px-6 py-4 flex items-center justify-end gap-3 flex-shrink-0">
              <button
                onClick={() => setShowCoverSelector(false)}
                className="bg-[#1a1a1a] border border-gray-600/50 hover:border-gray-500 hover:bg-[#242424] text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all"
              >
                Cancelar
              </button>
              <button
                onClick={() => setShowCoverSelector(false)}
                className="bg-gradient-to-r from-[#bb86fc] to-[#9966dd] hover:from-[#9966dd] hover:to-[#7744cc] text-white px-4 py-2 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-[#bb86fc]/40 hover:shadow-[#bb86fc]/60"
              >
                Confirmar
              </button>
            </div>
          </div>
        </div>
      )}

      {showBatchSizeModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-gradient-to-b from-[#1f1f1f] to-[#121212] rounded-2xl border border-gray-700/40 w-full max-w-md shadow-2xl">
            <div className="bg-gradient-to-b from-[#2a2a2a]/80 to-[#1f1f1f]/80 border-b border-gray-700/30 px-6 py-4 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-gradient-to-br from-[#bb86fc] to-[#9966dd] rounded-lg shadow-lg shadow-[#bb86fc]/30">
                  <Settings2 className="w-5 h-5 text-white" />
                </div>
                <div>
                  <h2 className="text-xl font-bold text-white">Configurar Subida</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Tamaño de lote de imágenes</p>
                </div>
              </div>
              <button
                onClick={() => setShowBatchSizeModal(false)}
                className="text-gray-500 hover:text-white transition-colors p-1.5 rounded-lg hover:bg-white/10"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-[#1a1a1a] border border-gray-700/40 rounded-lg p-4 mb-4">
                <h3 className="text-xs font-semibold text-gray-300 mb-2">Opciones disponibles:</h3>
                <ul className="text-xs text-gray-400 space-y-1.5">
                  <li>• 1 por lote: Más lento pero más estable</li>
                  <li>• 10 por lote: Balance entre velocidad y estabilidad (predeterminado)</li>
                  <li>• 50 por lote: Más rápido para muchas imágenes</li>
                  <li>• Sin límite: Sube todas las imágenes simultáneamente</li>
                </ul>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => {
                    setBatchSize(1);
                    saveBatchSize(1);
                  }}
                  className={`p-4 rounded-lg border-2 transition-all ${batchSize === 1
                    ? 'border-[#bb86fc] bg-[#bb86fc]/10 shadow-lg shadow-[#bb86fc]/30'
                    : 'border-gray-600/50 hover:border-gray-600 bg-[#1a1a1a]'
                    }`}
                >
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white mb-1">1</div>
                    <div className="text-xs text-gray-400">Por lote</div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setBatchSize(10);
                    saveBatchSize(10);
                  }}
                  className={`p-4 rounded-lg border-2 transition-all ${batchSize === 10
                    ? 'border-[#bb86fc] bg-[#bb86fc]/10 shadow-lg shadow-[#bb86fc]/30'
                    : 'border-gray-600/50 hover:border-gray-600 bg-[#1a1a1a]'
                    }`}
                >
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white mb-1">10</div>
                    <div className="text-xs text-gray-400">Por lote</div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setBatchSize(50);
                    saveBatchSize(50);
                  }}
                  className={`p-4 rounded-lg border-2 transition-all ${batchSize === 50
                    ? 'border-[#bb86fc] bg-[#bb86fc]/10 shadow-lg shadow-[#bb86fc]/30'
                    : 'border-gray-600/50 hover:border-gray-600 bg-[#1a1a1a]'
                    }`}
                >
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white mb-1">50</div>
                    <div className="text-xs text-gray-400">Por lote</div>
                  </div>
                </button>

                <button
                  onClick={() => {
                    setBatchSize(0);
                    saveBatchSize(999999);
                  }}
                  className={`p-4 rounded-lg border-2 transition-all ${batchSize === 0 || batchSize >= 999999
                    ? 'border-[#bb86fc] bg-[#bb86fc]/10 shadow-lg shadow-[#bb86fc]/30'
                    : 'border-gray-600/50 hover:border-gray-600 bg-[#1a1a1a]'
                    }`}
                >
                  <div className="text-center">
                    <div className="text-2xl font-bold text-white mb-1">∞</div>
                    <div className="text-xs text-gray-400">Sin límite</div>
                  </div>
                </button>
              </div>

              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                <p className="text-green-400 text-xs font-semibold">
                  Configuración guardada: {batchSize === 0 || batchSize >= 999999 ? 'Sin límite' : `${batchSize} imagen${batchSize !== 1 ? 'es' : ''} por lote`}
                </p>
              </div>

              <button
                onClick={() => setShowBatchSizeModal(false)}
                className="w-full bg-gradient-to-r from-[#bb86fc] to-[#9966dd] hover:from-[#9966dd] hover:to-[#7744cc] text-white px-4 py-3 rounded-lg font-semibold text-sm transition-all shadow-lg shadow-[#bb86fc]/40 hover:shadow-[#bb86fc]/60"
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      <ConfirmModal
        isOpen={!!pendingBulkFiles}
        onClose={() => setPendingBulkFiles(null)}
        onConfirm={() => {
          if (pendingBulkFiles) {
            handleBulkUpload(pendingBulkFiles);
            setPendingBulkFiles(null);
          }
        }}
        title="Subida Masiva"
        message={`Estás a punto de subir ${pendingBulkFiles?.length} archivos TXT. Se creará un manga por cada archivo usando la información de Autor y Categorías actual.`}
        confirmText="Empezar Subida"
      />

      <ConfirmModal
        isOpen={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        onConfirm={() => {
          if (editingManga && onDelete) {
            onDelete(editingManga.id);
            onClose();
          }
        }}
        title="Eliminar Manga"
        message="¿Estás seguro de que deseas eliminar este manga? Esta acción no se puede deshacer y se borrarán todos sus capítulos."
        confirmText="Eliminar permanentemente"
        variant="danger"
      />
    </div>
  );
}
