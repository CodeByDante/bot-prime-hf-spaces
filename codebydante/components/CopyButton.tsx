import React, { useState } from 'react';
import { Copy, Check } from 'lucide-react';

export const CopyButton = ({ text, className = '' }: { text: string, className?: string }) => {
    const [copied, setCopied] = useState(false);

    const handleCopy = () => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <button
            onClick={handleCopy}
            className={`p-1.5 bg-[#2d2d2d] border border-white/10 rounded-md text-gray-400 hover:text-white hover:bg-primary/20 transition-all z-10 ${className}`}
            title="Copiar código"
        >
            {copied ? <Check size={14} /> : <Copy size={14} />}
        </button>
    );
};
