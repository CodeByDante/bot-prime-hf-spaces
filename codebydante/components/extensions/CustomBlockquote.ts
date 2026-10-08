import { Blockquote } from '@tiptap/extension-blockquote';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { QuoteComponent } from '../QuoteComponent';

export interface CustomBlockquoteOptions {
    HTMLAttributes: Record<string, any>;
}

export const CustomBlockquote = Blockquote.extend<CustomBlockquoteOptions>({
    name: 'customBlockquote',

    addNodeView() {
        return ReactNodeViewRenderer(QuoteComponent);
    },

    addAttributes() {
        return {
            borderColor: {
                default: 'gray',
                parseHTML: (element) => element.style.borderLeftColor,
                renderHTML: (attributes) => {
                    if (!attributes.borderColor) {
                        return {};
                    }
                    return {
                        style: `border-left-color: ${attributes.borderColor}`,
                    };
                },
            },
            borderWidth: {
                default: '4px',
                parseHTML: (element) => element.style.borderLeftWidth,
                renderHTML: (attributes) => {
                    if (!attributes.borderWidth) return {};
                    return { style: `border-left-width: ${attributes.borderWidth}` };
                }
            },
            backgroundColor: {
                default: 'transparent',
                parseHTML: (element) => element.style.backgroundColor,
                renderHTML: (attributes) => {
                    if (!attributes.backgroundColor) {
                        return {};
                    }
                    return {
                        style: `background-color: ${attributes.backgroundColor}`,
                    };
                },
            },
            textColor: {
                default: 'inherit',
                parseHTML: (element) => element.style.color,
                renderHTML: (attributes) => {
                    if (!attributes.textColor) {
                        return {};
                    }
                    return {
                        style: `color: ${attributes.textColor}`,
                    };
                },
            },
            padding: {
                default: '4px',
                parseHTML: (element) => element.style.padding,
                renderHTML: (attributes) => {
                    if (!attributes.padding) return {};
                    return { style: `padding: ${attributes.padding}` };
                }
            },
            fontSize: {
                default: 'inherit',
                parseHTML: (element) => element.style.fontSize,
                renderHTML: (attributes) => {
                    if (!attributes.fontSize) return {};
                    return { style: `font-size: ${attributes.fontSize}` };
                }
            },
            borderRadius: {
                default: '0px',
                parseHTML: (element) => element.style.borderRadius,
                renderHTML: (attributes) => {
                    if (!attributes.borderRadius) return {};
                    return { style: `border-radius: ${attributes.borderRadius}` };
                }
            },
            width: {
                default: '100%',
                parseHTML: (element) => element.style.width,
                renderHTML: (attributes) => {
                    if (!attributes.width) return {};
                    return { style: `width: ${attributes.width}` };
                }
            },
            height: {
                default: 'auto',
                parseHTML: (element) => element.style.height,
                renderHTML: (attributes) => {
                    if (!attributes.height) return {};
                    return { style: `height: ${attributes.height}` };
                }
            },
            italic: {
                default: false,
                parseHTML: (element) => element.style.fontStyle === 'italic',
                renderHTML: (attributes) => {
                    if (!attributes.italic) return {};
                    return { style: `font-style: italic` };
                }
            },
            showCopyButton: {
                default: false,
                parseHTML: (element) => element.getAttribute('data-show-copy') === 'true',
                renderHTML: (attributes) => {
                    return { 'data-show-copy': attributes.showCopyButton };
                }
            },
            fontFamily: {
                default: 'inherit',
                parseHTML: (element) => element.style.fontFamily,
                renderHTML: (attributes) => {
                    if (!attributes.fontFamily) return {};
                    return { style: `font-family: ${attributes.fontFamily}` };
                }
            },
            isCodeFont: {
                default: false,
                parseHTML: (element) => element.getAttribute('data-is-code-font') === 'true',
                renderHTML: (attributes) => {
                    return { 'data-is-code-font': attributes.isCodeFont };
                }
            },
            showDownloadButton: {
                default: false,
                parseHTML: (element) => element.getAttribute('data-show-download') === 'true',
                renderHTML: (attributes) => {
                    return { 'data-show-download': attributes.showDownloadButton };
                }
            },
            collapsible: {
                default: true,
                parseHTML: (element) => element.getAttribute('data-collapsible') === 'true',
                renderHTML: (attributes) => {
                    return { 'data-collapsible': attributes.collapsible };
                }
            }
        };
    },

    renderHTML({ HTMLAttributes }) {
        // Merge all style attributes into a single style string to avoid multiple style attributes
        const styleParts: string[] = [];

        // Helper to extract style from HTMLAttributes if it exists as a separate property
        // (though renderHTML in addAttributes usually handles adding it to HTMLAttributes.style)
        // However, TipTap merges them. Let's ensure we have a clean style string.

        // Actually, TipTap's default renderHTML merges the attributes returned by individual renderHTML functions.
        // So we just need to return the tag.
        return ['blockquote', HTMLAttributes, 0];
    },
});
