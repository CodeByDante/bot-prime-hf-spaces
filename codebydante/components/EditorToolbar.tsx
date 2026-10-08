import React, { useEffect, useState } from 'react';
import { Editor } from '@tiptap/react';
import {
    Bold,
    Italic,
    Code,
    Link as LinkIcon,
    Heading1,
    Heading2,
    List,
    ListOrdered,
    Quote,
    Pilcrow,
    Settings,
    Check,
    X,
    Eraser,
    Image as ImageIcon,
    AlignLeft,
    AlignCenter,
    AlignRight,
    AlignJustify,
    Video,
    Terminal,
    FileCode,
    MousePointerClick,
    ExternalLink,
    Download,
    Github,
    Send,
    Twitter,
    Linkedin,
    Instagram,
    Youtube,
    Facebook,
    Layers,
    MessageCircle, // Using MessageCircle as generic community/chat since Discord might be missing
    Globe,
    Mail,
    FileText,
    Minus,
    Paperclip
} from 'lucide-react';
import { TiktokIcon } from './TiktokIcon';

import { QuoteStyleConfig, LinkStyleConfig, CodeStyleConfig } from '../services/codeStyleService';
import { uploadImageToImgBB } from '../services/imageService';

interface EditorToolbarProps {
    editor: Editor | null;
    onOpenSettings?: () => void;
    onSave?: () => void;
    defaultQuoteStyles?: QuoteStyleConfig;
    linkStyleConfig?: LinkStyleConfig;
    codeStyleConfig?: CodeStyleConfig;
    buttonStyleConfig?: any;
    minimalMode?: boolean;
}

