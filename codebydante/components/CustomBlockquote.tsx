import React from 'react';
import { CopyButton } from './CopyButton';
import { DownloadButton } from './DownloadButton';

interface CustomBlockquoteProps extends React.HTMLAttributes<HTMLQuoteElement> {
    isEditable?: boolean;
    'data-show-copy'?: string | boolean;
    'data-show-download'?: string | boolean;
}

export const CustomBlockquote: React.FC<CustomBlockquoteProps> = ({
    children,
    style,
    className = '',
    isEditable,
    'data-show-copy': showCopyData,
    'data-show-download': showDownloadData,
    ...props
}) => {
    // Extract text content for copy button
    const getTextContent = (node: React.ReactNode): string => {
        if (typeof node === 'string') return node;
        if (Array.isArray(node)) return node.map(getTextContent).join('');
        if (React.isValidElement(node)) return getTextContent((node as React.ReactElement<any>).props.children);
        return '';
    };

    const quoteText = getTextContent(children);
    const showCopyButton = showCopyData === 'true' || showCopyData === true;
    const showDownloadButton = showDownloadData === 'true' || showDownloadData === true;

    // Ensure we have default styles if not provided, but respect overrides
    const computedStyle: React.CSSProperties = {
        position: 'relative',
        marginBottom: '1rem',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        overflow: 'visible',
        maxWidth: '100%',
        boxSizing: 'border-box',
        ...style, // Allow style prop to override defaults
    };

    // Handle width specifically to ensure it doesn't break layout
    if (computedStyle.width === 'auto' || !computedStyle.width) {
        computedStyle.width = '100%';
    }

    return (
        <div className="relative group w-full max-w-full">
            <blockquote
                className={`transition-all duration-200 ease-in-out ${className}`}
                style={computedStyle}
                {...props}
            >
                {children}
            </blockquote>

            <div className="absolute right-2 top-2 flex gap-2 transition-opacity duration-200 opacity-0 group-hover:opacity-100 z-10">
                {showCopyButton && (
                    <CopyButton
                        text={quoteText}
                        className=""
                    />
                )}
                {showDownloadButton && (
                    <DownloadButton
                        text={quoteText}
                        className=""
                    />
                )}
            </div>
        </div>
    );
};
