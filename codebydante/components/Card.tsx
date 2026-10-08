import React, { useState, useEffect, useRef } from 'react';
import { DataItem } from '../types';
import { Download, ExternalLink, Check, Folder, Pin, Maximize2 } from 'lucide-react';
import { getIconComponent } from './IconPicker';
import { subscribeToStyleConfig, DEFAULT_STYLE_CONFIG, saveStyleConfigToCloud } from '../services/codeStyleService';

interface CardProps {
  item: DataItem;
  onClick: (item: DataItem) => void;
  isSelectable?: boolean;
  isSelected?: boolean;
  onMouseDown?: (e: React.MouseEvent, item: DataItem) => void;
  onMouseEnter?: (e: React.MouseEvent, item: DataItem) => void;
  onDoubleClick?: (item: DataItem) => void;
}

export const Card: React.FC<CardProps> = ({ item, onClick, isSelectable, isSelected, onMouseDown, onMouseEnter, onDoubleClick }) => {
  const Icon = getIconComponent(item.icon);
  const [styleConfig, setStyleConfig] = useState(DEFAULT_STYLE_CONFIG);

  useEffect(() => {
    const unsubscribe = subscribeToStyleConfig((config) => {
      setStyleConfig(config);
    });
    return () => unsubscribe();
  }, []);

  const cardStyle = {
    width: '100%',
    height: '190px',
  };

  const rawTitle = (item.title || '').replace(/<[^>]*>?/gm, '').replace(/&nbsp;/g, ' ');

  if (item.isFolder) {
    return (
       <div
         onClick={() => onClick(item)}
         onDoubleClick={() => onDoubleClick?.(item)}
         onMouseDown={(e) => onMouseDown?.(e, item)}
         onMouseEnter={(e) => onMouseEnter?.(e, item)}
         style={{ 
           userSelect: isSelectable ? 'none' : 'auto',
           ...cardStyle
         }}
         className={`relative group bg-surface border ${isSelected ? 'border-primary ring-2 ring-primary bg-primary/10 shadow-[0_0_20px_rgba(187,134,252,0.15)]' : 'border-white/5 hover:border-primary/30 hover:bg-white/[0.02]'} rounded-xl cursor-pointer transition-[border,background-color,transform,box-shadow,color] duration-300 ${isSelected ? 'scale-[0.98]' : 'hover:-translate-y-1 hover:shadow-lg'} flex flex-col items-center justify-center text-center overflow-hidden`}
       >
         {isSelected && (
            <div className="absolute top-2 right-2 z-20 w-5 h-5 bg-primary rounded-full flex items-center justify-center shadow-lg transition-transform animate-in zoom-in duration-200 pointer-events-none">
              <Check size={12} className="text-[#121212]" strokeWidth={3} />
            </div>
         )}
         {item.isPinned && (
            <div className="absolute top-2 left-2 z-20 w-5 h-5 bg-primary/20 backdrop-blur-sm border border-primary/30 rounded-full flex items-center justify-center shadow-lg transition-transform animate-in zoom-in duration-200 pointer-events-none">
              <Pin size={10} className="text-primary fill-primary" />
            </div>
         )}
         {/* Folder content stays as was before pill change */}
         <div className="p-3 bg-white/5 rounded-xl mb-2 group-hover:bg-primary/10 transition-colors">
            <Folder size={28} className="text-primary opacity-80 group-hover:opacity-100 transition-opacity" strokeWidth={1} />
         </div>
         <h3 
           style={{ fontSize: styleConfig.general.cardTitleSize }}
           className="font-bold text-white group-hover:text-primary transition-colors truncate w-full px-2"
           title={rawTitle}
         >
           {rawTitle}
         </h3>
       </div>
    );
  }

  return (
    <div
      onClick={(e) => {
        onClick(item);
      }}
      onDoubleClick={() => onDoubleClick?.(item)}
      onMouseDown={(e) => onMouseDown?.(e, item)}
      onMouseEnter={(e) => onMouseEnter?.(e, item)}
      style={{ 
        userSelect: isSelectable ? 'none' : 'auto',
        ...cardStyle
      }}
      className={`relative group bg-surface border ${isSelected ? 'border-primary ring-2 ring-primary bg-primary/10 shadow-[0_0_20px_rgba(187,134,252,0.15)]' : 'border-white/5 hover:border-primary/30'} rounded-xl cursor-pointer transition-[border,background-color,transform,box-shadow,color] duration-300 ${isSelected ? 'scale-[0.98]' : 'hover:-translate-y-1'} flex flex-col overflow-hidden p-5`}
    >
      {isSelected && (
        <div className="absolute top-2 right-2 z-20 w-5 h-5 bg-primary rounded-full flex items-center justify-center shadow-lg pointer-events-none">
          <Check size={12} className="text-[#121212]" strokeWidth={3} />
        </div>
      )}
      {item.isPinned && (
        <div className="absolute top-2 left-2 z-20 w-5 h-5 bg-primary/20 backdrop-blur-sm border border-primary/30 rounded-full flex items-center justify-center shadow-lg pointer-events-none">
          <Pin size={10} className="text-primary fill-primary" />
        </div>
      )}
      <div className="mb-1 flex-grow flex flex-col min-h-0">
        <div className="flex items-start gap-2 mb-2 w-full">
          {Icon && (
            <div className="text-primary shrink-0 mt-0.5">
              <Icon size={20} />
            </div>
          )}
          <h3
            style={{ fontSize: styleConfig.general.cardTitleSize }}
            className="font-bold text-white leading-tight group-hover:text-primary transition-colors truncate min-w-0"
            title={rawTitle}
          >
            {rawTitle}
          </h3>
        </div>
        <div
          className="text-zinc-400 leading-relaxed [&>p]:m-0 [&_img]:hidden [&_figure]:hidden overflow-hidden"
          dangerouslySetInnerHTML={{ __html: item.summary }}
          style={{
            display: '-webkit-box',
            WebkitLineClamp: (item.visitUrl || item.downloadUrl) ? 3 : 6,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            fontSize: styleConfig.general.cardFontSize
          }}
        />
      </div>



      {/* Buttons Section */}
      {(item.visitUrl || item.downloadUrl) && (
        <div className="mt-auto flex gap-1.5 pt-2 border-t border-white/5">
          {item.visitUrl && (
            <a
              href={item.visitUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className={`flex-1 bg-transparent border border-primary/30 text-primary font-bold py-2 px-2 rounded-lg flex items-center justify-center gap-1.5 hover:bg-primary hover:text-background transition-all text-xs sm:text-[12px]`}
            >
              <ExternalLink size={14} />
              Visitar
            </a>
          )}

          {item.downloadUrl && (
            <a
              href={item.downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              onClick={(e) => e.stopPropagation()}
              className={`flex-1 bg-transparent border border-primary/30 text-primary font-bold py-2 px-2 rounded-lg flex items-center justify-center gap-1.5 hover:bg-primary hover:text-background transition-all text-xs sm:text-[12px]`}
            >
              <Download size={14} />
              Descargar
            </a>
          )}
        </div>
      )}
    </div>
  );
};