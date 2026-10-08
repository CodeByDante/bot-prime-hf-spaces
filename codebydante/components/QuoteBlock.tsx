import React, { useState, useEffect } from 'react';
import { subscribeToStyleConfig, DEFAULT_QUOTE_STYLE, QuoteStyleConfig } from '../services/codeStyleService';
import { CopyButton } from './CopyButton';
import { Edit2 } from 'lucide-react';

interface QuoteBlockProps extends React.HTMLAttributes<HTMLElement> {
    children: React.ReactNode;
    'data-show-copy'?: string;
    isEditable?: boolean;
}

export const QuoteBlock: React.FC<QuoteBlockProps> = ({ children, style, isEditable, ...props }) => {
    const [quoteStyle, setQuoteStyle] = useState<QuoteStyleConfig>(DEFAULT_QUOTE_STYLE);
    const [quoteText, setQuoteText] = useState('');

    useEffect(() => {
        const unsubscribe = subscribeToStyleConfig((config) => {
            setQuoteStyle(config.quote);
        });
        return () => unsubscribe();
    }, []);

    useEffect(() => {
        let text = '';
        if (Array.isArray(children)) {
            text = children
                .map((child) => {
                    if (typeof child === 'string') return child;
                    if (React.isValidElement(child) && (child.props as any).children) {
                        return String((child.props as any).children);
                    }
                    return '';
                })
                .join('\n');
        } else if (typeof children === 'string') {
            text = children;
        }
        setQuoteText(text);
    }, [children]);

    // Merge global styles with inline styles (inline takes precedence)
    const containerStyle: React.CSSProperties = {
        backgroundColor: quoteStyle.bgColor,
        color: quoteStyle.textColor,
        borderLeft: `${quoteStyle.borderWidth} solid ${quoteStyle.borderColor}`,
        padding: quoteStyle.padding,
        fontSize: quoteStyle.fontSize,
        borderRadius: quoteStyle.borderRadius,
        fontStyle: quoteStyle.italic ? 'italic' : 'normal',
        width: (quoteStyle.width !== 'auto' && quoteStyle.width) ? quoteStyle.width : '100%',
        height: quoteStyle.height !== 'auto' ? quoteStyle.height : undefined,
        minHeight: 0,
        overflow: 'visible',
        position: 'relative',
        maxWidth: '100%',
        boxSizing: 'border-box',
        marginBottom: '1rem',
        transition: 'all 0.2s ease-in-out',
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        ...style, // Override with inline styles
    };

    // Ensure inline style width is also respected or defaults to 100% if auto/undefined
    if (containerStyle.width === 'auto' || !containerStyle.width) {
        containerStyle.width = '100%';
    }

    const showCopyButton = props['data-show-copy'] === 'true' || (props['data-show-copy'] === undefined && quoteStyle.showCopyButton);

    const heightVal = style?.height || quoteStyle.height;
    const isSmallHeight = heightVal !== 'auto' && parseInt(String(heightVal)) < 40;
    const buttonPosition = isSmallHeight ? 'top-1/2 -translate-y-1/2' : 'top-2';

    return (
        <div className="relative group mb-4">
            <blockquote style={containerStyle} className="quote-block" {...props}>
                {children}
            </blockquote>
            <div className={`absolute right-2 flex gap-2 transition-opacity duration-200 ${isSmallHeight ? 'top-1/2 -translate-y-1/2' : 'top-2'} opacity-0 group-hover:opacity-100`}>
                {showCopyButton && (
                    <CopyButton
                        text={quoteText}
                        className=""
                    />
                )}
            </div>
        </div>
    );
};
