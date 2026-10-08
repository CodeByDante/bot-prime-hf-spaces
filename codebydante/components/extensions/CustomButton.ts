import { Node, mergeAttributes } from '@tiptap/core';
import { ReactNodeViewRenderer } from '@tiptap/react';
import { CustomButtonComponent } from '../CustomButtonComponent';

export interface CustomButtonOptions {
    HTMLAttributes: Record<string, any>;
}

declare module '@tiptap/core' {
    interface Commands<ReturnType> {
        customButton: {
            setCustomButton: (options: { text: string; url: string; variant: 'visit' | 'download' } & Record<string, any>) => ReturnType;
        };
    }
}

export const CustomButton = Node.create<CustomButtonOptions>({
    name: 'customButton',

    group: 'inline',

    inline: true,

    atom: true,

    addAttributes() {
        return {
            text: {
                default: 'Button',
                parseHTML: element => element.textContent,
                // We handle text content in the main renderHTML
            },
            url: {
                default: '#',
                parseHTML: element => element.getAttribute('href'),
                renderHTML: attributes => ({
                    href: attributes.url,
                }),
            },
            variant: {
                default: 'visit',
                parseHTML: element => element.getAttribute('data-variant'),
                renderHTML: attributes => ({
                    'data-variant': attributes.variant,
                }),
            },
            backgroundColor: {
                default: null,
                parseHTML: element => element.getAttribute('data-background-color'),
                renderHTML: attributes => ({
                    'data-background-color': attributes.backgroundColor,
                }),
            },
            textColor: {
                default: null,
                parseHTML: element => element.getAttribute('data-text-color'),
                renderHTML: attributes => ({
                    'data-text-color': attributes.textColor,
                }),
            },
            borderRadius: {
                default: null,
                parseHTML: element => element.getAttribute('data-border-radius'),
                renderHTML: attributes => ({
                    'data-border-radius': attributes.borderRadius,
                }),
            },
            width: {
                default: null,
                parseHTML: element => element.getAttribute('data-width'),
                renderHTML: attributes => ({
                    'data-width': attributes.width,
                }),
            },
            height: {
                default: null,
                parseHTML: element => element.getAttribute('data-height'),
                renderHTML: attributes => ({
                    'data-height': attributes.height,
                }),
            },
        };
    },

    parseHTML() {
        return [
            {
                tag: 'a[data-type="custom-button"]',
                priority: 10000,
                getAttrs: (element) => {
                    if (element instanceof HTMLElement && element.getAttribute('data-type') === 'custom-button') {
                        return {};
                    }
                    return false;
                },
            },
        ];
    },

    renderHTML({ node, HTMLAttributes }) {
        const { text, url, variant, backgroundColor, textColor, borderRadius, width, height } = node.attrs;
        const defaultBg = '#bb86fc';
        const defaultText = '#ffffff';

        const activeBg = backgroundColor || defaultBg;
        const activeText = textColor || defaultText;

        const styles = {
            width: width || 'auto',
            height: height || 'auto',
            'max-width': '100%',
            'background-color': 'transparent',
            color: activeBg, // Main color for icon/border
            'border-radius': borderRadius || '8px',
            border: `1px solid ${activeBg}`,
            'box-shadow': `0 0 10px ${activeBg}40`,
            'text-decoration': 'none',
            'vertical-align': 'middle',
        };

        const styleString = Object.entries(styles)
            .map(([key, value]) => `${key}: ${value}`)
            .join('; ');

        // Start with the generic logic for icons
        const getIconChildren = (v: string) => {
            switch (v) {
                case 'download':
                    // <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" x2="12" y1="15" y2="3"/>
                    return [
                        ['path', { d: 'M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' }],
                        ['polyline', { points: '7 10 12 15 17 10' }],
                        ['line', { x1: '12', x2: '12', y1: '15', y2: '3' }]
                    ];
                case 'visit':
                default:
                    // <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" x2="21" y1="14" y2="3"/>
                    return [
                        ['path', { d: 'M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6' }],
                        ['polyline', { points: '15 3 21 3 21 9' }],
                        ['line', { x1: '10', x2: '21', y1: '14', y2: '3' }]
                    ];
            }
        };

        return [
            'a',
            mergeAttributes(HTMLAttributes, {
                'data-type': 'custom-button',
                class: 'inline-flex items-center justify-center gap-2 px-4 py-2 border transition-all duration-200 no-underline cursor-pointer hover:opacity-90 mx-1 align-middle',
                style: styleString,
                href: url || '#',
                target: '_blank',
                rel: 'noopener noreferrer'
            }),
            [
                'svg',
                {
                    xmlns: 'http://www.w3.org/2000/svg',
                    width: '16',
                    height: '16',
                    viewBox: '0 0 24 24',
                    fill: 'none',
                    stroke: activeBg,
                    'stroke-width': '2',
                    'stroke-linecap': 'round',
                    'stroke-linejoin': 'round',
                },
                ...getIconChildren(variant || 'visit')
            ],
            [
                'span',
                {
                    class: 'font-medium text-sm',
                    style: `color: ${activeText}`
                },
                text || 'Button'
            ]
        ];
    },

    addNodeView() {
        return ReactNodeViewRenderer(CustomButtonComponent);
    },

    addCommands() {
        return {
            setCustomButton:
                (options) =>
                    ({ commands }) => {
                        return commands.insertContent({
                            type: this.name,
                            attrs: options,
                        });
                    },
        };
    },
});
