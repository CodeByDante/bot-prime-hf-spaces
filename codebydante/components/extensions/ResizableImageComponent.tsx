
import React, { useState, useRef, useEffect } from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { AlignLeft, AlignCenter, AlignRight, Maximize2, Link as LinkIcon, X, Check } from 'lucide-react';

export const ResizableImageComponent = (props: any) => {
    const { node, updateAttributes, selected, editor } = props;
    const [width, setWidth] = useState(node.attrs.width || '100%');
    const [height, setHeight] = useState(node.attrs.height || 'auto');
    const [align, setAlign] = useState(node.attrs.align || 'center');
    const [isResizing, setIsResizing] = useState(false);
    const [isLightboxOpen, setIsLightboxOpen] = useState(false);
    const [isLinkMenuOpen, setIsLinkMenuOpen] = useState(false);
    const [tempLink, setTempLink] = useState('');

    const imageRef = useRef<HTMLImageElement>(null);
    const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

    useEffect(() => {
        setWidth(node.attrs.width || '100%');
        setHeight(node.attrs.height || 'auto');
        setAlign(node.attrs.align || 'center');
    }, [node.attrs]);

    const handleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        if (imageRef.current) {
            setIsResizing(true);
            resizeRef.current = {
                startX: e.clientX,
                startWidth: imageRef.current.offsetWidth,
            };
            document.addEventListener('mousemove', handleMouseMove);
            document.addEventListener('mouseup', handleMouseUp);
        }
    };

    const handleMouseMove = (e: MouseEvent) => {
        if (!resizeRef.current) return;
        const diff = e.clientX - resizeRef.current.startX;
        const newWidth = resizeRef.current.startWidth + diff;
        // Limit min width
        if (newWidth > 100) {
            setWidth(`${newWidth}px`);
        }
    };

    const handleMouseUp = () => {
        setIsResizing(false);
        resizeRef.current = null;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        // Update attributes only on mouse up to avoid too many updates
        if (imageRef.current) {
            updateAttributes({ width: `${imageRef.current.offsetWidth}px` });
        }
    };

    const handleAlign = (newAlign: 'left' | 'center' | 'right') => {
        setAlign(newAlign);
        updateAttributes({ align: newAlign });
    };

    const handleLink = () => {
        setTempLink(node.attrs.href || '');
        setIsLinkMenuOpen(true);
    };

    const saveLink = () => {
        updateAttributes({ href: tempLink || null });
        setIsLinkMenuOpen(false);
    };

    const handleImageClick = (e: React.MouseEvent) => {
        // Prevent navigation in edit mode
        if (editor.isEditable) {
            e.preventDefault();
        }

        // Triple click detection handled by TipTap or manual logic if needed.
        // For simplicity, we can use detail property if available or just rely on toolbar.
        if (e.detail === 3 && editor.isEditable) {
            handleLink();
        }
    };

    const handleDoubleClick = (e: React.MouseEvent) => {
        if (!editor.isEditable && !node.attrs.href) {
            setIsLightboxOpen(true);
        }
    };

    let containerStyle: React.CSSProperties = {
        display: 'flex',
        justifyContent: align === 'left' ? 'flex-start' : align === 'right' ? 'flex-end' : 'center',
        margin: '1rem 0',
        clear: 'both', // Default to clear
        position: 'relative',
    };

    // For "Word-like" wrapping, we might use float.
    // However, flexbox centering doesn't work well with float.
    // If align is left/right, we can use float.
    if (align === 'left') {
        containerStyle = {
            float: 'left',
            marginRight: '1rem',
            marginBottom: '0.5rem',
            display: 'inline-block',
        };
    } else if (align === 'right') {
        containerStyle = {
            float: 'right',
            marginLeft: '1rem',
            marginBottom: '0.5rem',
            display: 'inline-block',
        };
    }

    return (
        <NodeViewWrapper style={containerStyle} className="resizable-image-wrapper group">
            <div className={`relative inline-block transition-all ${selected && editor.isEditable ? 'ring-2 ring-primary rounded-lg' : ''}`}>
                {node.attrs.href ? (
                    <a
                        href={node.attrs.href}
                        target={node.attrs.target}
                        onClick={handleImageClick}
                        className="block"
                    >
                        <img
                            ref={imageRef}
                            src={node.attrs.src}
                            alt={node.attrs.alt}
                            style={{
                                width: width,
                                height: height,
                                maxWidth: '100%',
                                borderRadius: '0.5rem',
                                display: 'block',
                            }}
                            className="transition-shadow shadow-lg"
                        />
                    </a>
                ) : (
                    <img
                        ref={imageRef}
                        src={node.attrs.src}
                        alt={node.attrs.alt}
                        style={{
                            width: width,
                            height: height,
                            maxWidth: '100%',
                            borderRadius: '0.5rem',
                            display: 'block',
                            cursor: !editor.isEditable && !node.attrs.href ? 'zoom-in' : 'default'
                        }}
                        className="transition-shadow shadow-lg"
                        onClick={handleImageClick}
                        onDoubleClick={handleDoubleClick}
                    />
                )}

                {/* Resize Handle - Only in Edit Mode */}
                {selected && editor.isEditable && (
                    <div
                        className="absolute bottom-2 right-2 w-4 h-4 bg-primary rounded-full cursor-se-resize shadow-md border-2 border-white z-10"
                        onMouseDown={handleMouseDown}
                    />
                )}

                {/* Toolbar (Visible on hover or selected) - Only in Edit Mode */}
                {editor.isEditable && (
                    <div className={`absolute top-2 right-2 flex gap-1 bg-black/80 backdrop-blur rounded-lg p-1 opacity-0 group-hover:opacity-100 transition-opacity ${selected ? 'opacity-100' : ''}`}>
                        <button
                            onClick={() => handleAlign('left')}
                            className={`p-1 rounded hover:bg-white/20 ${align === 'left' ? 'text-primary' : 'text-white'}`}
                            title="Align Left"
                        >
                            <AlignLeft size={14} />
                        </button>
                        <button
                            onClick={() => handleAlign('center')}
                            className={`p-1 rounded hover:bg-white/20 ${align === 'center' ? 'text-primary' : 'text-white'}`}
                            title="Align Center"
                        >
                            <AlignCenter size={14} />
                        </button>
                        <button
                            onClick={() => handleAlign('right')}
                            className={`p-1 rounded hover:bg-white/20 ${align === 'right' ? 'text-primary' : 'text-white'}`}
                            title="Align Right"
                        >
                            <AlignRight size={14} />
                        </button>
                        <button
                            onClick={() => {
                                setWidth('100%');
                                updateAttributes({ width: '100%' });
                            }}
                            className="p-1 rounded hover:bg-white/20 text-white"
                            title="Full Width"
                        >
                            <Maximize2 size={14} />
                        </button>
                        <div className="w-px h-4 bg-white/20 mx-1 self-center" />
                        <button
                            onClick={handleLink}
                            className={`p-1 rounded hover:bg-white/20 ${node.attrs.href ? 'text-primary' : 'text-white'}`}
                            title={node.attrs.href ? "Editar Enlace" : "Añadir Enlace"}
                        >
                            <LinkIcon size={14} />
                        </button>
                    </div>
                )}
            </div>

            {/* Link Menu Modal */}
            {isLinkMenuOpen && (
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-[#1e1e1e] border border-white/10 rounded-xl shadow-2xl p-4 min-w-[300px] animate-fade-in flex flex-col gap-3">
                    <h4 className="text-sm font-medium text-white">Editar Enlace</h4>
                    <input
                        type="url"
                        value={tempLink}
                        onChange={(e) => setTempLink(e.target.value)}
                        placeholder="https://ejemplo.com"
                        className="w-full bg-black/20 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary transition-colors"
                        autoFocus
                        onKeyDown={(e) => {
                            if (e.key === 'Enter') saveLink();
                            if (e.key === 'Escape') setIsLinkMenuOpen(false);
                        }}
                    />
                    <div className="flex gap-2 justify-end">
                        <button
                            onClick={() => setIsLinkMenuOpen(false)}
                            className="px-3 py-1.5 rounded-lg text-sm text-zinc-400 hover:text-white hover:bg-white/5 transition-colors"
                        >
                            Cancelar
                        </button>
                        <button
                            onClick={saveLink}
                            className="px-3 py-1.5 rounded-lg text-sm bg-primary text-background font-medium hover:opacity-90 transition-opacity flex items-center gap-1.5"
                        >
                            <Check size={14} strokeWidth={2.5} />
                            Guardar
                        </button>
                    </div>
                </div>
            )}

            {/* Lightbox Overlay */}
            {isLightboxOpen && (
                <div
                    className="fixed inset-0 z-[9999] bg-black/90 flex items-center justify-center p-4 animate-fade-in"
                    onClick={() => setIsLightboxOpen(false)}
                >
                    <button
                        className="absolute top-4 right-4 text-white/70 hover:text-white transition-colors"
                        onClick={() => setIsLightboxOpen(false)}
                    >
                        <X size={32} />
                    </button>
                    <img
                        src={node.attrs.src}
                        alt={node.attrs.alt}
                        className="max-w-full max-h-full object-contain rounded-lg shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    />
                </div>
            )}
        </NodeViewWrapper>
    );
};
