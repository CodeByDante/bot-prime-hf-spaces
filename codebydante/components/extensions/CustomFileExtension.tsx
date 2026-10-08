import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer, NodeViewWrapper } from '@tiptap/react';
import React from 'react';
import { FileText, Send } from 'lucide-react';

// Extensión para renderizar archivos subidos de forma elegante
export const CustomFileExtension = Node.create({
    name: 'customFile',
    group: 'block',
    atom: true,

    addAttributes() {
        return {
            name: { default: 'Archivo' },
            messageId: { default: null },
            channelId: { default: null },
            size: { default: null },
        };
    },

    parseHTML() {
        return [{ tag: 'div[data-type="custom-file"]' }];
    },

    renderHTML({ HTMLAttributes }) {
        return ['div', mergeAttributes(HTMLAttributes, { 'data-type': 'custom-file' })];
    },

    addNodeView() {
        return ReactNodeViewRenderer(FileComponent);
    },
});

const FileComponent = ({ node }: any) => {
    const { name = "Archivo sin nombre", messageId = "0" } = node.attrs || {};
    
    const botUsername = "CodeByDantePrimebot"; 
    const telegramUrl = `https://t.me/${botUsername}?start=${messageId}`;

    return (
        <NodeViewWrapper className="custom-file-node">
            <div 
                contentEditable={false}
                className="my-3 p-3 bg-zinc-900/90 border border-white/10 rounded-xl flex items-center justify-between gap-4 group hover:border-primary/50 transition-all shadow-lg select-none"
            >
                <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center text-primary shrink-0">
                        <FileText size={20} />
                    </div>
                    <div className="flex-1 min-w-0">
                        <div className="text-sm font-bold text-white truncate">
                            {name}
                        </div>
                        <div className="text-[10px] text-zinc-500 flex items-center gap-2">
                            <span>ID: {messageId}</span>
                        </div>
                    </div>
                </div>
                
                <a 
                    href={telegramUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-primary hover:bg-primary-hover text-white rounded-lg flex items-center gap-2 text-xs font-bold transition-all shrink-0 no-underline whitespace-nowrap"
                >
                    <Send size={14} />
                    <span>Telegram</span>
                </a>
            </div>
        </NodeViewWrapper>
    );
};
