import React, { useEffect, useState } from 'react';
import { useEditor, EditorContent, Editor, mergeAttributes, Extension } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Heading from '@tiptap/extension-heading';
import Link from '@tiptap/extension-link';
import TextAlign from '@tiptap/extension-text-align';
import Code from '@tiptap/extension-code';
import HorizontalRule from '@tiptap/extension-horizontal-rule';
import { CustomBlockquote } from './extensions/CustomBlockquote';
import { CustomImageExtension } from './extensions/CustomImageExtension';
import { UniversalVideoExtension } from './extensions/UniversalVideoExtension';
import { CustomCodeBlock } from './extensions/CustomCodeBlock';
import { CustomButton } from './extensions/CustomButton';
import { CustomFileExtension } from './extensions/CustomFileExtension';
import { WordBehaviorExtension } from './extensions/WordBehaviorExtension';
import { EditorToolbar } from './EditorToolbar';
import { StyleSettingsPanel } from './StyleSettingsPanel';
import { EditorSelectionWrapper } from './EditorSelectionWrapper';
import { QuoteStyleConfig, DEFAULT_QUOTE_STYLE, DEFAULT_CODE_STYLE, StyleConfig, saveStyleConfigToCloud, DEFAULT_STYLE_CONFIG, subscribeToStyleConfig } from '../services/codeStyleService';

interface TipTapEditorProps {
    content: any; // JSON content or string (for initial load)
    onUpdate: (content: any) => void; // Returns JSON
    isEditable?: boolean;
    editorRef?: React.MutableRefObject<Editor | null>;
    onBlockDoubleClick?: (type: 'code' | 'quote', index: number) => void;
    onSave?: () => void;
    autoFocus?: boolean;
    showToolbarOnFocus?: boolean;
    className?: string;
    extensions?: Extension[];
    dense?: boolean;
    minimalMode?: boolean;
    cardStyle?: 'bordered' | 'transparent' | 'filled';
    onCardStyleChange?: (style: 'bordered' | 'transparent' | 'filled') => void;
}

