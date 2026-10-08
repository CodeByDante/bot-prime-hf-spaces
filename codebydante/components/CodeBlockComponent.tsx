import React, { useState, useEffect, useRef } from 'react';
import { NodeViewWrapper, NodeViewContent, NodeViewProps } from '@tiptap/react';
import { Copy, Check, Download, Pencil, ChevronDown, ChevronUp, Settings } from 'lucide-react';

export const CodeBlockComponent: React.FC<NodeViewProps> = (props) => {
    const [copied, setCopied] = useState(false);
    const { node: { attrs: { language: defaultLanguage, filename: defaultFilename, showLineNumbers, wrapText } }, updateAttributes, extension } = props;
    const [detectedLang, setDetectedLang] = useState(defaultLanguage || 'text');
    const [isEditingName, setIsEditingName] = useState(false);
    const [filename, setFilename] = useState(defaultFilename || '');
    const inputRef = useRef<HTMLInputElement>(null);
    const [isManualExpanded, setIsManualExpanded] = useState(false);
    const contentRef = useRef<HTMLDivElement>(null);
    const [contentHeight, setContentHeight] = useState<string | number>('300px'); // Default max height for collapsed state

    const handleCopy = () => {
        const text = props.node.textContent;
        navigator.clipboard.writeText(text).then(() => {
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        });
    };

    const detectLanguage = (content: string): string => {
        const c = content.trim();
        if (c.startsWith('npm ') || c.startsWith('yarn ') || c.startsWith('pnpm ') || c.startsWith('npx ') || c.startsWith('git ')) return 'bash';
        if (c.includes('@echo off') || c.startsWith('::') || c.startsWith('REM ') || c.includes('set "PROYECTO=')) return 'batch';
        if ((c.includes('def ') && c.includes(':')) || c.includes('import pandas') || c.includes('print(')) return 'python';
        if (c.includes('public class') || c.includes('System.out.println') || c.includes('public static void')) return 'java';
        if (c.includes('import React') || c.includes('export const') || c.includes('interface ')) return 'typescript';
        if (c.includes('function ') || c.includes('const ') || c.includes('let ') || c.includes('console.log')) return 'javascript';
        if (c.includes('<!DOCTYPE html>') || c.includes('</div>')) return 'html';
        if (c.includes('{') && c.includes('}') && c.includes(':') && c.includes(';')) return 'css';
        return 'text';
    };

    useEffect(() => {
        const content = props.node.textContent;
        const lang = detectLanguage(content);
        if (lang !== detectedLang && lang !== 'text') {
            setDetectedLang(lang);
            updateAttributes({ language: lang });
        } else if (lang === 'text' && defaultLanguage && defaultLanguage !== 'text') {
            setDetectedLang(defaultLanguage);
        }

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
    }, [props.node.textContent, showLineNumbers, wrapText]);

    useEffect(() => {
        if (isEditingName && inputRef.current) {
            inputRef.current.focus();
        }
    }, [isEditingName]);

    const handleDownload = () => {
        const text = props.node.textContent;

        let downloadName = filename;
        if (!downloadName) {
            const extensionMap: Record<string, string> = {
                'bash': 'sh',
                'batch': 'bat',
                'python': 'py',
                'java': 'java',
                'typescript': 'ts',
                'javascript': 'js',
                'html': 'html',
                'css': 'css',
                'text': 'txt'
            };
            const ext = extensionMap[detectedLang] || 'txt';
            downloadName = `code.${ext}`;
        }

        const blob = new Blob([text], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = downloadName;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    };

    const handleNameSubmit = () => {
        setIsEditingName(false);
        updateAttributes({ filename });
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleNameSubmit();
        }
    };

    const handleOpenSettings = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (props.editor.isEditable) {
            const event = new CustomEvent('block-triple-click', {
                detail: { type: 'code', pos: props.getPos() },
                bubbles: true
            });
            props.editor.view.dom.dispatchEvent(event);
        }
    };

    const toggleExpand = () => {
        setIsManualExpanded(!isManualExpanded);
    };

    const isCollapsed = props.node.attrs.collapsible && !isManualExpanded;

    const lineCount = props.node.textContent.split('\n').length;

    return (
        <NodeViewWrapper
            className="relative group my-6 rounded-xl overflow-hidden bg-[#151515] border border-white/10 shadow-2xl ring-1 ring-white/5 w-full not-prose"
        >
            <div className="flex items-center justify-between px-4 py-3 bg-[#202020] border-b border-white/5">
                <div className="flex items-center gap-2">
                    <div className="flex gap-1.5">
                        <div className="w-3 h-3 rounded-full bg-[#ff5f56] border border-[#e0443e]/50"></div>
                        <div className="w-3 h-3 rounded-full bg-[#ffbd2e] border border-[#dea123]/50"></div>
                        <div className="w-3 h-3 rounded-full bg-[#27c93f] border border-[#1aab29]/50"></div>
                    </div>

                    {isEditingName ? (
                        <input
                            ref={inputRef}
                            type="text"
                            value={filename}
                            onChange={(e) => setFilename(e.target.value)}
                            onBlur={handleNameSubmit}
                            onKeyDown={handleKeyDown}
                            className="ml-3 text-xs font-medium text-zinc-200 bg-white/10 rounded px-1.5 py-0.5 outline-none border border-white/20 w-32 font-mono"
                            placeholder="nombre.ext"
                        />
                    ) : (
                        <span className="ml-3 text-xs font-medium text-zinc-400 uppercase tracking-wider select-none font-mono">
                            {filename || detectedLang}
                        </span>
                    )}
                </div>
                <div className="flex items-center gap-2">
                    {props.editor.isEditable && (
                        <>
                            <button
                                onClick={(e) => handleOpenSettings(e)}
                                contentEditable={false}
                                className="p-1.5 rounded-md transition-all duration-200 hover:bg-white/10 text-zinc-400 hover:text-white"
                                title="Configurar Estilo"
                            >
                                <Settings size={14} />
                            </button>
                            <button
                                onClick={() => setIsEditingName(true)}
                                contentEditable={false}
                                className="p-1.5 rounded-md transition-all duration-200 hover:bg-white/10 text-zinc-400 hover:text-white"
                                title="Editar nombre"
                            >
                                <Pencil size={14} />
                            </button>
                        </>
                    )}
                    {props.node.attrs.collapsible && (
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                toggleExpand();
                            }}
                            contentEditable={false}
                            className="p-1.5 rounded-md transition-all duration-200 hover:bg-white/10 text-zinc-400 hover:text-white"
                            title={isManualExpanded ? "Contraer" : "Expandir"}
                        >
                            {isManualExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                        </button>
                    )}
                    <button
                        onClick={handleDownload}
                        contentEditable={false}
                        className="p-1.5 rounded-md transition-all duration-200 hover:bg-white/10 text-zinc-400 hover:text-white"
                        title="Descargar archivo"
                    >
                        <Download size={14} />
                    </button>
                    <div className="relative">
                        <button
                            onClick={handleCopy}
                            contentEditable={false}
                            className={`p-1.5 rounded-md transition-all duration-200 ${copied
                                ? 'bg-green-500/20 text-green-400 scale-110'
                                : 'hover:bg-white/10 text-zinc-400 hover:text-white'
                                }`}
                            title="Copiar código"
                        >
                            {copied ? <Check size={14} strokeWidth={3} /> : <Copy size={14} />}
                        </button>
                        {copied && (
                            <div className="absolute bottom-full right-0 mb-2 px-2 py-1 bg-[#252525] border border-white/10 text-green-400 text-[10px] font-medium rounded shadow-xl animate-in fade-in slide-in-from-bottom-1 whitespace-nowrap z-50">
                                Copiado!
                            </div>
                        )}
                    </div>
                </div>
            </div>
            <div
                ref={contentRef}
                style={{
                    maxHeight: props.node.attrs.collapsible
                        ? (isCollapsed ? '300px' : `${contentHeight}${typeof contentHeight === 'number' ? 'px' : ''}`)
                        : 'none',
                    overflow: 'hidden',
                    transition: 'max-height 0.5s cubic-bezier(0.4, 0, 0.2, 1)',
                    position: 'relative',
                    maskImage: isCollapsed ? 'linear-gradient(to bottom, black 60%, transparent 100%)' : 'none',
                    WebkitMaskImage: isCollapsed ? 'linear-gradient(to bottom, black 60%, transparent 100%)' : 'none',
                    display: 'flex',
                    alignItems: 'stretch'
                }}
            >
                {showLineNumbers && !wrapText && (
                    <div
                        className="flex-none p-5 text-right select-none bg-[#1a1a1a] border-r border-white/5 text-zinc-600 font-mono text-sm leading-relaxed"
                        style={{ minWidth: '3rem' }}
                        contentEditable={false}
                    >
                        {Array.from({ length: lineCount }).map((_, i) => (
                            <div key={i}>{i + 1}</div>
                        ))}
                    </div>
                )}
                <pre className={`flex-1 !m-0 !p-5 !bg-[#151515] ${wrapText ? 'whitespace-pre-wrap word-break-all' : 'overflow-x-auto'}`}>
                    <NodeViewContent as="code" className="font-mono text-sm text-zinc-300 leading-relaxed block" />
                </pre>
            </div>
        </NodeViewWrapper>
    );
};
