import React, { useState, useRef, useEffect } from 'react';
import { DataItem, ContentBlock } from '../types';
import { Button } from './Button';
import { TipTapEditor } from './TipTapEditor';
import { BlockEditorModal } from './BlockEditorModal';
import { IconPicker } from './IconPicker';
import { ArrowLeft, Download, ExternalLink, Trash2, Edit2, Plus, Save, X, Check, Copy, Sparkles, Link as LinkIcon, ClipboardCheck } from 'lucide-react';
import { ConfirmDialog } from './ConfirmDialog';
import { Editor } from '@tiptap/react';
import { FishAudioPlayer } from './FishAudioPlayer';
import { MarkdownRenderer } from './MarkdownRenderer';


interface DetailViewProps {
  item: DataItem;
  onBack: () => void;
  onUpdate: (data: Omit<DataItem, 'id' | 'createdAt'>) => void;
  onDelete: (id: string) => void;
  onDuplicate?: () => void;
  onTagClick?: (tag: string) => void;
  isEditable?: boolean;
}

export const DetailView: React.FC<DetailViewProps> = ({ item, onBack, onUpdate, onDelete, onDuplicate, isEditable = false }) => {
  const getFishAudioId = (url: string | undefined) => {
    if (!url) return null;
    const match = url.match(/fish\.audio\/(?:[a-z]{2}\/)?(?:app\/)?m\/([a-f0-9]+)/i);
    return match ? match[1] : null;
  };



  const [isEditMode, setIsEditMode] = useState(false);
  const [editedItem, setEditedItem] = useState<DataItem>(item);
  const [editingBlockId, setEditingBlockId] = useState<string | null>(null);
  const [showEditTab, setShowEditTab] = useState(true);
  const [categoryInput, setCategoryInput] = useState('');
  const [blockEditor, setBlockEditor] = useState<{
    isOpen: boolean;
    type: 'quote' | 'code';
  }>({
    isOpen: false,
    type: 'quote'
  });

  const activeEditorRef = useRef<Editor | null>(null);
  const summaryEditorRef = useRef<Editor | null>(null);
  const summaryTextareaRef = useRef<HTMLTextAreaElement>(null);
  const [pendingModalOpen, setPendingModalOpen] = useState(false);

  const getCardClasses = (style?: 'bordered' | 'transparent' | 'filled') => {
    switch (style) {
      case 'filled':
        return 'bg-surface border border-white/5 shadow-xl';
      case 'transparent':
        return 'bg-transparent border-none shadow-none';
      case 'bordered':
      default:
        return 'bg-transparent border border-white/10 shadow-none'; // Default to "bordered" as per latest "transparent" refined look
    }
  };

  const [confirmDialog, setConfirmDialog] = useState<{
    isOpen: boolean;
    title: string;
    message: string;
    onConfirm: () => void;
  }>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => { }
  });

  // AI Modal State removed

  // Auto-resize summary textarea
  useEffect(() => {
    if (summaryTextareaRef.current) {
      summaryTextareaRef.current.style.height = 'auto';
      summaryTextareaRef.current.style.height = summaryTextareaRef.current.scrollHeight + 'px';
    }
  }, [editedItem.summary, isEditMode]);

  // Effect to open modal once editor is ready if pending
  useEffect(() => {
    if (pendingModalOpen && activeEditorRef.current && editingBlockId) {
      setBlockEditor(prev => ({ ...prev, isOpen: true }));
      setPendingModalOpen(false);
    }
  }, [pendingModalOpen, editingBlockId, activeEditorRef.current]);

  const handleSaveChanges = () => {
    onUpdate({
      icon: editedItem.icon,
      title: editedItem.title,
      summary: editedItem.summary,
      content: editedItem.content || '',
      tags: editedItem.tags,
      categories: editedItem.categories,
      blocks: editedItem.blocks,
      visitUrl: editedItem.visitUrl,
      downloadUrl: editedItem.downloadUrl,
      linkGroups: editedItem.linkGroups,
      cardStyle: editedItem.cardStyle
    });
    setIsEditMode(false);
  };

  const handleCancelEdit = () => {
    setEditedItem(item);
    setIsEditMode(false);
    setEditingBlockId(null);
    setEditingBlockId(null);
  };

  const handleAddBlockImmediately = (blockType: 'markdown' | 'raw-markdown' = 'markdown') => {
    const newBlock: ContentBlock = {
      id: Date.now().toString(),
      type: blockType,
      content: blockType === 'raw-markdown' ? '' : {
        type: 'doc',
        content: [
          {
            type: 'paragraph',
          }
        ]
      }
    };

    setEditedItem(prev => ({
      ...prev,
      blocks: [...(prev.blocks || []), newBlock]
    }));

    setEditingBlockId(newBlock.id);
  };

  const handleBlockUpdate = (blockId: string, content: any) => {
    setEditedItem(prev => ({
      ...prev,
      blocks: prev.blocks?.map(b => b.id === blockId ? { ...b, content } : b) || []
    }));
  };

  const handleDeleteBlock = (blockId: string) => {
    setConfirmDialog({
      isOpen: true,
      title: 'Eliminar Bloque',
      message: '¿Estás seguro de que quieres eliminar este bloque de contenido? Esta acción no se puede deshacer.',
      onConfirm: () => {
        setEditedItem(prev => ({
          ...prev,
          blocks: prev.blocks?.filter(b => b.id !== blockId) || []
        }));
      }
    });
  };

  const handleBlockDoubleClick = (type: 'code' | 'quote', index: number, blockId: string) => {
    // Switch to edit mode for this block
    const block = editedItem.blocks?.find(b => b.id === blockId);
    if (block) {
      setEditingBlockId(blockId);
      setBlockEditor({ isOpen: false, type }); // Will open in effect
      setPendingModalOpen(true);
    }
  };

  if (isEditMode) {
    return (
      <div className="max-w-5xl mx-auto animate-fade-in pb-20">
        <div className="flex items-center justify-between mb-6">
          <button
            onClick={handleCancelEdit}
            className="flex items-center gap-2 text-gray-400 hover:text-primary transition-colors text-sm font-medium"
          >
            <ArrowLeft size={18} /> Cancelar
          </button>
          <Button onClick={handleSaveChanges}>
            <Save size={18} /> Guardar Cambios
          </Button>
        </div>



        <div className="flex gap-2 mb-6">
          <button
            onClick={() => setShowEditTab(true)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${showEditTab
              ? 'bg-primary text-background'
              : 'bg-white/5 text-gray-400 hover:text-white border border-white/10'
              }`}
          >
            Edit
          </button>
          <button
            onClick={() => setShowEditTab(false)}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${!showEditTab
              ? 'bg-primary text-background'
              : 'bg-white/5 text-gray-400 hover:text-white border border-white/10'
              }`}
          >
            Preview
          </button>
        </div>

        <div className="relative mb-8 rounded-2xl p-6 border border-white/10 space-y-6" style={{ display: showEditTab ? 'block' : 'none' }}>
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Título</label>
            <div className="flex gap-4 items-start">
              <IconPicker
                selectedIcon={editedItem.icon}
                onSelect={(icon) => setEditedItem(prev => ({ ...prev, icon }))}
              />
              <div className="flex-grow bg-background border border-white/10 rounded-lg overflow-hidden focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
                <TipTapEditor
                  content={editedItem.title}
                  onUpdate={(content) => setEditedItem(prev => ({ ...prev, title: content }))}
                  isEditable={true}
                  showToolbarOnFocus={true}
                  className="px-3 py-2 min-h-[46px]"
                  dense={true}
                />
              </div>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-400">Resumen</label>
            </div>
            <div className="bg-background border border-white/10 rounded-lg overflow-hidden focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
              <TipTapEditor
                content={editedItem.summary}
                onUpdate={(content) => {
                  // Only update state if it comes from internal changes that usually sync automaticallly,
                  // but here we just keep the simple binding.
                  setEditedItem(prev => ({ ...prev, summary: content }));
                }}
                isEditable={true}
                editorRef={summaryEditorRef}
                showToolbarOnFocus={true}
                className="px-3 py-2 min-h-[40px]"
                dense={true}
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Categorías</label>
            <div className="mb-4">
              <div className="flex flex-wrap gap-2 mb-2">
                {(editedItem.categories || []).map((cat, idx) => (
                  <span key={idx} className="flex items-center gap-1 text-sm text-primary bg-primary/10 px-3 py-1 rounded-lg border border-primary/30 uppercase tracking-wide font-medium">
                    {cat}
                    <button 
                      type="button" 
                      onClick={() => setEditedItem(prev => ({ 
                        ...prev, 
                        categories: prev.categories?.filter((_, i) => i !== idx) 
                      }))} 
                      className="ml-1 hover:text-red-400"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
              <input
                type="text"
                value={categoryInput}
                onChange={(e) => setCategoryInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    const val = categoryInput.trim();
                    if (val && !(editedItem.categories || []).includes(val)) {
                      setEditedItem(prev => ({
                        ...prev,
                        categories: [...(prev.categories || []), val]
                      }));
                      setCategoryInput('');
                    }
                  }
                }}
                className="w-full bg-background border border-white/10 rounded-lg p-3 text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
                placeholder="Escribe una categoría y presiona Enter..."
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Tags</label>
            <input
              type="text"
              value={editedItem.tags.join(', ')}
              onChange={(e) => setEditedItem(prev => ({ ...prev, tags: e.target.value.split(',').map(t => t.trim()).filter(Boolean) }))}
              className="w-full bg-background border border-white/10 rounded-lg p-3 text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
              placeholder="tag1, tag2, tag3"
            />
            <div className="flex justify-end mt-2">
              <button
                type="button"
                onClick={() => {
                  const stopWords = new Set([
                    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'y', 'o', 'pero', 'si', 'no',
                    'de', 'del', 'a', 'al', 'en', 'con', 'por', 'para', 'sin', 'sobre', 'entre',
                    'mi', 'tu', 'su', 'nuestro', 'vuestro', 'sus', 'mis', 'tus',
                    'que', 'cual', 'quien', 'donde', 'cuando', 'como', 'porque',
                    'es', 'son', 'fue', 'fueron', 'era', 'eran', 'está', 'están',
                    'este', 'esta', 'ese', 'esa', 'aquel', 'aquella', 'esto', 'eso', 'aquello',
                    'hizo', 'hacer', 'todo', 'toda', 'todos', 'todas', 'muy', 'más', 'tan',
                    'ya', 'hoy', 'ayer', 'ahora', 'después', 'antes', 'mira', 'voy'
                  ]);

                  // Function to strip HTML tags
                  const stripHtml = (html: any) => {
                    if (typeof html !== 'string') return '';
                    const tmp = document.createElement("DIV");
                    tmp.innerHTML = html;
                    return tmp.textContent || tmp.innerText || "";
                  };

                  const titleText = stripHtml(editedItem.title);
                  const summaryText = stripHtml(editedItem.summary);

                  const text = `${titleText} ${summaryText}`.toLowerCase();
                  const words = text.replace(/[^\w\sáéíóúñü]/g, '').split(/\s+/);

                  const uniqueKeywords = new Set<string>();

                  words.forEach(word => {
                    if (word.length > 2 && !stopWords.has(word)) {
                      uniqueKeywords.add(word);
                    }
                  });

                  // Limit to 15 tags
                  const keywordsArray = Array.from(uniqueKeywords).slice(0, 15);
                  setEditedItem(prev => ({ ...prev, tags: keywordsArray }));
                }}
                className="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1 bg-primary/10 px-3 py-1.5 rounded-lg border border-primary/20"
                title="Extraer palabras clave automáticamente"
              >
                <Sparkles size={14} /> Generar Automáticamente
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">URL Visitar</label>
              <input
                type="url"
                value={editedItem.visitUrl || ''}
                onChange={(e) => setEditedItem(prev => ({ ...prev, visitUrl: e.target.value }))}
                className="w-full bg-background border border-white/10 rounded-lg p-3 text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
                placeholder="https://..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">URL Descargar</label>
              <input
                type="url"
                value={editedItem.downloadUrl || ''}
                onChange={(e) => setEditedItem(prev => ({ ...prev, downloadUrl: e.target.value }))}
                className="w-full bg-background border border-white/10 rounded-lg p-3 text-white focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
                placeholder="https://..."
              />
            </div>
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-400">Grupos de Enlaces Extra</label>
              <button
                type="button"
                onClick={() => setEditedItem(prev => ({ 
                  ...prev, 
                  linkGroups: [...(prev.linkGroups || []), { id: Date.now().toString(), title: `Opción ${(prev.linkGroups?.length || 0) + 1}` }] 
                }))}
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
              >
                + Añadir Enlace Extra
              </button>
            </div>
            
            {(editedItem.linkGroups || []).map((group) => (
              <div key={group.id} className="p-4 bg-background/50 rounded-xl border border-white/5 space-y-4 relative group">
                <button
                  type="button"
                  onClick={() => setEditedItem(prev => ({ ...prev, linkGroups: prev.linkGroups?.filter(g => g.id !== group.id) }))}
                  className="absolute top-2 right-2 p-1 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Eliminar grupo"
                >
                  <X size={16} />
                </button>
                <div>
                  <input
                    type="text"
                    value={group.title}
                    onChange={e => setEditedItem(prev => ({ ...prev, linkGroups: prev.linkGroups?.map(g => g.id === group.id ? { ...g, title: e.target.value } : g) }))}
                    placeholder="Título del grupo de enlaces..."
                    className="w-full bg-transparent border-b border-white/10 p-2 text-white outline-none focus:border-primary text-sm font-medium mb-2"
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="flex items-center gap-2 text-xs text-primary mb-1">
                      <LinkIcon size={12} /> URL Visitar
                    </label>
                    <input
                      type="url"
                      value={group.visitUrl || ''}
                      onChange={e => setEditedItem(prev => ({ ...prev, linkGroups: prev.linkGroups?.map(g => g.id === group.id ? { ...g, visitUrl: e.target.value } : g) }))}
                      placeholder="https://..."
                      className="w-full bg-surface border border-white/10 rounded p-2 text-white focus:border-primary outline-none text-xs"
                    />
                  </div>
                  <div>
                    <label className="flex items-center gap-2 text-xs text-primary mb-1">
                      <Download size={12} /> URL Descargar
                    </label>
                    <input
                      type="url"
                      value={group.downloadUrl || ''}
                      onChange={e => setEditedItem(prev => ({ ...prev, linkGroups: prev.linkGroups?.map(g => g.id === group.id ? { ...g, downloadUrl: e.target.value } : g) }))}
                      placeholder="https://..."
                      className="w-full bg-surface border border-white/10 rounded p-2 text-white focus:border-primary outline-none text-xs"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div className="border-t border-white/10 pt-6">
            <div className="flex items-center justify-between mb-4">
              <label className="block text-sm font-medium text-gray-400">Bloques de Contenido</label>
              <div className="flex gap-4">
                <button
                  onClick={() => handleAddBlockImmediately('markdown')}
                  className="flex items-center gap-2 text-primary hover:text-white transition-colors text-sm font-medium"
                >
                  <Plus size={16} /> Añadir Bloque
                </button>
                <button
                  onClick={() => handleAddBlockImmediately('raw-markdown')}
                  className="flex items-center gap-2 text-[#bb86fc] hover:text-white transition-colors text-sm font-medium"
                  title="Bloque de Markdown puro"
                >
                  <Plus size={16} /> Añadir Bloque MD
                </button>
              </div>
            </div>

            <div className="space-y-3">
              {editedItem.blocks && editedItem.blocks.map((block, index) => (
                <div key={block.id} className={`${getCardClasses(editedItem.cardStyle)} rounded-lg overflow-hidden transition-all duration-300`}>
                  <div className="flex items-center justify-between px-4 py-2 bg-white/5 border-b border-white/5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-gray-500">Bloque {index + 1}</span>
                      {block.type === 'markdown' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-primary/20 text-primary rounded border border-primary/30">Rich Text</span>
                      )}
                      {block.type === 'raw-markdown' && (
                        <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/20 text-purple-400 rounded border border-purple-500/30">Markdown</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDeleteBlock(block.id)}
                        className="text-gray-400 hover:text-red-400 transition-colors p-1"
                        title="Eliminar bloque"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="p-4">
                    {block.type === 'raw-markdown' ? (
                      <textarea
                        value={typeof block.content === 'string' ? block.content : ''}
                        onChange={(e) => handleBlockUpdate(block.id, e.target.value)}
                        className="w-full min-h-[150px] bg-background border border-white/10 rounded-lg p-3 text-gray-300 font-mono text-sm focus:border-primary focus:ring-1 focus:ring-primary outline-none transition-colors"
                        placeholder="Escribe tu código Markdown aquí..."
                      />
                    ) : (
                      <TipTapEditor
                        content={block.content}
                        onUpdate={(content) => handleBlockUpdate(block.id, content)}
                        isEditable={true}
                        editorRef={activeEditorRef}
                        autoFocus={false}
                        showToolbarOnFocus={true}
                        onBlockDoubleClick={(type, idx) => handleBlockDoubleClick(type, idx, block.id)}
                        dense={true}
                        className="min-h-[40px]"
                        cardStyle={editedItem.cardStyle || 'bordered'}
                        onCardStyleChange={(style) => setEditedItem(prev => ({ ...prev, cardStyle: style }))}
                      />
                    )}
                  </div>
                </div>
              ))}


            </div>
          </div>
        </div>

        <div style={{ display: !showEditTab ? 'block' : 'none' }}>
          <div className={`relative mb-8 p-6 rounded-xl ${getCardClasses(editedItem.cardStyle)}`}>
            <div className="absolute top-5 right-5 z-20 flex gap-2">
              <Button
                variant="outline"
                onClick={handleCancelEdit}
                className="!py-1.5 !px-3 text-xs h-8 bg-black/40 hover:bg-black/60 border-white/10"
              >
                <X size={14} /> <span className="hidden sm:inline">Cancelar</span>

              </Button>
              <Button
                variant="primary"
                onClick={handleSaveChanges}
                className="!py-1.5 !px-3 text-xs h-8"
              >
                <Save size={14} /> <span className="hidden sm:inline">Guardar</span>
              </Button>
            </div>

            <div className="mb-6">
              <label className="block text-xs font-medium text-gray-500 uppercase mb-2">Icono</label>
              <IconPicker
                selectedIcon={editedItem.icon || 'Layout'}
                onSelect={(icon) => setEditedItem(prev => ({ ...prev, icon }))}
              />
            </div>

            <div className="mb-6">
              <label className="block text-xs font-medium text-gray-500 uppercase mb-2">Título</label>
              <TipTapEditor
                content={editedItem.title}
                onUpdate={(content) => {
                  if (typeof content === 'string') {
                    setEditedItem(prev => ({ ...prev, title: content }));
                  }
                }}
                isEditable={true}
                dense={true}
                className="min-h-[40px] text-2xl font-bold"
                showToolbarOnFocus={true}
                cardStyle={editedItem.cardStyle || 'bordered'}
                onCardStyleChange={(style) => setEditedItem(prev => ({ ...prev, cardStyle: style }))}
              />
            </div>

            <div className="mb-6">
              <div className="flex justify-between items-center mb-2">
                <label className="block text-xs font-medium text-gray-500 uppercase">Resumen</label>
              </div>
              <TipTapEditor
                content={editedItem.summary}
                onUpdate={(content) => {
                  if (typeof content === 'string') {
                    setEditedItem(prev => ({ ...prev, summary: content }));
                  }
                }}
                isEditable={true}
                dense={true}
                className="min-h-[80px]"
                showToolbarOnFocus={true}
                cardStyle={editedItem.cardStyle || 'bordered'}
                onCardStyleChange={(style) => setEditedItem(prev => ({ ...prev, cardStyle: style }))}
              />
            </div>

            {(editedItem.categories && editedItem.categories.length > 0) && (
              <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-white/5">
                {editedItem.categories.map((cat, idx) => (
                  <span key={idx} className="text-sm text-primary bg-primary/10 px-3 py-1 rounded-lg border border-primary/30 uppercase tracking-wide font-medium">
                    {cat}
                  </span>
                ))}
              </div>
            )}

            {editedItem.tags.length > 0 && (
              <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-white/5">
                {editedItem.tags.map((tag, idx) => (
                  <span key={idx} className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded border border-white/5 uppercase tracking-wide">
                    {tag}
                  </span>
                ))}
              </div>
            )}

              <div className="flex flex-col gap-3 pt-6 mt-2 border-t border-white/5">
                {editedItem.visitUrl && getFishAudioId(editedItem.visitUrl) && (
                  <FishAudioPlayer modelId={getFishAudioId(editedItem.visitUrl)!} className="mb-2" />
                )}
                <div className="flex flex-col sm:flex-row gap-3">
                  {editedItem.visitUrl && (
                    <a href={editedItem.visitUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                      <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                        <ExternalLink size={16} /> Visitar Enlace
                      </button>
                    </a>
                  )}
                  {editedItem.downloadUrl && (
                    <a href={editedItem.downloadUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                      <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                        <Download size={16} /> Descargar
                      </button>
                    </a>
                  )}
                </div>
              </div>


            {editedItem.linkGroups && editedItem.linkGroups.length > 0 && (
              <div className="space-y-4 pt-6 mt-2 border-t border-white/5">
                {editedItem.linkGroups.map((group) => {
                  if (!group.visitUrl && !group.downloadUrl) return null;
                  const fishAudioId = getFishAudioId(group.visitUrl || '');
                  return (
                    <div key={group.id} className="w-full">
                      {group.title && (
                        <h4 className="text-sm font-medium text-gray-400 mb-2">{group.title}</h4>
                      )}
                      {fishAudioId && (
                        <FishAudioPlayer modelId={fishAudioId} className="mb-3" />
                      )}
                      <div className="flex flex-col sm:flex-row gap-3">
                        {group.visitUrl && (
                          <a href={group.visitUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                            <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                              <ExternalLink size={16} /> Visitar Enlace
                            </button>
                          </a>
                        )}
                        {group.downloadUrl && (
                           <a href={group.downloadUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                            <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                              <Download size={16} /> Descargar
                            </button>
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {editedItem.blocks && editedItem.blocks.length > 0 && (
            <div className="space-y-6 mb-8">
              {editedItem.blocks.map((block) => (
                <div key={block.id} className={`${getCardClasses(editedItem.cardStyle)} h-fit rounded-xl overflow-hidden p-6 transition-all duration-300`}>
                  {block.type === 'raw-markdown' ? (
                    <MarkdownRenderer content={typeof block.content === 'string' ? block.content : ''} />
                  ) : (
                    <TipTapEditor
                      content={block.content}
                      onUpdate={() => { }}
                      isEditable={false}
                      dense={true}
                      className="min-h-[40px]"
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <BlockEditorModal
          isOpen={blockEditor.isOpen}
          onClose={() => setBlockEditor(prev => ({ ...prev, isOpen: false }))}
          editor={activeEditorRef.current}
          type={blockEditor.type}
        />

        <ConfirmDialog
          isOpen={confirmDialog.isOpen}
          onClose={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
          onConfirm={confirmDialog.onConfirm}
          title={confirmDialog.title}
          message={confirmDialog.message}
        />

      </div >



    );
  }

  return (
    <div className="max-w-5xl mx-auto animate-fade-in pb-20">
      <button
        onClick={onBack}
        className="mb-6 flex items-center gap-2 text-gray-400 hover:text-primary transition-colors text-sm font-medium"
      >
        <ArrowLeft size={18} /> Volver al Inicio
      </button>

      <div className={`${getCardClasses(item.cardStyle)} h-fit rounded-xl p-6 relative mb-8 flex flex-col md:block`}>
        <div className="flex justify-end gap-2 mb-4 md:absolute md:top-5 md:right-5 md:mb-0 z-20">


          {isEditable && (
            <>
              <Button
                variant="outline"
                onClick={() => setIsEditMode(true)}
                className="!py-1.5 !px-3 text-xs h-8"
              >
                <Edit2 size={14} /> <span className="hidden sm:inline">Editar</span>
              </Button>
              <Button
                variant="danger"
                onClick={() => {
                  setConfirmDialog({
                    isOpen: true,
                    title: 'Eliminar Entrada',
                    message: '¿Estás seguro de que deseas eliminar esta entrada permanentemente? Esta acción no se puede deshacer.',
                    onConfirm: () => onDelete(item.id)
                  });
                }}
                className="!py-1.5 !px-3 h-8"
              >
                <Trash2 size={14} />
              </Button>
            </>
          )}
        </div>

        <h1
          className="text-2xl md:text-3xl font-bold text-white mb-4 md:pr-32 [&>p]:inline [&>p]:m-0"
          dangerouslySetInnerHTML={{ __html: item.title || 'Título' }}
        />

        <hr className="border-white/10 mb-4" />

        <div className="relative group/summary">

          
          <TipTapEditor
            content={item.summary || '<p>Resumen</p>'}
            onUpdate={() => { }}
            isEditable={false}
            className="text-gray-300 text-base leading-relaxed max-w-4xl mb-4 min-h-0"
            dense={true}
          />
        </div>

        {(item.categories && item.categories.length > 0) && (
          <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-white/5">
            {item.categories.map((cat, idx) => (
              <span key={idx} className="text-sm text-primary bg-primary/10 px-3 py-1 rounded-lg border border-primary/30 uppercase tracking-wide font-medium">
                {cat}
              </span>
            ))}
          </div>
        )}

        {item.tags.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-4 border-t border-white/5">
            {item.tags.map((tag, idx) => (
              <span key={idx} className="text-xs text-gray-500 bg-white/5 px-2 py-0.5 rounded border border-white/5 uppercase tracking-wide">
                {tag}
              </span>
            ))}
          </div>
        )}

        <div className="flex flex-col gap-3 pt-6 mt-2 border-t border-white/5">
          {item.visitUrl && getFishAudioId(item.visitUrl) && (
            <FishAudioPlayer modelId={getFishAudioId(item.visitUrl)!} className="mb-2" />
          )}
          <div className="flex flex-col sm:flex-row gap-3">
            {item.visitUrl && (
              <a href={item.visitUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                  <ExternalLink size={16} /> Visitar Enlace
                </button>
              </a>
            )}
            {item.downloadUrl && (
              <a href={item.downloadUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                  <Download size={16} /> Descargar
                </button>
              </a>
            )}
          </div>
        </div>



        {item.linkGroups && item.linkGroups.length > 0 && (
          <div className="space-y-4 pt-6 mt-2 border-t border-white/5">
            {item.linkGroups.map((group) => {
              if (!group.visitUrl && !group.downloadUrl) return null;
              const fishAudioId = getFishAudioId(group.visitUrl || '');
              return (
                <div key={group.id} className="w-full">
                  {group.title && (
                    <h4 className="text-sm font-medium text-gray-400 mb-2">{group.title}</h4>
                  )}
                  {fishAudioId && (
                    <FishAudioPlayer modelId={fishAudioId} className="mb-3" />
                  )}
                  <div className="flex flex-col sm:flex-row gap-3">
                    {group.visitUrl && (
                      <a href={group.visitUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                        <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                          <ExternalLink size={16} /> Visitar Enlace
                        </button>
                      </a>
                    )}
                    {group.downloadUrl && (
                       <a href={group.downloadUrl} target="_blank" rel="noopener noreferrer" className="flex-1 flex w-full">
                        <button className="w-full flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl border border-primary/30 text-primary hover:bg-primary/10 transition-colors text-sm font-medium">
                          <Download size={16} /> Descargar
                        </button>
                      </a>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {item.blocks && item.blocks.length > 0 && (
        <div className="space-y-6 mb-8">
          {item.blocks.map((block, blockIdx) => (
            <div key={block.id} className={`${getCardClasses(item.cardStyle)} h-fit rounded-xl overflow-hidden p-6 transition-all duration-300 relative group/block`}>
              {block.type === 'raw-markdown' ? (
                <MarkdownRenderer content={typeof block.content === 'string' ? block.content : ''} />
              ) : (
                <TipTapEditor
                  content={block.content}
                  onUpdate={() => { }}
                  isEditable={false}
                  dense={true}
                  className="min-h-[40px]"
                />
              )}
            </div>
          ))}
        </div>
      )}


      <ConfirmDialog
        isOpen={confirmDialog.isOpen}
        onClose={() => setConfirmDialog(prev => ({ ...prev, isOpen: false }))}
        onConfirm={confirmDialog.onConfirm}
        title={confirmDialog.title}
        message={confirmDialog.message}
      />
    </div>
  );
};