export const TipTapEditor: React.FC<TipTapEditorProps> = ({
    content,
    onUpdate,
    isEditable = true,
    editorRef,
    onBlockDoubleClick,
    onSave,
    autoFocus = false,
    showToolbarOnFocus = false,
    className = '',
    extensions = [],
    dense = false,
    minimalMode = false,
    cardStyle,
    onCardStyleChange
}) => {
    // Custom extension to handle ArrowDown at the end of the document
    const ArrowDownHandler = Extension.create({
        name: 'arrowDownHandler',
        addKeyboardShortcuts() {
            return {
                ArrowDown: () => {
                    const { state, commands } = this.editor;
                    const { selection, doc } = state;
                    const { empty, $head } = selection;

                    // Check if we are at the end of the document
                    // The document size includes the opening and closing tags of the doc itself.
                    // The last valid cursor position inside the last block is usually doc.content.size - 1
                    if (empty && $head.pos === doc.content.size - 1) {
                        return commands.insertContent('<p></p>');
                    }
                    return false;
                },
            };
        },
    });

    const [styleConfig, setStyleConfig] = useState<StyleConfig>(DEFAULT_STYLE_CONFIG);
    const [activeTab, setActiveTab] = useState<'code' | 'quote' | 'link' | 'general' | 'button' | 'codeblock'>('quote');
    const [isSettingsOpen, setIsSettingsOpen] = useState(false);
    const [editingBlockIndex, setEditingBlockIndex] = useState<number | null>(null);
    const [isFocused, setIsFocused] = useState(false);
    const [toolbarVisible, setToolbarVisible] = useState(!showToolbarOnFocus);
    // contextMenuPos state removed as context menu is disabled

    useEffect(() => {
        if (!showToolbarOnFocus) {
            setToolbarVisible(true);
        }
    }, [showToolbarOnFocus]);

    useEffect(() => {
        if (showToolbarOnFocus) {
            if (isFocused) {
                setToolbarVisible(true);
            } else {
                setToolbarVisible(false);
            }
        }
    }, [isFocused, showToolbarOnFocus]);

    const handleFocus = () => {
        setIsFocused(true);
        if (showToolbarOnFocus) setToolbarVisible(true);
    };

    const handleBlur = (e: React.FocusEvent) => {
        // Check if the new focus is still within the editor container
        const currentTarget = e.currentTarget;

        // Give a small timeout to allow focus to settle (e.g. clicking a button)
        requestAnimationFrame(() => {
            if (!currentTarget.contains(document.activeElement)) {
                setIsFocused(false);
                if (showToolbarOnFocus) setToolbarVisible(false);
            }
        });
    };



    // Close context menu on click anywhere

    const editor = useEditor({

        extensions: [
            StarterKit.configure({
                heading: false, // Disable default heading to use custom configuration
                code: false, // Disable default code to use custom configuration
                codeBlock: false, // Disable default codeBlock to use custom configuration
                horizontalRule: false, // Disable default horizontalRule to use custom configuration
                blockquote: false, // Disable default blockquote to use custom configuration
                strike: false, // Disable strike as it causes unwanted strikethrough on pasted syntax highlighter code
            }),
            Heading.configure({
                levels: [1, 2, 3],
            }).extend({
                renderHTML({ node, HTMLAttributes }) {
                    const level = node.attrs.level;
                    const classes: Record<number, string> = {
                        1: 'text-4xl font-bold text-white m-0 mb-2 leading-none',
                        2: 'text-2xl font-semibold text-zinc-100 m-0 mb-2 leading-tight',
                        3: 'text-xl font-medium text-zinc-200 m-0 mb-1',
                    };
                    return [`h${level}`, mergeAttributes(this.options.HTMLAttributes, HTMLAttributes, { class: classes[level] }), 0];
                },
            }),
            CustomBlockquote,
            CustomCodeBlock,
            Link.configure({
                openOnClick: false,
                HTMLAttributes: {
                    class: 'text-primary underline cursor-pointer hover:text-primary/80',
                },
            }),
            TextAlign.configure({
                types: ['heading', 'paragraph'],
            }),
            Code.extend({
                inclusive: false,
                addAttributes() {
                    return {
                        showBackground: {
                            default: true,
                            parseHTML: element => element.getAttribute('data-show-background') !== 'false',
                            renderHTML: attributes => {
                                if (!attributes.showBackground) {
                                    return {
                                        'data-show-background': 'false',
                                        style: 'background-color: transparent !important; color: inherit !important; padding: 0 !important;',
                                    };
                                }
                                return {
                                    'data-show-background': 'true',
                                };
                            },
                        },
                    };
                },
            }),
            CustomImageExtension,
            UniversalVideoExtension,
            CustomButton,
            CustomFileExtension,
            HorizontalRule.configure({
                HTMLAttributes: {
                    class: 'border-t border-white/10 my-8', // Reduced opacity
                },
            }),
            ArrowDownHandler,
            WordBehaviorExtension,
            ...extensions
        ],
        content: (typeof content === 'string' && !content.includes('<') && content.includes('\n')) ? content.replace(/\n/g, '<br>') : content,
        editable: isEditable,
        autofocus: autoFocus,
        onUpdate: ({ editor }) => {
            // Check if onUpdate expects an object or just the content
            // The interface says (content: any) => void
            // We'll pass both HTML and JSON if possible, but the signature usually expects one arg
            // If the consumer expects JSON, we pass JSON.
            // But for Title/Summary we want HTML.
            // Let's pass an object with both, OR check usage.
            // Existing usage: onUpdate(editor.getJSON())
            // We should change this to allow the parent to decide, or just pass the editor instance context?
            // "onUpdate" prop in DetailView expects "content: any".
            // I will change it to return `editor.getHTML()` if `showToolbarOnFocus` is true, otherwise `editor.getJSON()`.
            // This is a heuristic but matches the use case (Title/Summary = HTML string, Blocks = JSON).

            if (showToolbarOnFocus) {
                onUpdate(editor.getHTML());
            } else {
                onUpdate(editor.getJSON());
            }
        },
        editorProps: {
            handleDOMEvents: {
                // Context menu handler removed
            },
            attributes: {
                class: `prose prose-invert max-w-none focus:outline-none ${dense ? 'min-h-[40px]' : 'min-h-[50px]'} !h-auto prose-headings:font-bold prose-h1:text-3xl prose-h2:text-2xl prose-p:text-gray-300 prose-p:leading-relaxed prose-p:my-1 prose-blockquote:not-italic prose-pre:bg-[#000000] prose-pre:text-gray-300 prose-code:text-primary prose-code:rounded prose-code:px-1 prose-code:py-1 prose-code:leading-relaxed prose-code:decoration-clone prose-code:before:content-none prose-code:after:content-none prose-hr:border-white/10 ${className}`,
                style: `
                    --code-font-family: ${styleConfig.code.fontFamily};
                `
            },
        },
    });

    // Inject dynamic styles for code blocks
    useEffect(() => {
        if (!editor) return;

        const handleTripleClick = (e: any) => {
            const { type, pos } = e.detail;

            // Find the index of the block
            let index = 0;
            let found = false;
            let targetNode: any = null;

            editor.state.doc.descendants((n, p) => {
                if (found) return false;

                if (n.type.name === 'customBlockquote' && type === 'quote') {
                    if (p === pos) {
                        targetNode = n;
                        found = true;
                        return false;
                    }
                    index++;
                } else if (n.type.name === 'codeBlock' && type === 'code') {
                    if (p === pos) {
                        targetNode = n;
                        found = true;
                        return false;
                    }
                    index++;
                }
                return true;
            });

            if (found && targetNode) {
                // If it's a quote, open settings for this specific block
                if (type === 'quote') {
                    setEditingBlockIndex(pos); // Use pos as identifier for simplicity in this context, or index if we map it back
                    // Actually, let's use the node attributes to populate the settings panel
                    const nodeAttrs = targetNode.attrs;
                    const instanceConfig: StyleConfig = {
                        ...styleConfig,
                        quote: {
                            ...DEFAULT_QUOTE_STYLE,
                            ...nodeAttrs
                        }
                    };
                    // We need a way to pass this instance config to the panel without overwriting the global styleConfig state permanently
                    // But StyleSettingsPanel takes styleConfig as prop.
                    // We can use a temporary state or just pass it.
                    // Let's update the logic to open settings with this specific config.
                    // Wait, StyleSettingsPanel uses internal state initialized from prop.
                    // So if we pass a different config here, it should work.

                    // However, we need to know if we are in "instance edit" mode or "global edit" mode.
                    // We can use editingBlockIndex !== null to determine this.

                    // Let's set the styleConfig to this instance's config JUST for the panel
                    // But wait, styleConfig is used for global styles too (code font).
                    // If we overwrite it, we might lose global context.
                    // But here we are editing a quote.

                    // Let's try this:
                    // 1. Set editingBlockIndex to pos.
                    // 2. Open settings.
                    // 3. In the render, if editingBlockIndex is set, pass the instance config.
                    setIsSettingsOpen(true);
                    setActiveTab('quote');
                } else if (type === 'code') {
                    setEditingBlockIndex(pos);
                    setIsSettingsOpen(true);
                    setActiveTab('codeblock'); // Switch to codeblock tab
                } else if (onBlockDoubleClick) {
                    // Keep existing behavior for code blocks if needed, or handle similarly
                    onBlockDoubleClick('code', index);
                }
            }
        };

        editor.view.dom.addEventListener('block-triple-click', handleTripleClick);
        return () => {
            editor.view.dom.removeEventListener('block-triple-click', handleTripleClick);
        };
    }, [editor, onBlockDoubleClick, styleConfig]); // Added styleConfig dependency to ensure we have latest defaults

    useEffect(() => {
        if (editor) {
            editor.setEditable(isEditable);
        }
    }, [isEditable, editor]);

    useEffect(() => {
        if (editor && editorRef) {
            editorRef.current = editor;
        }
    }, [editor, editorRef]);

    // Update content if it changes externally (and is different)
    useEffect(() => {
        if (editor && content && JSON.stringify(editor.getJSON()) !== JSON.stringify(content)) {
            // Specialized content set for HTML string vs JSON
            if (typeof content === 'string') {
                let processedContent = content;
                if (!processedContent.includes('<') && processedContent.includes('\n')) {
                    processedContent = processedContent.replace(/\n/g, '<br>');
                }

                if (editor.getHTML() !== processedContent) {
                    editor.commands.setContent(processedContent);
                }
            } else {
                editor.commands.setContent(content);
            }
        }
    }, [content, editor]);

    // Subscribe to style config changes
    useEffect(() => {
        const unsubscribe = subscribeToStyleConfig((config) => {
            setStyleConfig(config);
        });
        return () => unsubscribe();
    }, []);

    if (!editor) {
        return null;
    }

    // Determine the config to pass to the panel
    const getSettingsPanelConfig = (): StyleConfig => {
        if (editingBlockIndex !== null) {
            // Find the node at editingBlockIndex
            let targetNode: any = null;
            editor.state.doc.descendants((n, p) => {
                if (p === editingBlockIndex) {
                    targetNode = n;
                    return false;
                }
                return true;
            });

            if (targetNode && targetNode.type.name === 'customBlockquote') {
                return {
                    ...styleConfig,
                    quote: {
                        ...DEFAULT_QUOTE_STYLE,
                        ...targetNode.attrs
                    }
                };
            }

            if (targetNode && targetNode.type.name === 'codeBlock') {
                return {
                    ...styleConfig,
                    code: {
                        ...DEFAULT_CODE_STYLE,
                        ...targetNode.attrs
                    }
                };
            }
        }
        return styleConfig;
    };

    return (
        <div
            className={`tiptap-editor-container w-full flex flex-col relative h-auto ${className}`}
            onFocus={handleFocus}
            onBlur={handleBlur}

        >
            <div className={`transition-opacity duration-200 ${isEditable && toolbarVisible ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'}`}>
                <EditorToolbar
                    editor={editor}
                    minimalMode={minimalMode}
                    defaultQuoteStyles={styleConfig.quote}
                    codeStyleConfig={styleConfig.code}
                    linkStyleConfig={styleConfig.link}
                    buttonStyleConfig={styleConfig.button}
                    onOpenSettings={() => {
                        setEditingBlockIndex(null); // Reset to global mode
                        setIsSettingsOpen(true);
                    }}
                    onSave={onSave}
                />
            </div>
            <div
                className={`h-auto ${dense ? 'pb-0' : 'pb-24'} text-zinc-100 cursor-text flex flex-col items-start`}
            >
                <EditorSelectionWrapper
                    editor={editor}
                    onBackgroundClick={() => {
                        editor?.chain().focus('end').run();
                    }}
                >
                    <EditorContent editor={editor} className="h-auto min-h-[40px]" />
                </EditorSelectionWrapper>
            </div>



            {isSettingsOpen && (
                <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 p-4">
                    <div className="bg-[#1e1e1e] rounded-xl shadow-2xl w-full max-w-2xl h-[85vh] flex flex-col overflow-hidden border border-white/10">
                        <StyleSettingsPanel
                            styleConfig={getSettingsPanelConfig()}
                            onUpdateConfig={(newConfig) => {
                                // Only update local state for preview/interaction
                                // Actual save happens on confirm or debounce if we implemented it
                                setStyleConfig(newConfig);
                            }}
                            activeTab={activeTab}
                            onTabChange={setActiveTab}
                            onClose={() => {
                                setIsSettingsOpen(false);
                                setEditingBlockIndex(null);
                            }}
                            onConfirm={async (config) => {
                                if (editingBlockIndex !== null) {
                                    // Instance Edit Mode: Update ONLY the specific block
                                    if (editor) {
                                        editor.chain().focus().command(({ tr }) => {
                                            const node = editor.state.doc.nodeAt(editingBlockIndex);
                                            if (node && node.type.name === 'customBlockquote') {
                                                tr.setNodeMarkup(editingBlockIndex, undefined, {
                                                    ...config.quote,
                                                    backgroundColor: config.quote.bgColor
                                                });
                                            } else if (node && node.type.name === 'codeBlock') {
                                                tr.setNodeMarkup(editingBlockIndex, undefined, {
                                                    ...node.attrs,
                                                    collapsible: config.code.collapsible,
                                                    showBackground: config.code.showBackground,
                                                    showLineNumbers: config.code.showLineNumbers,
                                                    wrapText: config.code.wrapText
                                                });
                                            }
                                            return true;
                                        }).run();
                                    }
                                    setEditingBlockIndex(null);
                                } else {
                                    // Global Edit Mode: Save to cloud ONLY. Do NOT update existing blocks.
                                    try {
                                        await saveStyleConfigToCloud(config);

                                        // Update local state
                                        setStyleConfig(config);

                                        // Propagate changes to all existing customBlockquote nodes
                                        if (editor) {
                                            editor.chain().focus().command(({ tr, state }) => {
                                                state.doc.descendants((node, pos) => {
                                                    if (node.type.name === 'customBlockquote') {
                                                        tr.setNodeMarkup(pos, undefined, {
                                                            ...node.attrs,
                                                            showDownloadButton: config.quote.showDownloadButton,
                                                            showCopyButton: config.quote.showCopyButton
                                                        });
                                                    }
                                                    return true;
                                                });
                                                return true;
                                            }).run();
                                        }
                                    } catch (error) {
                                        console.error('Error saving style config:', error);
                                    }
                                }
                                setIsSettingsOpen(false);
                            }}
                            hideTabs={false}
                            previewContent="Este es un ejemplo de cómo se verán tus citas con la configuración actual."
                            cardStyle={cardStyle}
                            onCardStyleChange={onCardStyleChange}
                        />
                    </div>
                </div>
            )}
        </div>
    );
};
