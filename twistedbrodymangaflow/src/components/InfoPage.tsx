import { ArrowLeft, Info, Edit2, Save, X } from 'lucide-react';
import { useState, useEffect } from 'react';
import { subscribeToInfo, saveInfo } from '../services/info';
import ReactMarkdown from 'react-markdown';

interface InfoPageProps {
    onBack: () => void;
    isAdmin: boolean;
}

export function InfoPage({ onBack, isAdmin }: InfoPageProps) {
    const [content, setContent] = useState('');
    const [isEditing, setIsEditing] = useState(false);
    const [editContent, setEditContent] = useState('');
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = subscribeToInfo((data) => {
            if (data) {
                setContent(data.content);
            }
            setIsLoading(false);
        });
        return () => unsubscribe();
    }, []);

    const handleSave = async () => {
        try {
            await saveInfo(editContent);
            setIsEditing(false);
        } catch (error) {
            console.error('Error saving info:', error);
            alert('Error al guardar la información.');
        }
    };

    const startEditing = () => {
        setEditContent(content);
        setIsEditing(true);
    };

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white p-4 sm:p-6 md:p-12 animate-in fade-in slide-in-from-bottom-4 duration-300">
            <div className="max-w-4xl mx-auto">
                <button
                    onClick={onBack}
                    className="flex items-center gap-2 text-gray-400 hover:text-white transition-colors mb-8 group"
                >
                    <ArrowLeft className="w-5 h-5 group-hover:-translate-x-1 transition-transform" />
                    <span className="font-medium">Volver al inicio</span>
                </button>

                <div className="bg-[#1a1a1a] rounded-2xl border border-gray-800 p-8 sm:p-12 shadow-2xl relative">

                    {isAdmin && !isEditing && (
                        <button
                            onClick={startEditing}
                            className="absolute top-8 right-8 p-2 rounded-lg bg-gray-800 text-gray-400 hover:text-[#bb86fc] hover:bg-[#bb86fc]/10 transition-colors"
                            title="Editar información"
                        >
                            <Edit2 className="w-5 h-5" />
                        </button>
                    )}

                    <div className="flex items-center gap-4 mb-8 border-b border-gray-800 pb-8">
                        <div className="p-3 bg-gradient-to-br from-[#bb86fc] to-[#9966dd] rounded-xl shadow-lg shadow-[#bb86fc]/20">
                            <Info className="w-8 h-8 text-white" />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-gray-400 bg-clip-text text-transparent">
                                Información
                            </h1>
                            <p className="text-gray-400 mt-1">
                                Sobre Twisted Brody MangaFlow
                            </p>
                        </div>
                    </div>

                    {isEditing ? (
                        <div className="space-y-4">
                            <textarea
                                value={editContent}
                                onChange={(e) => setEditContent(e.target.value)}
                                className="w-full h-[500px] bg-black/50 border border-[#bb86fc]/50 rounded-lg p-4 text-sm text-white focus:outline-none focus:border-[#bb86fc] font-mono"
                                placeholder="Escribe el contenido en Markdown..."
                            />
                            <div className="flex gap-3 justify-end">
                                <button
                                    onClick={() => setIsEditing(false)}
                                    className="px-4 py-2 rounded-lg font-semibold text-gray-400 hover:text-white hover:bg-white/10 transition-colors flex items-center gap-2"
                                >
                                    <X className="w-4 h-4" />
                                    Cancelar
                                </button>
                                <button
                                    onClick={handleSave}
                                    className="px-4 py-2 rounded-lg font-semibold bg-[#bb86fc] hover:bg-[#9966dd] text-white transition-colors shadow-lg shadow-[#bb86fc]/20 flex items-center gap-2"
                                >
                                    <Save className="w-4 h-4" />
                                    Guardar Cambios
                                </button>
                            </div>
                        </div>
                    ) : (
                        <div className="prose prose-invert prose-p:text-gray-300 prose-headings:text-white prose-a:no-underline max-w-none">
                            <ReactMarkdown
                                components={{
                                    h1: ({ node, ...props }) => (
                                        <h1 className="text-3xl font-bold bg-gradient-to-r from-[#bb86fc] to-[#7744cc] bg-clip-text text-transparent mb-6 pb-2 border-b border-gray-800" {...props} />
                                    ),
                                    h2: ({ node, ...props }) => (
                                        <h2 className="text-xl font-semibold text-white mt-8 mb-4 flex items-center gap-2" {...props} />
                                    ),
                                    p: ({ node, ...props }) => (
                                        <p className="text-gray-300 leading-relaxed mb-4" {...props} />
                                    ),
                                    ul: ({ node, ...props }) => (
                                        <ul className="space-y-2 mb-6" {...props} />
                                    ),
                                    li: ({ node, ...props }) => (
                                        <li className="flex items-start gap-2 text-gray-300" {...props} />
                                    ),
                                    a: ({ node, href, children, ...props }) => {
                                        const isExternal = href?.startsWith('http');
                                        const isButton = href?.includes('t.me') || href?.includes('patreon.com') || href?.includes('x.com');

                                        if (isButton) {
                                            let bgClass = "bg-[#1a1a1a] border border-gray-700 hover:border-gray-500";
                                            let textClass = "text-gray-300 hover:text-white";

                                            if (href?.includes('patreon')) bgClass = "bg-[#1a1a1a] border border-gray-700 hover:border-[#FF424D] hover:text-[#FF424D]";
                                            if (href?.includes('t.me')) bgClass = "bg-[#1a1a1a] border border-gray-700 hover:border-[#24A1DE] hover:text-[#24A1DE]";
                                            if (href?.includes('x.com')) bgClass = "bg-[#1a1a1a] border border-gray-700 hover:border-white hover:text-white";

                                            return (
                                                <a
                                                    href={href}
                                                    target={isExternal ? "_blank" : undefined}
                                                    rel={isExternal ? "noopener noreferrer" : undefined}
                                                    className={`inline-flex items-center gap-2 px-3 py-1.5 rounded-lg transition-all transform hover:scale-105 shadow-sm my-1 mr-2 no-underline text-xs sm:text-sm font-medium ${bgClass} ${textClass}`}
                                                    {...props}
                                                >
                                                    {children}
                                                </a>
                                            );
                                        }

                                        return (
                                            <a
                                                href={href}
                                                className="text-[#bb86fc] hover:underline"
                                                target={isExternal ? "_blank" : undefined}
                                                rel={isExternal ? "noopener noreferrer" : undefined}
                                                {...props}
                                            >
                                                {children}
                                            </a>
                                        );
                                    },
                                    blockquote: ({ node, ...props }) => (
                                        <blockquote className="border-l-4 border-[#bb86fc] pl-4 py-2 bg-[#bb86fc]/10 rounded-r-lg italic text-gray-400 my-6" {...props} />
                                    ),
                                    hr: ({ node, ...props }) => (
                                        <hr className="border-gray-800 my-8" {...props} />
                                    ),
                                    img: () => null
                                }}
                            >
                                {content}
                            </ReactMarkdown>
                        </div>
                    )}

                    {!isEditing && (
                        <div className="pt-8 border-t border-gray-800 text-center text-sm text-gray-500 mt-8">
                            &copy; {new Date().getFullYear()} Twisted Brody. Todos los derechos reservados.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
