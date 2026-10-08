import React, { useState } from 'react';
import { X, Sparkles, Check, Hash } from 'lucide-react';
import { Button } from './Button';

interface BulkCategoryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onApply: (categories: string[]) => void;
  selectionCount: number;
}

export const BulkCategoryModal: React.FC<BulkCategoryModalProps> = ({ isOpen, onClose, onApply, selectionCount }) => {
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryInput, setCategoryInput] = useState('');

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm px-4">
      <div className="bg-[#1e1e1e] rounded-xl shadow-2xl w-full max-w-lg border border-white/10 animate-fade-in overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Hash size={18} className="text-primary" /> Aplicar Categorías en Masa
          </h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-6">
          <p className="text-sm text-gray-400 mb-6">
            Añade las categorías que deseas aplicar a las {selectionCount} entradas seleccionadas. Las categorías existentes se conservarán.
          </p>

          <div className="mb-4">
            <div className="flex flex-wrap gap-2 mb-2">
              {categories.map((cat, idx) => (
                <span key={idx} className="flex items-center gap-1 text-sm text-primary bg-primary/10 px-3 py-1 rounded-lg border border-primary/30 uppercase tracking-wide font-medium">
                  {cat}
                  <button 
                    type="button" 
                    onClick={() => setCategories(categories.filter((_, i) => i !== idx))} 
                    className="ml-1 hover:text-red-400 focus:outline-none"
                  >
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
            <div className="relative">
              <Sparkles size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-primary" />
              <input
                type="text"
                autoFocus
                className="w-full bg-background border border-white/10 rounded-lg p-3 pl-10 text-white focus:border-primary outline-none focus:ring-1 focus:ring-primary transition-colors"
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

          <div className="flex justify-end gap-3 mt-8">
            <Button variant="outline" onClick={onClose} className="px-6 border-white/10">
              Cancelar
            </Button>
            <Button 
              onClick={() => {
                onApply(categories);
                setCategories([]);
                setCategoryInput('');
              }} 
              disabled={categories.length === 0}
            >
              <Check size={18} /> Aplicar a {selectionCount} items
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};
