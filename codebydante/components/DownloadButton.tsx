import React, { useState } from 'react';
import { Download, Check } from 'lucide-react';

export const DownloadButton = ({ text, filename = 'download.txt', className = '', ...props }: { text: string, filename?: string, className?: string } & React.ButtonHTMLAttributes<HTMLButtonElement>) => {
    const [downloaded, setDownloaded] = useState(false);

    const handleDownload = () => {
        const element = document.createElement("a");
        const file = new Blob([text], { type: 'text/plain' });
        element.href = URL.createObjectURL(file);
        element.download = filename;
        document.body.appendChild(element); // Required for this to work in FireFox
        element.click();
        document.body.removeChild(element);

        setDownloaded(true);
        setTimeout(() => setDownloaded(false), 2000);
    };

    return (
        <button
            onClick={handleDownload}
            className={`p-1.5 bg-[#2d2d2d] border border-white/10 rounded-md text-gray-400 hover:text-white hover:bg-primary/20 transition-all z-10 ${className}`}
            title="Descargar archivo"
            {...props}
        >
            {downloaded ? <Check size={14} /> : <Download size={14} />}
        </button>
    );
};
