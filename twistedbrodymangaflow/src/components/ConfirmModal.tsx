import { AlertTriangle, X } from 'lucide-react';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
}

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  variant = 'warning',
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const colorClasses = {
    danger: 'from-red-500 to-red-600 shadow-red-500/20',
    warning: 'from-[#bb86fc] to-[#9966dd] shadow-[#bb86fc]/30',
    info: 'from-blue-500 to-blue-600 shadow-blue-500/20',
  };

  const iconClasses = {
    danger: 'bg-red-500/10 text-red-500',
    warning: 'bg-[#bb86fc]/10 text-[#bb86fc]',
    info: 'bg-blue-500/10 text-blue-500',
  };

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-[100] p-4 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-gradient-to-b from-[#1f1f1f] to-[#121212] rounded-2xl border border-gray-700/40 w-full max-w-md shadow-2xl overflow-hidden scale-in-center">
        <div className="bg-gradient-to-b from-[#2a2a2a] to-[#1f1f1f] border-b border-gray-700/30 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${iconClasses[variant]}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <h2 className="text-xl font-bold text-white tracking-tight">{title}</h2>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-white hover:bg-white/10 transition-all p-1.5 rounded-lg"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-8">
          <p className="text-gray-300 leading-relaxed">
            {message}
          </p>

          <div className="flex gap-3 mt-8">
            <button
              onClick={onClose}
              className="flex-1 bg-[#1a1a1a] border border-gray-600/40 hover:border-gray-500 hover:bg-[#242424] text-white px-5 py-3 rounded-xl font-semibold text-sm transition-all shadow-md active:scale-95"
            >
              {cancelText}
            </button>
            <button
              onClick={() => {
                onConfirm();
                onClose();
              }}
              className={`flex-1 bg-gradient-to-r ${colorClasses[variant]} text-white px-5 py-3 rounded-xl font-bold text-sm transition-all shadow-lg hover:brightness-110 active:scale-95`}
            >
              {confirmText}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
