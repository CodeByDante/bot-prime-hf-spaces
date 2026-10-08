import React, { useState } from 'react';
import { DataItem, LinkGroup } from '../types';
import { Button } from './Button';
import { IconPicker } from './IconPicker';
import { TipTapEditor } from './TipTapEditor';
import { Save, X, Link as LinkIcon, Download, Hash, Sparkles } from 'lucide-react';

interface DataFormProps {
  initialData?: DataItem | null;
  onSave: (data: Omit<DataItem, 'id' | 'createdAt'>) => void | Promise<void>;
  onCancel: () => void;
}

export const DataForm: React.FC<DataFormProps> = ({ initialData, onSave, onCancel }) => {
  const [title, setTitle] = useState(initialData?.title || '');
  const [icon, setIcon] = useState(initialData?.icon || 'layers');
  const [summary, setSummary] = useState(initialData?.summary || '');
  const [downloadUrl, setDownloadUrl] = useState(initialData?.downloadUrl || '');
  const [visitUrl, setVisitUrl] = useState(initialData?.visitUrl || '');
  const [tagsString, setTagsString] = useState(initialData?.tags.join(', ') || '');
  const [categories, setCategories] = useState<string[]>(initialData?.categories || []);
  const [categoryInput, setCategoryInput] = useState('');
  const [linkGroups, setLinkGroups] = useState<LinkGroup[]>(initialData?.linkGroups || []);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    
    setIsSubmitting(true);

    try {
      await onSave({
        icon: icon || 'layers',
        title,
        content: "", // Legacy
        summary,
        downloadUrl: downloadUrl || undefined,
        visitUrl: visitUrl || undefined,
        linkGroups,
        tags: tagsString.split(',').map(t => t.trim()).filter(Boolean),
        categories: categories,
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto animate-fade-in pb-20">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-bold text-white">
          {initialData ? 'Editar Entrada' : 'Crear Nueva Entrada'}
        </h2>
        <Button variant="ghost" onClick={onCancel} className="text-gray-500 hover:text-white">
          <X size={24} />
        </Button>
      </div>

      <form onSubmit={handleSubmit} className="space-y-8">

        {/* MAIN INFO CARD */}
        <div className="bg-surface p-8 rounded-2xl border border-white/5 shadow-xl space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-400 mb-2">Título</label>
            <div className="flex gap-4 items-start">
              <IconPicker
                selectedIcon={icon}
                onSelect={setIcon}
              />
              <div className="w-full bg-background border border-white/10 rounded-lg overflow-hidden focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
                <TipTapEditor
                  content={title}
                  onUpdate={(content) => {
                    if (typeof content === 'string') {
                      setTitle(content);
                    }
                  }}
                  isEditable={true}
                  showToolbarOnFocus={true}
                  className="px-4 py-2 min-h-[50px] text-lg"
                  dense={true}
                  minimalMode={true}
                />
              </div>
            </div>
          </div>

          <div>
            <div className="flex justify-between items-center mb-2">
              <label className="block text-sm font-medium text-gray-400">Resumen / Descripción Principal</label>
            </div>
            <div className="bg-background border border-white/10 rounded-lg overflow-hidden focus-within:border-primary focus-within:ring-1 focus-within:ring-primary transition-colors">
              <TipTapEditor
                content={summary}
                onUpdate={(content) => {
                  if (typeof content === 'string') {
                    setSummary(content);
                  }
                }}
                isEditable={true}
                showToolbarOnFocus={true}
                className="px-3 py-2 min-h-[100px]"
                dense={false}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 p-6 bg-background/30 rounded-xl border border-white/5">
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-primary mb-2">
                <LinkIcon size={16} /> Enlace de Visita
              </label>
              <input
                type="url"
                className="w-full bg-surface border border-white/10 rounded-lg p-3 text-white focus:border-primary outline-none text-sm placeholder-gray-600"
                value={visitUrl}
                onChange={(e) => setVisitUrl(e.target.value)}
                placeholder="https://mi-sitio-web.com"
              />
            </div>
            <div>
              <label className="flex items-center gap-2 text-sm font-medium text-primary mb-2">
                <Download size={16} /> Enlace de Descarga
              </label>
              <input
                type="url"
                className="w-full bg-surface border border-white/10 rounded-lg p-3 text-white focus:border-primary outline-none text-sm placeholder-gray-600"
                value={downloadUrl}
                onChange={(e) => setDownloadUrl(e.target.value)}
                placeholder="https://drive.google.com/..."
              />
            </div>
          </div>

          {/* LINK GROUPS */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <label className="block text-sm font-medium text-gray-400">Grupos de Enlaces Extra</label>
              <button
                type="button"
                onClick={() => setLinkGroups([...linkGroups, { id: Date.now().toString(), title: `Opción ${linkGroups.length + 1}` }])}
                className="text-xs text-primary hover:text-primary/80 flex items-center gap-1"
              >
                + Añadir Enlace Extra
              </button>
            </div>
            
            {linkGroups.map((group) => (
              <div key={group.id} className="p-4 bg-background/50 rounded-xl border border-white/5 space-y-4 relative group">
                <button
                  type="button"
                  onClick={() => setLinkGroups(linkGroups.filter(g => g.id !== group.id))}
                  className="absolute top-2 right-2 p-1 text-gray-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                  title="Eliminar grupo"
                >
                  <X size={16} />
                </button>
                <div>
                  <input
                    type="text"
                    value={group.title}
                    onChange={e => setLinkGroups(linkGroups.map(g => g.id === group.id ? { ...g, title: e.target.value } : g))}
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
                      onChange={e => setLinkGroups(linkGroups.map(g => g.id === group.id ? { ...g, visitUrl: e.target.value } : g))}
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
                      onChange={e => setLinkGroups(linkGroups.map(g => g.id === group.id ? { ...g, downloadUrl: e.target.value } : g))}
                      placeholder="https://..."
                      className="w-full bg-surface border border-white/10 rounded p-2 text-white focus:border-primary outline-none text-xs"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <div>
            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Categorías</label>
            </div>
            <div className="mb-6">
              <div className="flex flex-wrap gap-2 mb-2">
                {categories.map((cat, idx) => (
                  <span key={idx} className="flex items-center gap-1 text-sm text-primary bg-primary/10 px-3 py-1 rounded-lg border border-primary/30 uppercase tracking-wide font-medium">
                    {cat}
                    <button type="button" onClick={() => setCategories(categories.filter((_, i) => i !== idx))} className="ml-1 hover:text-red-400">
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
              <div className="relative">
                <Sparkles size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
                <input
                  type="text"
                  className="w-full bg-background border border-white/10 rounded-lg p-3 pl-10 text-white focus:border-primary outline-none"
                  value={categoryInput}
                  onChange={(e) => setCategoryInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      const val = categoryInput.trim();
                      if (val && !categories.includes(val)) {
                        setCategories([...categories, val]);
                        setCategoryInput('');
                      }
                    }
                  }}
                  placeholder="Escribe una categoría y presiona Enter..."
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-400 mb-2">Etiquetas</label>
            </div>
            <div className="relative">
              <Hash size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="text"
                className="w-full bg-background border border-white/10 rounded-lg p-3 pl-10 text-white focus:border-primary outline-none"
                value={tagsString}
                onChange={(e) => setTagsString(e.target.value)}
                placeholder="etiqueta1, etiqueta2..."
              />
            </div>
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

                  const text = `${title} ${summary}`.toLowerCase();
                  // RegEx to remove special chars, keep accents/letters/numbers
                  const words = text.replace(/[^\w\sáéíóúñü]/g, '').split(/\s+/);

                  const uniqueKeywords = new Set<string>();

                  words.forEach(word => {
                    if (word.length > 2 && !stopWords.has(word)) {
                      uniqueKeywords.add(word);
                    }
                  });

                  // Limit to 15 tags
                  const keywordsArray = Array.from(uniqueKeywords).slice(0, 15);
                  setTagsString(keywordsArray.join(', '));
                }}
                className="text-xs text-primary hover:text-primary/80 transition-colors flex items-center gap-1 bg-primary/10 px-3 py-1.5 rounded-lg border border-primary/20"
                title="Extraer palabras clave automáticamente"
                disabled={!title && !summary}
              >
                <Sparkles size={14} /> Generar Automáticamente
              </button>
            </div>
          </div>
        </div>

        {/* ACTION BUTTONS */}
        <div className="flex gap-4 pt-6 border-t border-white/5 sticky bottom-0 bg-[#121212] py-6 z-10">
          <Button type="button" variant="ghost" onClick={onCancel} className="flex-1">
            Cancelar
          </Button>
          <Button type="submit" className="flex-1 py-3 text-lg shadow-[0_0_20px_rgba(187,134,252,0.2)]" disabled={isSubmitting}>
            <Save size={20} /> {isSubmitting ? 'Guardando...' : 'Guardar Cambios'}
          </Button>
        </div>
      </form>
    </div>
  );
};