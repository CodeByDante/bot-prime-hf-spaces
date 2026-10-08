import React, { useState, useRef, useEffect } from 'react';
import { NodeViewWrapper } from '@tiptap/react';
import { AlignLeft, AlignCenter, AlignRight, Maximize2 } from 'lucide-react';

export const ResizableVideoComponent = (props: any) => {
    const { node, updateAttributes, selected, editor } = props;
    const [width, setWidth] = useState(node.attrs.width || '100%');
    const [align, setAlign] = useState(node.attrs.align || 'center');
    const [isResizing, setIsResizing] = useState(false);
    const [isMounted, setIsMounted] = useState(false);

    const containerRef = useRef<HTMLDivElement>(null);
    const resizeRef = useRef<{ startX: number; startWidth: number } | null>(null);

    useEffect(() => {
        setIsMounted(true);
        setWidth(node.attrs.width || '100%');
        setAlign(node.attrs.align || 'center');
    }, [node.attrs]);

    const handleMouseDown = (e: React.MouseEvent) => {
        e.preventDefault();
        if (containerRef.current) {
            setIsResizing(true);
            resizeRef.current = {
                startX: e.clientX,
                startWidth: containerRef.current.offsetWidth,
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
        if (newWidth > 200) {
            setWidth(`${newWidth}px`);
        }
    };

    const handleMouseUp = () => {
        setIsResizing(false);
        resizeRef.current = null;
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
        // Update attributes only on mouse up
        if (containerRef.current) {
            updateAttributes({ width: `${containerRef.current.offsetWidth}px` });
        }
    };

    const handleAlign = (newAlign: 'left' | 'center' | 'right') => {
        setAlign(newAlign);
        updateAttributes({ align: newAlign });
    };

    let containerStyle: React.CSSProperties = {
        display: 'flex',
        justifyContent: align === 'left' ? 'flex-start' : align === 'right' ? 'flex-end' : 'center',
        margin: '1rem 0',
        clear: 'both',
        position: 'relative',
    };

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

    // Ensure URL is valid string
    const videoUrl = typeof node.attrs.src === 'string' ? node.attrs.src.trim() : '';

    const getEmbedConfig = (url: string) => {
        // 1. Dropbox (Tratamiento especial: video nativo)
        if (url.includes('dropbox.com')) {
            try {
                const urlObj = new URL(url);
                urlObj.searchParams.set('raw', '1');
                urlObj.searchParams.delete('dl');
                return {
                    type: 'video',
                    src: urlObj.toString()
                };
            } catch (e) {
                return {
                    type: 'video',
                    src: url
                };
            }
        }

        // 2. Archivos directos (Video nativo)
        if (url.match(/\.(mp4|mov|webm|ogg)$/i)) {
            return { type: 'video', src: url };
        }

        // 3. Transformaciones para Iframe
        let embedUrl = url;

        // YouTube
        if (url.includes('youtube.com') || url.includes('youtu.be')) {
            const id = url.match(/.*(youtu.be\/|v\/|u\/\w\/|embed\/|watch\?v=|&v=)([^#&?]*).*/)?.[2];
            if (id) embedUrl = `https://www.youtube.com/embed/${id}`;
        }
        // Vimeo
        else if (url.includes('vimeo.com')) {
            const id = url.match(/vimeo\.com\/(?:channels\/(?:\w+\/)?|groups\/(?:[^\/]*)\/videos\/|album\/(?:\d+)\/video\/|video\/|)(\d+)/)?.[1];
            if (id) embedUrl = `https://player.vimeo.com/video/${id}`;
        }
        // Google Drive
        else if (url.includes('drive.google.com')) {
            embedUrl = url.replace(/\/view.*/, '/preview').replace(/\/open.*/, '/preview');
        }
        // Facebook
        else if (url.includes('facebook.com') || url.includes('fb.watch')) {
            embedUrl = `https://www.facebook.com/plugins/video.php?href=${encodeURIComponent(url)}&show_text=false`;
        }
        // MEGA
        else if (url.includes('mega.nz')) {
            // Mega suele requerir formato embed, intentamos conversión simple si es enlace de archivo
            if (!url.includes('/embed')) embedUrl = url.replace('/file/', '/embed/');
        }
        // TikTok (Experimental - requiere video ID)
        else if (url.includes('tiktok.com')) {
            const videoId = url.match(/video\/(\d+)/)?.[1];
            if (videoId) embedUrl = `https://www.tiktok.com/embed/v2/${videoId}`;
        }

        return { type: 'iframe', src: embedUrl };
    };

    const embedConfig = getEmbedConfig(videoUrl);

    return (
        <NodeViewWrapper style={containerStyle} className="resizable-video-wrapper group">
            <div
                ref={containerRef}
                className={`relative inline-block transition-all ${selected && editor.isEditable ? 'ring-2 ring-primary rounded-lg' : ''}`}
                style={{
                    width: width,
                    maxWidth: '100%',
                }}
            >
                <div className="rounded-lg overflow-hidden shadow-lg bg-black pointer-events-auto relative pt-[56.25%]">
                    {/* Overlay to capture clicks when not selected */}
                    {!selected && editor.isEditable && (
                        <div className="absolute inset-0 z-10 bg-transparent cursor-pointer" />
                    )}

                    {isMounted && videoUrl ? (
                        embedConfig.type === 'iframe' ? (
                            <iframe
                                src={embedConfig.src}
                                title="Video player"
                                frameBorder="0"
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                                allowFullScreen
                                className={`absolute top-0 left-0 w-full h-full ${selected && !isResizing ? 'pointer-events-auto' : 'pointer-events-none'}`}
                            />
                        ) : (
                            <video
                                src={embedConfig.src}
                                controls
                                className={`absolute top-0 left-0 w-full h-full object-contain bg-black ${selected && !isResizing ? 'pointer-events-auto' : 'pointer-events-none'}`}
                            />
                        )
                    ) : (
                        <div className="absolute inset-0 flex items-center justify-center text-white/50 bg-zinc-900">
                            {videoUrl ? 'Cargando video...' : 'Sin URL de video'}
                        </div>
                    )}
                </div>



                {/* Resize Handle - Only in Edit Mode */}
                {selected && editor.isEditable && (
                    <div
                        className="absolute bottom-2 right-2 w-4 h-4 bg-primary rounded-full cursor-se-resize shadow-md border-2 border-white z-50"
                        onMouseDown={handleMouseDown}
                    />
                )}

                {/* Toolbar (Visible on hover or selected) - Only in Edit Mode */}
                {editor.isEditable && (
                    <div className={`absolute top-2 right-2 flex gap-1 bg-black/80 backdrop-blur rounded-lg p-1 opacity-0 group-hover:opacity-100 transition-opacity ${selected ? 'opacity-100' : ''} z-50`}>
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
                    </div>
                )}
            </div>
        </NodeViewWrapper>
    );
};
