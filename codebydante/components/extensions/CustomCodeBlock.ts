import { CodeBlock } from '@tiptap/extension-code-block';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { CodeBlockComponent } from '../CodeBlockComponent';

export const CustomCodeBlock = CodeBlock.extend({
    addNodeView() {
        return ReactNodeViewRenderer(CodeBlockComponent);
    },
    addAttributes() {
        return {
            language: {
                default: null,
            },
            filename: {
                default: null,
            },
            collapsible: {
                default: true,
                parseHTML: (element) => element.getAttribute('data-collapsible') !== 'false',
                renderHTML: (attributes) => {
                    return {
                        'data-collapsible': attributes.collapsible,
                    };
                },
            },
            showLineNumbers: {
                default: false,
                parseHTML: (element) => element.getAttribute('data-show-line-numbers') === 'true',
                renderHTML: (attributes) => {
                    return {
                        'data-show-line-numbers': attributes.showLineNumbers,
                    };
                },
            },
            wrapText: {
                default: false,
                parseHTML: (element) => element.getAttribute('data-wrap-text') === 'true',
                renderHTML: (attributes) => {
                    return {
                        'data-wrap-text': attributes.wrapText,
                    };
                },
            }
        };
    },
    content: 'text*',
    marks: '',
});
