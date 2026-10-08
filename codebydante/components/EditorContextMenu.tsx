import React from 'react';
import { Editor } from '@tiptap/react';
import {
    Bold,
    Italic,
    Code,
    List,
    ListOrdered,
    Quote,
    Heading1,
    Heading2,
    Link as LinkIcon,
    Terminal,
    FileCode,
    Eraser,
    AlignLeft,
    AlignCenter,
    AlignRight,
    AlignJustify,
    Settings
} from 'lucide-react';

interface EditorContextMenuProps {
    editor: Editor | null;
    x: number;
    y: number;
    onClose: () => void;
    onOpenSettings: () => void;
}

export const EditorContextMenu: React.FC<EditorContextMenuProps> = ({ editor, x, y, onClose, onOpenSettings }) => {
    if (!editor) return null;

    const handleAction = (e: React.MouseEvent, action: () => void) => {
        e.preventDefault();
        e.stopPropagation();
        action();
        onClose();
    };

    const isAlignActive = (align: string) => editor.isActive({ textAlign: align });

    const MenuItem = ({
        icon: Icon,
        label,
        onClick,
        isActive = false,
        kdb = ''
    }: {
        icon: any,
        label: string,
        onClick: (e: React.MouseEvent) => void,
        isActive?: boolean,
        kdb?: string
    }) => (
        <button
            onMouseDown={onClick}
            className={`w-full flex items-center justify-between px-3 py-2 text-sm transition-colors ${isActive
                ? 'bg-primary/20 text-primary'
                : 'text-gray-300 hover:bg-white/10 hover:text-white'
                }`}
        >
            <div className="flex items-center gap-2">
                <Icon size={16} />
                <span>{label}</span>
            </div>
            {kdb && <span className="text-xs text-gray-500 font-mono ml-4">{kdb}</span>}
        </button>
    );

    const Divider = () => <div className="h-px bg-white/10 my-1 mx-2" />;

    return (
        <div
            className="fixed z-[100] w-64 bg-[#1e1e1e] border border-white/10 rounded-lg shadow-2xl overflow-hidden py-1"
            style={{
                top: Math.min(y, window.innerHeight - 400),
                left: Math.min(x, window.innerWidth - 260)
            }}
            onMouseDown={(e) => e.stopPropagation()}
            onContextMenu={(e) => e.preventDefault()}
        >
            <MenuItem
                icon={Heading1}
                label="Título 1"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleHeading({ level: 1 }).run())}
                isActive={editor.isActive('heading', { level: 1 })}
            />
            <MenuItem
                icon={Heading2}
                label="Título 2"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleHeading({ level: 2 }).run())}
                isActive={editor.isActive('heading', { level: 2 })}
            />

            <Divider />

            <MenuItem
                icon={Bold}
                label="Negrita"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleBold().run())}
                isActive={editor.isActive('bold')}
                kdb="Ctrl+B"
            />
            <MenuItem
                icon={Italic}
                label="Cursiva"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleItalic().run())}
                isActive={editor.isActive('italic')}
                kdb="Ctrl+I"
            />

            <Divider />

            <MenuItem
                icon={LinkIcon}
                label="Enlace"
                onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const previousUrl = editor.getAttributes('link').href;
                    const url = window.prompt('URL del enlace:', previousUrl);
                    if (url === null) return;
                    if (url === '') {
                        editor.chain().focus().extendMarkRange('link').unsetLink().run();
                        return;
                    }
                    editor.chain().focus().extendMarkRange('link').setLink({ href: url }).run();
                    onClose();
                }}
                isActive={editor.isActive('link')}
            />

            <MenuItem
                icon={Code}
                label="Código Inline"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleCode().run())}
                isActive={editor.isActive('code') && editor.getAttributes('code').showBackground !== false}
            />

            <MenuItem
                icon={Terminal}
                label="Estilo Tarjeta"
                onClick={(e) => handleAction(e, () => {
                    const isCodeActive = editor.isActive('code');
                    if (isCodeActive) {
                        editor.chain().focus().unsetCode().run();
                    } else {
                        editor.chain().focus().setCode().updateAttributes('code', { showBackground: false }).run();
                    }
                })}
                isActive={editor.isActive('code') && editor.getAttributes('code').showBackground === false}
            />

            <MenuItem
                icon={FileCode}
                label="Bloque de Código"
                onClick={(e) => handleAction(e, () => editor.chain().focus().setCodeBlock({ language: 'text' }).run())}
                isActive={editor.isActive('codeBlock')}
            />

            <Divider />

            <MenuItem
                icon={Quote}
                label="Cita"
                onClick={(e) => handleAction(e, () => {
                    if (editor.isActive('customBlockquote')) {
                        editor.chain().focus().unsetBlockquote().run();
                    } else {
                        editor.chain().focus().setBlockquote().run();
                    }
                })}
                isActive={editor.isActive('customBlockquote')}
            />

            <MenuItem
                icon={List}
                label="Lista con viñetas"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleBulletList().run())}
                isActive={editor.isActive('bulletList')}
            />
            <MenuItem
                icon={ListOrdered}
                label="Lista numerada"
                onClick={(e) => handleAction(e, () => editor.chain().focus().toggleOrderedList().run())}
                isActive={editor.isActive('orderedList')}
            />

            <Divider />

            <div className="flex justify-between px-2 py-1">
                <button
                    onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setTextAlign('left').run())}
                    className={`p-1 rounded hover:bg-white/10 ${isAlignActive('left') ? 'text-primary' : 'text-gray-400'}`}
                >
                    <AlignLeft size={16} />
                </button>
                <button
                    onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setTextAlign('center').run())}
                    className={`p-1 rounded hover:bg-white/10 ${isAlignActive('center') ? 'text-primary' : 'text-gray-400'}`}
                >
                    <AlignCenter size={16} />
                </button>
                <button
                    onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setTextAlign('right').run())}
                    className={`p-1 rounded hover:bg-white/10 ${isAlignActive('right') ? 'text-primary' : 'text-gray-400'}`}
                >
                    <AlignRight size={16} />
                </button>
                <button
                    onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setTextAlign('justify').run())}
                    className={`p-1 rounded hover:bg-white/10 ${isAlignActive('justify') ? 'text-primary' : 'text-gray-400'}`}
                >
                    <AlignJustify size={16} />
                </button>
            </div>

            <Divider />

            <MenuItem
                icon={Eraser}
                label="Limpiar Formato"
                onClick={(e) => handleAction(e, () => editor.chain().focus().unsetAllMarks().clearNodes().run())}
            />

            <MenuItem
                icon={Settings}
                label="Configuración"
                onClick={(e) => handleAction(e, onOpenSettings)}
            />

        </div>
    );
};
