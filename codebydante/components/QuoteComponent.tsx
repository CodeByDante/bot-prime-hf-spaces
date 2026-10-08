import React, { useState, useRef, useEffect } from 'react';
import { NodeViewWrapper, NodeViewContent, NodeViewProps } from '@tiptap/react';
import { Copy, Check, Download, ChevronDown, ChevronUp, Settings } from 'lucide-react';
import { DownloadButton } from './DownloadButton';

export const QuoteComponent: React.FC<NodeViewProps> = (props) => {
    const [copied, setCopied] = useState(false);
    const [isManualExpanded, setIsManualExpanded] = useState(false);
    const { node } = props;
    const { attrs } = node;
    const contentRef = useRef<HTMLDivElement>(null);
    const [contentHeight, setContentHeight] = useState<number>(0);

    useEffect(() => {
        const measureHeight = () => {
            if (contentRef.current) {
                const currentMaxHeight = contentRef.current.style.maxHeight;
                contentRef.current.style.maxHeight = 'none';
                setContentHeight(contentRef.current.scrollHeight);
                contentRef.current.style.maxHeight = currentMaxHeight;
            }
        };

        measureHeight();

        window.addEventListener('resize', measureHeight);
        return () => window.removeEventListener('resize', measureHeight);
    }, [node.textContent, attrs.collapsible]);

    const toggleExpand = () => {
        setIsManualExpanded(!isManualExpanded);
    };

    const handleCopy = () => {
        const text = node.textContent;
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    const handleDownload = () => {
        const text = node.textContent;
        const element = document.createElement("a");
        const file = new Blob([text], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        element.download = 'cita.txt';
        document.body.appendChild(element);
        element.click();
        document.body.removeChild(element);
    };

    // Construct dynamic styles from attributes
    const dynamicStyles: React.CSSProperties = {
        borderLeftColor: attrs.borderColor || 'gray',
        borderLeftWidth: attrs.borderWidth || '4px',
        backgroundColor: attrs.backgroundColor || 'transparent',
        color: attrs.textColor || 'inherit',
        padding: attrs.padding || '4px',
        fontSize: attrs.fontSize || 'inherit',
        borderRadius: attrs.borderRadius || '0px',
        width: attrs.width || '100%',
        minHeight: attrs.height || 'auto',
        fontFamily: attrs.isCodeFont ? 'monospace' : (attrs.fontFamily || 'inherit'),
        fontStyle: attrs.italic ? 'italic' : 'normal',
        borderLeftStyle: 'solid', // Ensure border style is solid
        wordBreak: 'break-word',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        position: 'relative', // Ensure relative positioning for absolute children
        lineHeight: '1.5', // Enforce consistent line height
    };

    const handleOpenSettings = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (props.editor.isEditable) {
            const event = new CustomEvent('block-triple-click', {
                detail: { type: 'quote', pos: props.getPos() },
                bubbles: true
            });
            props.editor.view.dom.dispatchEvent(event);
        }
    };

    const isEditing = props.editor.isEditable;
    const isCollapsed = attrs.collapsible && !isManualExpanded;

    const hasButtons = attrs.showCopyButton || attrs.showDownloadButton || isEditing || attrs.collapsible;

    return (
        <NodeViewWrapper
            style={dynamicStyles}
            className="group my-4 rounded-sm transition-all [&_p]:m-0"
        >
            {hasButtons && (
                <div className="absolute top-2 right-2 z-10 flex gap-2">
                    {attrs.collapsible && (
                        <button
                            onClick={toggleExpand}
                            contentEditable={false}
                            className="p-1 bg-zinc-800/50 rounded text-zinc-300 hover:text-white transition-all backdrop-blur-sm"
                            title={isManualExpanded ? "Contraer" : "Expandir"}
                        >
                            {isManualExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                    )}
                    {isEditing && (
                        <button
                            onClick={(e) => handleOpenSettings(e)}
                            contentEditable={false}
                            className="p-1 bg-zinc-800/50 rounded text-zinc-300 hover:text-white transition-all backdrop-blur-sm"
                            title="Configurar Estilo"
                        >
                            <Settings size={14} />
                        </button>
                    )}
                    {attrs.showCopyButton && (
                        <button
                            onClick={handleCopy}
                            contentEditable={false} // Important: prevent editor focus issues
                            className="p-1 bg-zinc-800/50 rounded text-zinc-300 hover:text-white transition-all backdrop-blur-sm"
                            title="Copiar texto"
                        >
                            {copied ? <Check size={14} /> : <Copy size={14} />}
                        </button>
                    )}
                    {attrs.showDownloadButton && (
                        <button
                            onClick={handleDownload}
                            contentEditable={false}
                            className="p-1 bg-zinc-800/50 rounded text-zinc-300 hover:text-white transition-all backdrop-blur-sm"
                            title="Descargar"
                        >
                            <Download size={14} />
                        </button>
                    )}
                </div>
            )}

            {/* --- Contenedor de Contenido con Lógica de Colapsado --- */}
            <div
                ref={contentRef}
                className={hasButtons ? "pr-28" : ""}
                style={{
                    // Si está colapsado, forzamos una altura máxima (aprox 3 líneas)
                    // Si NO es colapsable (feature disabled), usamos 'none' para que crezca automático
                    // Si es colapsable pero expandido, usamos la altura calculada para animar
                    maxHeight: isCollapsed
                        ? '4.5em'
                        : (attrs.collapsible ? `${contentHeight}px` : 'none'),
                    overflow: 'hidden',
                    position: 'relative',
                    transition: 'max-height 0.5s cubic-bezier(0.4, 0, 0.2, 1)', // Smooth slide animation
                    // Opcional: Un pequeño gradiente para suavizar el corte si está colapsado
                    maskImage: isCollapsed ? 'linear-gradient(to bottom, black 60%, transparent 100%)' : 'none',
                    WebkitMaskImage: isCollapsed ? 'linear-gradient(to bottom, black 60%, transparent 100%)' : 'none'
                }}
            >
                <NodeViewContent />
            </div>

        </NodeViewWrapper>
    );
};
