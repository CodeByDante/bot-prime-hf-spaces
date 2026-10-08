import React from 'react';
import { Button } from './Button';
import { AlertCircle, Trash2 } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  isDestructive?: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Aceptar',
  cancelText = 'Cancelar',
  isDestructive = false
}) => {
  if (!isOpen) return null;

  return (
    <>
      <div 
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 animate-in fade-in duration-200"
        onClick={onClose}
      />
      
      <div className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-sm bg-[#1a1a1a] shadow-[0_0_50px_rgba(0,0,0,0.5)] z-50 rounded-2xl overflow-hidden border border-white/10 animate-in zoom-in-95 duration-200">
        <div className="p-6">
          <div className="flex items-center gap-3 mb-4">
            {isDestructive ? (
              <div className="p-2.5 bg-red-500/10 rounded-xl text-red-500">
                <Trash2 size={24} />
              </div>
            ) : (
              <div className="p-2.5 bg-primary/10 rounded-xl text-primary">
                <AlertCircle size={24} />
              </div>
            )}
            <h2 className="text-xl font-bold text-white tracking-tight">{title}</h2>
          </div>
          
          <p className="text-gray-400 mb-8 leading-relaxed">
            {message}
          </p>
          
          <div className="flex justify-end gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white hover:bg-white/5 rounded-xl transition-colors"
            >
              {cancelText}
            </button>
            <Button
              onClick={() => {
                onConfirm();
                onClose();
              }}
              className={`!py-2 !px-5 ${isDestructive ? 'bg-red-500 hover:bg-red-600 text-white shadow-lg shadow-red-500/20' : ''}`}
            >
              {confirmText}
            </Button>
          </div>
        </div>
      </div>
    </>
  );
};