export const EditorToolbar: React.FC<EditorToolbarProps> = ({
    editor,
    onOpenSettings,
    onSave,
    defaultQuoteStyles,
    linkStyleConfig,
    codeStyleConfig,
    buttonStyleConfig,
    minimalMode = false
}) => {
    const [hasSelection, setHasSelection] = useState(false);
    const [showLinkInput, setShowLinkInput] = useState(false);
    const [linkUrl, setLinkUrl] = useState('');
    const fileInputRef = React.useRef<HTMLInputElement>(null);
    const [isImageUploading, setIsImageUploading] = useState(false);
    const [isFileUploading, setIsFileUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [showVideoInput, setShowVideoInput] = useState(false);
    const [videoUrl, setVideoUrl] = useState('');
    const [showButtonInput, setShowButtonInput] = useState(false);
    const [buttonText, setButtonText] = useState('');
    const [buttonUrl, setButtonUrl] = useState('');
    const [buttonVariant, setButtonVariant] = useState<'visit' | 'download' | 'github' | 'telegram' | 'twitter' | 'linkedin' | 'instagram' | 'youtube' | 'facebook' | 'tiktok' | 'x' | 'code' | 'layers' | 'community' | 'globe' | 'mail' | 'file'>('visit');

    useEffect(() => {
        if (!editor) return;

        const updateSelection = () => {
            setHasSelection(!editor.state.selection.empty);
        };

        // Initial check
        updateSelection();

        editor.on('selectionUpdate', updateSelection);
        editor.on('update', updateSelection);

        return () => {
            editor.off('selectionUpdate', updateSelection);
            editor.off('update', updateSelection);
        };
    }, [editor]);

    if (!editor) return null;

    const handleAction = (e: React.MouseEvent, action: () => void) => {
        e.preventDefault();
        action();
    };

    const handleLink = (e: React.MouseEvent) => {
        e.preventDefault();

        if (editor.state.selection.empty && !editor.isActive('image')) {
            return;
        }

        let previousUrl = '';
        if (editor.isActive('image')) {
            previousUrl = editor.getAttributes('image').href;
        } else {
            previousUrl = editor.getAttributes('link').href;
        }

        setLinkUrl(previousUrl || '');
        setShowLinkInput(!showLinkInput);
    };

    const saveLink = () => {
        if (editor.isActive('image')) {
            if (linkUrl === '') {
                editor.chain().focus().updateAttributes('image', { href: null }).run();
            } else {
                editor.chain().focus().updateAttributes('image', { href: linkUrl }).run();
            }
        } else {
            if (linkUrl === '') {
                editor.chain().focus().extendMarkRange('link').unsetLink().run();
            } else {
                const attributes: any = { href: linkUrl };
                // Check if underline should be disabled
                if (linkStyleConfig && !linkStyleConfig.underlineEnabled) {
                    attributes.class = 'no-underline-link';
                }
                editor.chain().focus().extendMarkRange('link').setLink(attributes).run();
            }
        }
        setShowLinkInput(false);
        setLinkUrl('');
    };

    const handleQuoteClick = (e: React.MouseEvent) => {
        e.preventDefault();

        // Allow quote creation even with empty selection (it will wrap the current block)

        if (editor.isActive('customBlockquote')) {
            editor.chain().focus().unsetBlockquote().run();
        } else {
            console.log('Creating quote with styles:', defaultQuoteStyles);
            // Create with default styles if available
            // Map QuoteStyleConfig properties to CustomBlockquote attributes
            const attributes = defaultQuoteStyles ? {
                ...defaultQuoteStyles,
                backgroundColor: defaultQuoteStyles.bgColor, // Map bgColor to backgroundColor
                // Ensure all other properties are passed correctly
                borderColor: defaultQuoteStyles.borderColor,
                borderWidth: defaultQuoteStyles.borderWidth,
                textColor: defaultQuoteStyles.textColor,
                padding: defaultQuoteStyles.padding,
                fontSize: defaultQuoteStyles.fontSize,
                borderRadius: defaultQuoteStyles.borderRadius,
                width: defaultQuoteStyles.width,
                height: defaultQuoteStyles.height,
                italic: defaultQuoteStyles.italic,
                showCopyButton: defaultQuoteStyles.showCopyButton,
                showDownloadButton: defaultQuoteStyles.showDownloadButton,
                collapsible: defaultQuoteStyles.collapsible,
                fontFamily: defaultQuoteStyles.fontFamily,
                isCodeFont: defaultQuoteStyles.isCodeFont
            } : {};

            editor.chain().focus().wrapIn('customBlockquote', attributes).run();
        }
    };

    const handleCodeClick = (e: React.MouseEvent) => {
        e.preventDefault();

        // Allow toggle for typing
        // if (editor.state.selection.empty) {
        //     return;
        // }

        const isCodeActive = editor.isActive('code');
        const currentAttributes = editor.getAttributes('code');
        const wantsBackground = codeStyleConfig?.showBackground ?? true;

        if (isCodeActive) {
            const currentShowBackground = currentAttributes.showBackground ?? true;

            // If the current state doesn't match the preference, update it
            if (currentShowBackground !== wantsBackground) {
                editor.chain().focus().updateAttributes('code', { showBackground: wantsBackground }).run();
            } else {
                // If it matches, toggle it off (remove mark)
                editor.chain().focus().unsetMark('code').run();
            }
        } else {
            editor.chain().focus().setMark('code', { showBackground: wantsBackground }).run();
        }

        (editor.commands as any).removeStoredMark('code');
    };

    const handleCardCodeClick = (e: React.MouseEvent) => {
        e.preventDefault();

        // Allow toggle for typing
        // if (editor.state.selection.empty) {
        //     return;
        // }

        const isCodeActive = editor.isActive('code');
        const currentAttributes = editor.getAttributes('code');

        if (isCodeActive) {
            if (currentAttributes.showBackground !== false) {
                // Switch to card style code
                editor.chain().focus().updateAttributes('code', { showBackground: false }).run();
            } else {
                // Toggle off
                editor.chain().focus().unsetMark('code').run();
            }
        } else {
            editor.chain().focus().setMark('code', { showBackground: false }).run();
        }

        (editor.commands as any).removeStoredMark('code');
    };



    const handleClearFormatting = (e: React.MouseEvent) => {
        e.preventDefault();
        // Solo eliminamos marcas para no romper estructura de listas o código
        editor.chain().focus().unsetAllMarks().run();
    };

    const handleImageUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setIsImageUploading(true);
        try {
            const url = await uploadImageToImgBB(file);
            if (editor) {
                editor.chain().focus().setImage({ src: url }).run();
            }
        } catch (error) {
            console.error('Failed to upload image:', error);
            alert('Error al subir la imagen. Por favor intenta de nuevo.');
        } finally {
            setIsImageUploading(false);
            if (fileInputRef.current) {
                fileInputRef.current.value = '';
            }
        }
    };

    const handleVideoClick = (e: React.MouseEvent) => {
        e.preventDefault();
        setShowVideoInput(!showVideoInput);
        setShowLinkInput(false); // Cierra el input de links si estaba abierto
    };

    const saveVideo = () => {
        if (videoUrl && editor) {
            // Validamos si es YouTube y aseguramos el protocolo
            let finalUrl = videoUrl.trim();
            const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/;

            if (youtubeRegex.test(finalUrl)) {
                if (!finalUrl.match(/^https?:\/\//)) {
                    finalUrl = `https://${finalUrl}`;
                }
            } else if (!finalUrl.match(/^https?:\/\//) && !finalUrl.startsWith('data:')) {
                finalUrl = `https://${finalUrl}`;
            }

            editor.chain().focus().insertContent({ type: 'universalVideo', attrs: { src: finalUrl } }).run();
        }
        setShowVideoInput(false);
        setVideoUrl('');
    };

    const handleButtonClick = (e: React.MouseEvent) => {
        e.preventDefault();
        setShowButtonInput(!showButtonInput);
        setShowLinkInput(false);
        setShowVideoInput(false);
    };

    const saveButton = () => {
        if (buttonText && buttonUrl && editor) {
            let finalUrl = buttonUrl.trim();
            if (!finalUrl.match(/^https?:\/\//) && !finalUrl.startsWith('mailto:') && !finalUrl.startsWith('/')) {
                finalUrl = `https://${finalUrl}`;
            }

            (editor.commands as any).setCustomButton({
                text: buttonText,
                url: finalUrl,
                variant: buttonVariant,
                backgroundColor: buttonStyleConfig?.backgroundColor,
                textColor: buttonStyleConfig?.textColor,
                borderRadius: buttonStyleConfig?.borderRadius,
                width: buttonStyleConfig?.width,
                height: buttonStyleConfig?.height
            });
        }
        setShowButtonInput(false);
        setButtonText('');
        setButtonUrl('');
        setButtonVariant('visit');
    };

    const handleAlign = (alignment: 'left' | 'center' | 'right' | 'justify') => {
        if (!editor) return;

        if (editor.isActive('universalVideo')) {
            editor.chain().focus().updateAttributes('universalVideo', { align: alignment }).run();
        } else if (editor.isActive('image')) {
            editor.chain().focus().updateAttributes('image', { align: alignment }).run();
        } else {
            editor.chain().focus().setTextAlign(alignment).run();
        }
    };

    const isAlignActive = (alignment: 'left' | 'center' | 'right' | 'justify') => {
        if (!editor) return false;

        if (editor.isActive('universalVideo')) {
            return editor.getAttributes('universalVideo').align === alignment;
        }
        if (editor.isActive('image')) {
            return editor.getAttributes('image').align === alignment;
        }
        return editor.isActive({ textAlign: alignment });
    };



    return (
        <>
            <div className="fixed bottom-10 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 rounded-full bg-zinc-900/90 backdrop-blur-md border border-white/10 shadow-2xl px-4 py-2 transition-all duration-300 ease-in-out max-w-[95vw] overflow-x-auto">

                <div
                    className={`flex items-center gap-2 overflow-hidden transition-all duration-500 ease-in-out ${minimalMode ? 'w-0 opacity-0 pointer-events-none' : 'w-auto opacity-100'
                        }`}
                >
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleHeading({ level: 1 }).run())}
                        isActive={editor.isActive('heading', { level: 1 })}
                        disabled={!editor.can().toggleHeading({ level: 1 })}
                        icon={<Heading1 size={18} />}
                        title="Título 1"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleHeading({ level: 2 }).run())}
                        isActive={editor.isActive('heading', { level: 2 })}
                        disabled={!editor.can().toggleHeading({ level: 2 })}
                        icon={<Heading2 size={18} />}
                        title="Título 2"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setParagraph().run())}
                        isActive={editor.isActive('paragraph')}
                        disabled={!editor.can().setParagraph()}
                        icon={<Pilcrow size={18} />}
                        title="Párrafo"
                    />

                    <div className="w-px h-4 bg-white/10 mx-1 shrink-0" />

                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleBold().run())}
                        isActive={editor.isActive('bold')}
                        disabled={!editor.can().toggleBold()}
                        icon={<Bold size={18} />}
                        title="Negrita"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleItalic().run())}
                        isActive={editor.isActive('italic')}
                        disabled={!editor.can().toggleItalic()}
                        icon={<Italic size={18} />}
                        title="Cursiva"
                    />
                    <ToolbarButton
                        onMouseDown={handleLink}
                        isActive={editor.isActive('link') || (editor.isActive('image') && !!editor.getAttributes('image').href)}
                        disabled={!hasSelection && !editor.isActive('image')}
                        icon={<LinkIcon size={18} />}
                        title="Enlace"
                    />
                    <ToolbarButton
                        onMouseDown={handleCodeClick}
                        isActive={editor.isActive('code') && editor.getAttributes('code').showBackground !== false}
                        disabled={!editor.can().setMark('code')}
                        icon={<Code size={18} />}
                        title="Código Inline"
                    />
                    <ToolbarButton
                        onMouseDown={handleCardCodeClick}
                        isActive={editor.isActive('code') && editor.getAttributes('code').showBackground === false}
                        disabled={!editor.can().setMark('code')}
                        icon={<Terminal size={18} />}
                        title="Texto Estilo Tarjeta"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => {
                            e.preventDefault();
                            editor.chain().focus().setCodeBlock({
                                language: 'text' // Set a default language if required or just keep it simple
                            }).updateAttributes('codeBlock', {
                                collapsible: codeStyleConfig?.collapsible ?? true,
                                showLineNumbers: codeStyleConfig?.showLineNumbers ?? false,
                                wrapText: codeStyleConfig?.wrapText ?? false
                            }).run();
                        }}
                        isActive={editor.isActive('codeBlock')}
                        disabled={!editor.can().setCodeBlock()}
                        icon={<FileCode size={18} />}
                        title="Bloque de Código"
                    />

                    <ToolbarButton
                        onMouseDown={handleClearFormatting}
                        isActive={false}
                        icon={<Eraser size={18} />}
                        title="Limpiar Formato"
                    />

                    <div className="w-px h-4 bg-white/10 mx-1 shrink-0" />

                    <ToolbarButton
                        onMouseDown={(e) => { e.preventDefault(); handleImageUploadClick(); }}
                        isActive={false}
                        icon={isImageUploading ? <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> : <ImageIcon size={18} />}
                        title="Subir Imagen"
                    />
                    
                    <ToolbarButton
                        onMouseDown={async (e) => { 
                            e.preventDefault(); 
                            const input = document.createElement('input');
                            input.type = 'file';
                            input.multiple = true; // Habilitamos selección múltiple
                            
                            input.onchange = async (event: any) => {
                                const files = Array.from(event.target.files || []);
                                if (files.length === 0) return;

                                setIsFileUploading(true);
                                
                                // Procesamos los archivos uno por uno para no saturar el bot
                                for (const file of files as File[]) {
                                    setUploadProgress(0);
                                    
                                    await new Promise((resolve, reject) => {
                                        const formData = new FormData();
                                        formData.append('file', file);

                                        const xhr = new XMLHttpRequest();
                                        xhr.upload.addEventListener('progress', (e) => {
                                            if (e.lengthComputable) {
                                                const percent = Math.round((e.loaded / e.total) * 100);
                                                setUploadProgress(percent);
                                            }
                                        });

                                        xhr.onreadystatechange = () => {
                                            if (xhr.readyState === 4) {
                                                if (xhr.status === 200) {
                                                    const data = JSON.parse(xhr.responseText);
                                                    if (data.status === 'success') {
                                                        editor?.chain()
                                                            .focus()
                                                            .insertContent([
                                                                {
                                                                    type: 'customFile',
                                                                    attrs: {
                                                                        name: file.name,
                                                                        messageId: data.message_id || 'Subido',
                                                                        channelId: data.channel_id
                                                                    }
                                                                },
                                                                { type: 'paragraph' }
                                                            ])
                                                            .run();
                                                        resolve(true);
                                                    } else {
                                                        alert('Error en ' + file.name + ': ' + data.message);
                                                        resolve(false);
                                                    }
                                                } else {
                                                    alert('Error de conexión al subir ' + file.name);
                                                    resolve(false);
                                                }
                                            }
                                        };

                                        xhr.open('POST', '/upload', true);
                                        xhr.send(formData);
                                    });
                                }
                                
                                setIsFileUploading(false);
                            };
                            input.click();
                        }}
                        isActive={false}
                        icon={isFileUploading ? (
                            <div className="relative flex items-center justify-center">
                                <div className="w-8 h-8 border-2 border-primary/20 border-t-primary rounded-full animate-spin" />
                                <span className="absolute text-[10px] font-bold text-primary">{uploadProgress}%</span>
                            </div>
                        ) : <Paperclip size={18} />}
                        title="Subir Archivo a Telegram"
                    />

                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileChange}
                        accept="image/*"
                        className="hidden"
                    />

                    <ToolbarButton
                        onMouseDown={handleVideoClick}
                        isActive={false}
                        icon={<Video size={18} />}
                        title="Insertar Video de YouTube"
                    />

                    <ToolbarButton
                        onMouseDown={handleButtonClick}
                        isActive={false}
                        icon={<MousePointerClick size={18} />}
                        title="Insertar Botón de Acción"
                    />

                    <div className="w-px h-4 bg-white/10 mx-1 shrink-0" />

                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => handleAlign('left'))}
                        isActive={isAlignActive('left')}
                        icon={<AlignLeft size={18} />}
                        title="Alinear a la izquierda"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => handleAlign('center'))}
                        isActive={isAlignActive('center')}
                        icon={<AlignCenter size={18} />}
                        title="Centrar"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => handleAlign('right'))}
                        isActive={isAlignActive('right')}
                        icon={<AlignRight size={18} />}
                        title="Alinear a la derecha"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => handleAlign('justify'))}
                        isActive={isAlignActive('justify')}
                        icon={<AlignJustify size={18} />}
                        title="Justificar"
                    />

                    <div className="w-px h-4 bg-white/10 mx-1 shrink-0" />

                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleBulletList().run())}
                        isActive={editor.isActive('bulletList')}
                        disabled={!editor.can().toggleBulletList()}
                        icon={<List size={18} />}
                        title="Lista con viñetas"
                    />
                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().toggleOrderedList().run())}
                        isActive={editor.isActive('orderedList')}
                        disabled={!editor.can().toggleOrderedList()}
                        icon={<ListOrdered size={18} />}
                        title="Lista numerada"
                    />

                    <div className="w-px h-4 bg-white/10 mx-1 shrink-0" />

                    <ToolbarButton
                        onMouseDown={handleQuoteClick}
                        isActive={editor.isActive('customBlockquote')}
                        icon={<Quote size={18} />}
                        title="Cita Personalizada"
                    />

                    <ToolbarButton
                        onMouseDown={(e) => handleAction(e, () => editor.chain().focus().setHorizontalRule().run())}
                        isActive={false}
                        icon={<Minus size={18} />}
                        title="Insertar Separador (---)"
                    />

                </div>

                {onOpenSettings && (
                    <>
                        <div className={`w-px h-4 bg-white/10 mx-1 shrink-0 transition-opacity duration-300 ${minimalMode ? 'opacity-0' : 'opacity-100'}`} />
                        <ToolbarButton
                            onMouseDown={(e) => {
                                e.preventDefault();
                                onOpenSettings();
                            }}
                            isActive={false}
                            icon={<Settings size={18} />}
                            title="Configurar Estilo"
                        />
                    </>
                )}
            </div>

            {
                showLinkInput && (
                    <div className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 p-2 rounded-xl bg-[#1a1a1a] border border-white/10 shadow-2xl animate-fade-in">
                        <input
                            type="url"
                            value={linkUrl}
                            onChange={(e) => setLinkUrl(e.target.value)}
                            placeholder="https://ejemplo.com"
                            className="bg-transparent border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary min-w-[200px]"
                            onKeyDown={(e) => {
                                if (e.key === 'Enter') saveLink();
                                if (e.key === 'Escape') setShowLinkInput(false);
                            }}
                            onMouseDown={(e) => e.stopPropagation()}
                            onClick={(e) => e.stopPropagation()}
                        />
                        <button
                            onClick={(e) => { e.stopPropagation(); saveLink(); }}
                            className="p-1.5 rounded-lg bg-primary text-background hover:opacity-90 transition-opacity"
                            title="Guardar enlace"
                        >
                            <Check size={16} strokeWidth={2.5} />
                        </button>
                        <button
                            onClick={(e) => { e.stopPropagation(); setShowLinkInput(false); }}
                            className="p-1.5 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
                            title="Cancelar"
                        >
                            <X size={16} />
                        </button>
                    </div>
                )
            }

            {showVideoInput && (
                <div
                    className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex items-center gap-2 p-2 rounded-xl bg-[#1a1a1a] border border-white/10 shadow-2xl animate-fade-in"
                    onMouseDown={(e) => e.stopPropagation()}
                >
                    <input
                        type="url"
                        value={videoUrl}
                        onChange={(e) => setVideoUrl(e.target.value)}
                        placeholder="https://www.youtube.com/watch?v=..."
                        className="bg-transparent border border-white/10 rounded-lg px-3 py-1.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary min-w-[250px]"
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') saveVideo();
                            if (e.key === 'Escape') setShowVideoInput(false);
                        }}
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                    />
                    <button
                        onClick={(e) => { e.stopPropagation(); saveVideo(); }}
                        className="p-1.5 rounded-lg bg-primary text-background hover:opacity-90 transition-opacity"
                        title="Confirmar video"
                    >
                        <Check size={16} strokeWidth={2.5} />
                    </button>
                    <button
                        onClick={(e) => { e.stopPropagation(); setShowVideoInput(false); }}
                        className="p-1.5 rounded-lg hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
                        title="Cancelar"
                    >
                        <X size={16} />
                    </button>
                </div>
            )}

            {showButtonInput && (
                <div
                    className="fixed bottom-24 left-1/2 -translate-x-1/2 z-50 flex flex-col gap-2 p-2 rounded-xl bg-[#1a1a1a] border border-white/10 shadow-2xl animate-fade-in w-[240px]"
                    onMouseDown={(e) => e.stopPropagation()}
                >
                    <input
                        type="text"
                        value={buttonText}
                        onChange={(e) => setButtonText(e.target.value)}
                        placeholder="Texto"
                        className="bg-transparent border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-primary w-full"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => e.stopPropagation()}
                        autoFocus
                    />
                    <input
                        type="url"
                        value={buttonUrl}
                        onChange={(e) => setButtonUrl(e.target.value)}
                        placeholder="URL"
                        className="bg-transparent border border-white/10 rounded-lg px-2 py-1.5 text-xs text-white placeholder-zinc-500 focus:outline-none focus:border-primary w-full"
                        onMouseDown={(e) => e.stopPropagation()}
                        onClick={(e) => e.stopPropagation()}
                    />
                    <div className="grid grid-cols-4 gap-1">
                        <button
                            onClick={() => setButtonVariant('visit')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'visit' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Visitar"
                        >
                            <ExternalLink size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('download')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'download' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Descargar"
                        >
                            <Download size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('github')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'github' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="GitHub"
                        >
                            <Github size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('telegram')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'telegram' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Telegram"
                        >
                            <Send size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('twitter')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'twitter' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Twitter"
                        >
                            <Twitter size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('linkedin')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'linkedin' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="LinkedIn"
                        >
                            <Linkedin size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('instagram')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'instagram' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Instagram"
                        >
                            <Instagram size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('youtube')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'youtube' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="YouTube"
                        >
                            <Youtube size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('facebook')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'facebook' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Facebook"
                        >
                            <Facebook size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('tiktok')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'tiktok' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="TikTok"
                        >
                            <TiktokIcon size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('x')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'x' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="X"
                        >
                            <X size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('code')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'code' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Código"
                        >
                            <Code size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('layers')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'layers' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Capas"
                        >
                            <Layers size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('community')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'community' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Comunidad"
                        >
                            <MessageCircle size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('globe')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'globe' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Web"
                        >
                            <Globe size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('mail')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'mail' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Email"
                        >
                            <Mail size={14} />
                        </button>
                        <button
                            onClick={() => setButtonVariant('file')}
                            className={`flex justify-center items-center py-1.5 rounded-md border transition-colors ${buttonVariant === 'file' ? 'bg-primary/20 border-primary text-primary' : 'border-white/10 text-zinc-400 hover:bg-white/5'}`}
                            title="Documento"
                        >
                            <FileText size={14} />
                        </button>
                    </div>
                    <div className="flex justify-end gap-1 mt-1">
                        <button
                            onClick={() => setShowButtonInput(false)}
                            className="px-2 py-1 rounded-md hover:bg-white/10 text-zinc-400 hover:text-white transition-colors text-[10px]"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={saveButton}
                            className="px-2 py-1 rounded-md bg-primary text-background hover:opacity-90 transition-opacity text-[10px] font-medium"
                        >
                            Insertar
                        </button>
                    </div>
                </div>
            )}


        </>
    );
};

interface ToolbarButtonProps {
    onMouseDown: (e: React.MouseEvent) => void;
    isActive?: boolean;
    disabled?: boolean;
    icon: React.ReactNode;
    title: string;
}

const ToolbarButton: React.FC<ToolbarButtonProps> = ({ onMouseDown, isActive, disabled, icon, title }) => (
    <button
        onMouseDown={onMouseDown}
        disabled={disabled}
        title={title}
        className={`p-2 rounded-full transition-colors ${isActive
            ? 'bg-white text-black'
            : 'text-zinc-400 hover:text-white hover:bg-white/10'
            } ${disabled ? 'opacity-40 cursor-not-allowed' : 'opacity-100 cursor-pointer'}`}
    >
        {icon}
    </button>
);
