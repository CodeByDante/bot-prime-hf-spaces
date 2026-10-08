import React, { useState, useEffect, useRef } from 'react';
import { X, Sparkles, Wand2, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

interface AIInstructionModalProps {
    isOpen: boolean;
    onClose: () => void;
    onGenerate: (instructions: string) => Promise<void>;
    currentContent?: string;
}

export const AIInstructionModal: React.FC<AIInstructionModalProps> = ({
    isOpen,
    onClose,
    onGenerate,
    currentContent
}) => {
    const [instructions, setInstructions] = useState('');
    const [isGenerating, setIsGenerating] = useState(false);
    const textareaRef = useRef<HTMLTextAreaElement>(null);

    useEffect(() => {
        if (isOpen) {
            setInstructions('');
            setIsGenerating(false);
            // Focus after animation
            setTimeout(() => textareaRef.current?.focus(), 100);
        }
    }, [isOpen]);

    const handleSubmit = async (e?: React.FormEvent) => {
        e?.preventDefault();
        if (!instructions.trim() || isGenerating) return;

        setIsGenerating(true);
        try {
            await onGenerate(instructions);
            onClose();
        } catch (error) {
            console.error("Analysis failed", error);
        } finally {
            setIsGenerating(false);
        }
    };

    const isContentEmpty = !currentContent || currentContent.trim().length === 0;
    const title = isContentEmpty ? "¿Qué deseas crear?" : "¿Cómo deseas mejorarlo?";
    const placeholder = isContentEmpty
        ? "Ej: Escribe un resumen sobre React Hooks..."
        : "Ej: Hazlo más conciso, añade emojis, tradúcelo al inglés...";

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    {/* Backdrop */}
                    <motion.div
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
                    />

                    {/* Modal */}
                    <motion.div
                        initial={{ opacity: 0, scale: 0.95, y: 20 }}
                        animate={{ opacity: 1, scale: 1, y: 0 }}
                        exit={{ opacity: 0, scale: 0.95, y: 20 }}
                        className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
                    >
                        <div className="w-full max-w-lg bg-[#1a1a1a] border border-white/10 rounded-2xl shadow-2xl overflow-hidden pointer-events-auto flex flex-col">

                            {/* Header */}
                            <div className="relative h-32 bg-gradient-to-br from-indigo-600/20 via-purple-600/20 to-pink-600/20 flex flex-col items-center justify-center border-b border-white/5">
                                <button
                                    onClick={onClose}
                                    className="absolute top-4 right-4 text-white/50 hover:text-white transition-colors"
                                >
                                    <X size={20} />
                                </button>

                                <div className="w-12 h-12 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-purple-500/30 mb-3">
                                    <Sparkles className="text-white" size={24} />
                                </div>
                                <h3 className="text-xl font-bold text-white tracking-tight">{title}</h3>
                                <p className="text-white/50 text-xs mt-1">Dante AI Assistant</p>
                            </div>

                            {/* Body */}
                            <div className="p-6 space-y-4">
                                <div className="relative">
                                    <textarea
                                        ref={textareaRef}
                                        value={instructions}
                                        onChange={(e) => setInstructions(e.target.value)}
                                        onKeyDown={(e) => {
                                            if (e.key === 'Enter' && !e.shiftKey) {
                                                e.preventDefault();
                                                handleSubmit();
                                            }
                                        }}
                                        placeholder={placeholder}
                                        className="w-full h-32 bg-black/20 border border-white/10 rounded-xl p-4 text-white placeholder:text-white/20 resize-none focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/50 transition-all text-base"
                                    />
                                    <div className="absolute bottom-3 right-3 text-xs text-white/30">
                                        Enter para enviar
                                    </div>
                                </div>

                                <button
                                    onClick={() => handleSubmit()}
                                    disabled={!instructions.trim() || isGenerating}
                                    className="w-full py-3 bg-white text-black font-semibold rounded-xl hover:bg-white/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all flex items-center justify-center gap-2 shadow-lg shadow-white/10"
                                >
                                    {isGenerating ? (
                                        <>
                                            <Loader2 size={18} className="animate-spin" />
                                            <span>Procesando...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Wand2 size={18} />
                                            <span>{isContentEmpty ? 'Generar Contenido' : 'Aplicar Mejoras'}</span>
                                        </>
                                    )}
                                </button>
                            </div>
                        </div>
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    );
};
