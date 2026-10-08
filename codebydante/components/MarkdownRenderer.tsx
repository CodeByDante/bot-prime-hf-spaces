import React, { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkAlert from 'remark-github-blockquote-alert';
import rehypeRaw from 'rehype-raw';
import { Copy, Check } from 'lucide-react';
import { subscribeToStyleConfig } from '../services/codeStyleService';
import { CopyButton } from './CopyButton';
import { CustomBlockquote } from './CustomBlockquote';
import 'github-markdown-css/github-markdown-dark.css';
import 'remark-github-blockquote-alert/alert.css';

interface MarkdownRendererProps {
  content: string;
  onBlockDoubleClick?: (type: 'code' | 'quote', index: number) => void;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, onBlockDoubleClick }) => {
  const [showCopyButton, setShowCopyButton] = useState(false);
  const [copied, setCopied] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const unsubscribe = subscribeToStyleConfig((config) => {
      setShowCopyButton(config.showCopyButton);
    });
    return () => unsubscribe();
  }, []);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleBlockDoubleClick = (e: React.MouseEvent, type: 'code' | 'quote') => {
    if (!onBlockDoubleClick || !containerRef.current) return;

    e.stopPropagation(); // Prevent bubbling

    const wrapper = e.currentTarget as HTMLElement;
    const selector = type === 'quote' ? 'blockquote' : 'pre';
    const block = wrapper.querySelector(selector);

    if (!block) return;

    const allBlocks = Array.from(containerRef.current.querySelectorAll(selector));
    const index = allBlocks.indexOf(block as any);

    if (index !== -1) {
      onBlockDoubleClick(type, index);
    }
  };

  return (
    <div ref={containerRef} className="markdown-body bg-transparent relative group" style={{ backgroundColor: 'transparent' }}>
      {showCopyButton && (
        <button
          onClick={handleCopy}
          className="absolute -top-2 -right-2 p-2 bg-surface border border-white/10 rounded-lg opacity-0 group-hover:opacity-100 transition-opacity hover:bg-primary hover:text-background z-10"
          title="Copiar contenido"
        >
          {copied ? <Check size={16} /> : <Copy size={16} />}
        </button>
      )}
      <style>{`
        .markdown-body table tr {
          background-color: transparent !important;
        }
        .markdown-body table tr:nth-child(2n) {
          background-color: rgba(255,255,255,0.02) !important;
        }
      `}</style>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkAlert]}
        rehypePlugins={[rehypeRaw]}
        components={{
          div: ({ align, children, className, style, ...props }: any) => {
            const isCenter = align === 'center';
            return (
              <div 
                className={`${className || ''} ${isCenter ? 'flex flex-col items-center text-center' : ''}`}
                style={style}
                {...props}
              >
                {children}
              </div>
            );
          },
          blockquote: ({ children, ...props }) => (
            <div
              onDoubleClick={(e) => handleBlockDoubleClick(e, 'quote')}
            >
              <CustomBlockquote isEditable={!!onBlockDoubleClick} {...props}>{children}</CustomBlockquote>
            </div>
          ),
          code: ({ inline, children, className, style, ...props }: any) => {
            const codeString = String(children).replace(/\n$/, '');

            if (inline) {
              return (
                <code className={className} style={style} {...props}>
                  {children}
                </code>
              );
            }

            return (
              <code className="text-gray-300 font-mono text-sm leading-relaxed">
                {codeString.split('\n').map((line, i) => {
                  const highlighted = line
                    .replace(/(\b(?:const|let|var|function|return|if|else|for|while|class|import|export|from|default|async|await|try|catch|throw|new)\b)/g, '<span class="text-[#569cd6]">$1</span>')
                    .replace(/(['"`].*?['"`])/g, '<span class="text-[#ce9178]">$1</span>')
                    .replace(/(\b\d+\b)/g, '<span class="text-[#b5cea8]">$1</span>')
                    .replace(/(\/\/.*$)/g, '<span class="text-[#6a9955]">$1</span>')
                    .replace(/([{}()[\];,.])/g, '<span class="text-gray-400">$1</span>');

                  return (
                    <div key={i} className="leading-6" dangerouslySetInnerHTML={{ __html: highlighted || ' ' }} />
                  );
                })}
              </code>
            );
          },
          pre: ({ children, ...props }: any) => {
            // Extract text content from the code block for the copy button
            let codeText = '';
            const childProps = (children as any)?.props;
            if (React.isValidElement(children) && childProps && childProps.children) {
              codeText = String(childProps.children);
            }

            const showCopy = props['data-show-copy'] === 'true' || (props['data-show-copy'] === undefined && showCopyButton);

            return (
              <div
                className="relative group mb-4"
                onDoubleClick={(e) => handleBlockDoubleClick(e, 'code')}
              >
                <pre className="overflow-x-auto bg-[#1a1a1a] border border-white/10 rounded-lg p-4" {...props}>
                  {children}
                </pre>
                <div className={`absolute top-2 right-2 flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity`}>
                  {showCopy && <CopyButton text={codeText} className="" />}
                </div>
              </div>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};