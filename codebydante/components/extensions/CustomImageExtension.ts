
import Image from '@tiptap/extension-image';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { ResizableImageComponent } from './ResizableImageComponent';

export const CustomImageExtension = Image.extend({
    addAttributes() {
        return {
            ...this.parent?.(),
            width: {
                default: '100%',
                renderHTML: (attributes) => ({
                    width: attributes.width,
                }),
            },
            height: {
                default: 'auto',
                renderHTML: (attributes) => ({
                    height: attributes.height,
                }),
            },
            align: {
                default: 'center',
                renderHTML: (attributes) => ({
                    'data-align': attributes.align,
                    style: `float: ${attributes.align === 'left' ? 'left' : attributes.align === 'right' ? 'right' : 'none'}; display: ${attributes.align === 'center' ? 'block' : 'inline-block'}; margin: ${attributes.align === 'center' ? '0 auto' : '0 1rem 0.5rem 0'}`,
                }),
            },
            href: {
                default: null,
            },
            target: {
                default: '_blank',
            },
        };
    },

    addNodeView() {
        return ReactNodeViewRenderer(ResizableImageComponent);
    },
});
