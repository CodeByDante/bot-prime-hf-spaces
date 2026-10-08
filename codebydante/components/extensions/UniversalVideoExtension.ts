import { Node, mergeAttributes, PasteRule } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { ResizableVideoComponent } from './ResizableVideoComponent';

export const UniversalVideoExtension = Node.create({
    name: 'universalVideo',

    group: 'block',

    atom: true,

    addAttributes() {
        return {
            src: {
                default: null,
                parseHTML: element => element.getAttribute('data-src'),
                renderHTML: attributes => ({
                    'data-src': attributes.src,
                }),
            },
            width: {
                default: '100%',
                parseHTML: element => element.getAttribute('data-width') || element.style.width,
                renderHTML: (attributes) => ({
                    'data-width': attributes.width,
                    style: `width: ${attributes.width}`,
                }),
            },
            align: {
                default: 'center',
                parseHTML: element => element.getAttribute('data-align'),
                renderHTML: (attributes) => ({
                    'data-align': attributes.align,
                    style: `float: ${attributes.align === 'left' ? 'left' : attributes.align === 'right' ? 'right' : 'none'}; display: ${attributes.align === 'center' ? 'block' : 'inline-block'}; margin: ${attributes.align === 'center' ? '0 auto' : '0 1rem 0.5rem 0'}`,
                }),
            },
        };
    },

    parseHTML() {
        return [
            {
                tag: 'div[data-type="universal-video"]',
            },
        ];
    },

    renderHTML({ HTMLAttributes }) {
        return ['div', mergeAttributes(HTMLAttributes, { 'data-type': 'universal-video' })];
    },

    addNodeView() {
        return ReactNodeViewRenderer(ResizableVideoComponent);
    },

    addPasteRules() {
        return [
            new PasteRule({
                find: /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/g,
                handler: ({ state, range, match }) => {
                    const url = match[0];
                    let finalUrl = url;
                    if (!finalUrl.match(/^https?:\/\//)) {
                        finalUrl = `https://${finalUrl}`;
                    }

                    state.tr.replaceWith(range.from, range.to, this.type.create({ src: finalUrl }));
                },
            }),
        ];
    },
});
