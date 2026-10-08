import React, { useState, useEffect } from 'react';
import { X, Check } from 'lucide-react';
import { StyleSettingsPanel } from './StyleSettingsPanel';
import { Editor } from '@tiptap/react';
import {
    DEFAULT_STYLE_CONFIG,
    type StyleConfig
} from '../services/codeStyleService';

interface BlockEditorModalProps {
    isOpen: boolean;
    onClose: () => void;
    editor: Editor | null;
    type: 'quote' | 'code';
}

export const BlockEditorModal: React.FC<BlockEditorModalProps> = ({
    isOpen,
    onClose,
    editor,
    type
}) => {
    const [localConfig, setLocalConfig] = useState<StyleConfig>(DEFAULT_STYLE_CONFIG);
    const [activeTab, setActiveTab] = useState<'code' | 'quote' | 'general'>(type === 'quote' ? 'quote' : 'code');

    useEffect(() => {
        if (isOpen && editor) {
            // Load current attributes from selection
            const { from, to } = editor.state.selection;
            let node;

            editor.state.doc.nodesBetween(from, to, (n) => {
                if (n.type.name === 'customBlockquote' && type === 'quote') {
                    node = n;
                    return false;
                }
                // Add code block support if needed
                return true;
            });

            if (node && type === 'quote') {
                const attrs = (node as any).attrs;
                setLocalConfig(prev => ({
                    ...prev,
                    quote: {
                        ...prev.quote,
                        borderColor: attrs.borderColor || prev.quote.borderColor,
                        borderWidth: attrs.borderWidth || prev.quote.borderWidth,
                        bgColor: attrs.backgroundColor || prev.quote.bgColor,
                        textColor: attrs.textColor || prev.quote.textColor,
                        padding: attrs.padding || prev.quote.padding,
                        fontSize: attrs.fontSize || prev.quote.fontSize,
                        borderRadius: attrs.borderRadius || prev.quote.borderRadius,
                        width: attrs.width || prev.quote.width,
                        height: attrs.height || prev.quote.height,
                        italic: attrs.italic || prev.quote.italic,
                        showCopyButton: attrs.showCopyButton || prev.quote.showCopyButton
                    }
                }));
            }
        }
    }, [isOpen, editor, type]);

    const handleUpdateConfig = (newConfig: StyleConfig) => {
        setLocalConfig(newConfig);
        if (editor) {
            if (type === 'quote') {
                editor.chain().focus().updateAttributes('customBlockquote', {
                    borderColor: newConfig.quote.borderColor,
                    borderWidth: newConfig.quote.borderWidth,
                    backgroundColor: newConfig.quote.bgColor,
                    textColor: newConfig.quote.textColor,
                    padding: newConfig.quote.padding,
                    fontSize: newConfig.quote.fontSize,
                    borderRadius: newConfig.quote.borderRadius,
                    width: newConfig.quote.width,
                    height: newConfig.quote.height,
                    italic: newConfig.quote.italic,
                    showCopyButton: newConfig.quote.showCopyButton
                }).run();
            }
            // Implement code block update if needed
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in">
            <div className="bg-[#1a1a1a] border border-white/10 rounded-xl shadow-2xl w-[450px] max-h-[85vh] flex flex-col overflow-hidden">
                <div className="p-4 border-b border-white/5 bg-white/5 flex items-center justify-between">
                    <h3 className="text-white font-bold flex items-center gap-2">
                        Editar Estilo de {type === 'quote' ? 'Cita' : 'Código'}
                    </h3>
                    <button
                        onClick={onClose}
                        className="text-gray-500 hover:text-white transition-colors"
                    >
                        <X size={20} />
                    </button>
                </div>

                <div className="flex-1 overflow-hidden flex flex-col">
                    <StyleSettingsPanel
                        styleConfig={localConfig}
                        onUpdateConfig={handleUpdateConfig}
                        activeTab={activeTab}
                        onTabChange={(tab) => {
                            if (tab === 'general' || tab === type) {
                                setActiveTab(tab);
                            }
                        }}
                        onConfirm={onClose}
                        onClose={onClose}
                        hideTabs={true}
                        // Preview content is now handled by the editor itself in the background
                        // But StyleSettingsPanel expects a previewContent string. 
                        // We can pass a dummy string or try to extract text from editor node.
                        previewContent="Vista previa en el editor"
                    />
                </div>
            </div>
        </div>
    );
};
