import React, { useState, useEffect, useRef, forwardRef, useImperativeHandle } from 'react';
import {
  Bold, Italic, List, ListOrdered, Quote, Code,
  Type, Palette, Layout, Settings, X, Check, Copy,
  AlignLeft, AlignCenter, AlignRight, Maximize2, Minimize2
} from 'lucide-react';
import {
  DEFAULT_STYLE_CONFIG,
  subscribeToStyleConfig,
  saveStyleConfigToCloud,
  type StyleConfig,
  type CodeStyleConfig,
  type QuoteStyleConfig
} from '../services/codeStyleService';
import { StyleSettingsPanel } from './StyleSettingsPanel';

interface TextFormatToolbarProps {
  textareaRef: React.RefObject<HTMLTextAreaElement>;
  onApplyFormat: (start: number, end: number, formatted: string) => void;
}

export interface TextFormatToolbarRef {
  openSettings: (tab: 'code' | 'quote') => void;
  syncStylesFromSelection: () => void;
}

type FormatType = 'bold' | 'italic' | 'code' | 'quote' | 'uppercase' | 'lowercase' | 'plain';
type SettingsTab = 'code' | 'quote' | 'general' | 'link';

export const TextFormatToolbar = forwardRef<TextFormatToolbarRef, TextFormatToolbarProps>(({ textareaRef, onApplyFormat }, ref) => {
  const [selectedText, setSelectedText] = useState('');
  const [selectedRange, setSelectedRange] = useState<{ start: number; end: number } | null>(null);
  const [activeFormats, setActiveFormats] = useState<Set<FormatType>>(new Set());
  const [showSettings, setShowSettings] = useState(false);
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('code');

  const [localStyleConfig, setLocalStyleConfig] = useState<StyleConfig>(DEFAULT_STYLE_CONFIG);
  // Estado temporal para la configuración (borrador)
  const [tempStyleConfig, setTempStyleConfig] = useState<StyleConfig | null>(null);
  const toolbarRef = useRef<HTMLDivElement>(null);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    openSettings: (tab) => {
      setShowSettings(true);
      setSettingsTab(tab);
      // Inicializar el borrador con la configuración actual
      setTempStyleConfig(localStyleConfig);
    },
    syncStylesFromSelection: () => {
      checkSelectionFormat();
    }
  }));

  useEffect(() => {
    const unsubscribe = subscribeToStyleConfig((config) => {
      setLocalStyleConfig(config);
    });
    return () => unsubscribe();
  }, []);

  // Usar tempStyleConfig si existe (modo edición), sino localStyleConfig
  const styleConfig = tempStyleConfig || localStyleConfig;

  // Helper to update style config (Draft logic)
  const handleConfigUpdate = (newConfig: StyleConfig) => {
    // Solo actualizamos el estado temporal, no aplicamos cambios al texto ni a la nube todavía
    setTempStyleConfig(newConfig);
  };

  const handleConfirmSettings = () => {
    if (!tempStyleConfig) return;

    // Aplicar cambios permanentemente
    setLocalStyleConfig(tempStyleConfig);

    // Guardar en la nube y aplicar al texto seleccionado
    const newConfig = tempStyleConfig;

    const textarea = textareaRef.current;
    if (!textarea) {
      saveStyleConfigToCloud(newConfig);
      setShowSettings(false);
      setTempStyleConfig(null);
      return;
    }

    const cursor = textarea.selectionStart;
    const text = textarea.value;

    let isInBlock = false;

    // Check for Blockquote
    const quoteRegex = /<blockquote[^>]*>([\s\S]*?)<\/blockquote>/g;
    let match;
    while ((match = quoteRegex.exec(text)) !== null) {
      if (cursor >= match.index && cursor <= match.index + match[0].length) {
        isInBlock = true;
        const newStyle = getQuoteStyleString(newConfig.quote);
        const openTagRegex = /<blockquote[^>]*>/;
        const openTagMatch = openTagRegex.exec(match[0]);

        if (openTagMatch) {
          const newOpenTag = `<blockquote style="${newStyle}" data-show-copy="${newConfig.quote.showCopyButton}">`;
          const newFullBlock = match[0].replace(openTagMatch[0], newOpenTag);
          setTimeout(() => {
            onApplyFormat(match.index, match.index + match[0].length, newFullBlock);
          }, 0);
        }
        break;
      }
    }

    // Check for Code if not in quote
    if (!isInBlock) {
      const codeRegex = /<code[^>]*>([\s\S]*?)<\/code>/g;
      while ((match = codeRegex.exec(text)) !== null) {
        if (cursor >= match.index && cursor <= match.index + match[0].length) {
          isInBlock = true;
          const newStyle = getCodeStyleString(newConfig.code);
          const openTagRegex = /<code[^>]*>/;
          const openTagMatch = openTagRegex.exec(match[0]);

          if (openTagMatch) {
            const newOpenTag = `<code style="${newStyle}">`;
            const newFullBlock = match[0].replace(openTagMatch[0], newOpenTag);
            setTimeout(() => {
              onApplyFormat(match.index, match.index + match[0].length, newFullBlock);
            }, 0);
          }
          break;
        }
      }
    }

    // If NOT in a block, update global config
    if (!isInBlock) {
      saveStyleConfigToCloud(newConfig);
    }

    setShowSettings(false);
    setTempStyleConfig(null);
  };

  const handleCancelSettings = () => {
    // Descartar cambios
    setTempStyleConfig(null);
    setShowSettings(false);
  };

  const checkSelectionFormat = () => {
    // Placeholder for now, can be implemented to read styles from selection
    // For now, double click just opens the settings
  };

  const updateSelectionState = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const text = textarea.value.substring(start, end);

    setSelectedText(text);
    setSelectedRange({ start, end });
  };

  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    textarea.addEventListener('mouseup', updateSelectionState);
    textarea.addEventListener('keyup', updateSelectionState);
    textarea.addEventListener('click', updateSelectionState);
    textarea.addEventListener('select', updateSelectionState);
    textarea.addEventListener('focus', updateSelectionState);

    return () => {
      textarea.removeEventListener('mouseup', updateSelectionState);
      textarea.removeEventListener('keyup', updateSelectionState);
      textarea.removeEventListener('click', updateSelectionState);
      textarea.removeEventListener('select', updateSelectionState);
      textarea.removeEventListener('focus', updateSelectionState);
    };
  }, [textareaRef]);


  useEffect(() => {
    const style = document.createElement('style');
    style.id = 'dynamic-style-config';

    const codeStyle = styleConfig.code;
    const quoteStyle = styleConfig.quote;

    const rgbaMatch = codeStyle.bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
    let bgColorWithOpacity = codeStyle.bgColor;

    if (rgbaMatch) {
      const [_, r, g, b] = rgbaMatch;
      bgColorWithOpacity = `rgba(${r}, ${g}, ${b}, ${codeStyle.opacity / 100})`;
    }

    const widthValue = codeStyle.width === 'auto' ? 0 : parseFloat(codeStyle.width) || 0;
    const heightValue = codeStyle.height === 'auto' ? 0 : parseFloat(codeStyle.height) || 0;

    style.innerHTML = `
      :not(pre) > code {
        background-color: ${bgColorWithOpacity} !important;
        color: ${codeStyle.textColor} !important;
        font-size: ${codeStyle.fontSize} !important;
        border-radius: ${codeStyle.borderRadius} !important;

        padding: 0px 2px !important;

        ${codeStyle.width !== 'auto' && widthValue > 0 ? `min-width: ${codeStyle.width} !important;` : ''}
        ${codeStyle.height !== 'auto' && heightValue > 0 ? `min-height: ${codeStyle.height} !important;` : ''}

        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;

        vertical-align: middle !important;
        border: 1px solid rgba(255,255,255,0.05) !important;
        font-family: 'Consolas', 'Monaco', monospace !important;
        line-height: 1 !important;
        margin: 0 1px !important;
      }

      blockquote {
        background-color: ${quoteStyle.bgColor} !important;
        color: ${quoteStyle.textColor} !important;
        border-left: ${quoteStyle.borderWidth} solid ${quoteStyle.borderColor} !important;
        padding: ${quoteStyle.padding} !important;
        font-size: ${quoteStyle.fontSize} !important;
        border-radius: ${quoteStyle.borderRadius} !important;
        font-style: ${quoteStyle.italic ? 'italic' : 'normal'} !important;
        
        ${quoteStyle.width !== 'auto' ? `width: ${quoteStyle.width} !important;` : ''}
        ${quoteStyle.height !== 'auto' ? `min-height: ${quoteStyle.height} !important;` : ''}
        
        overflow: visible !important;
        position: relative !important;
        margin-bottom: 1rem !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: center !important;
        word-break: break-word !important;
      }

      button code, a code, .btn code {
        background: transparent !important;
        padding: 0 !important;
        color: inherit !important;
        border: none !important;
        margin: 0 !important;
      }
    `;

    const existingStyle = document.getElementById('dynamic-style-config');
    if (existingStyle) {
      existingStyle.remove();
    }

    document.head.appendChild(style);

    return () => {
      style.remove();
    };
  }, [styleConfig]);

  const applyFormat = (format: FormatType) => {
    let currentStart = selectedRange?.start || 0;
    let currentEnd = selectedRange?.end || 0;
    let currentText = selectedText;

    if (!selectedRange && textareaRef.current) {
      currentStart = textareaRef.current.selectionStart;
      currentEnd = textareaRef.current.selectionEnd;
      currentText = textareaRef.current.value.substring(currentStart, currentEnd);
    }

    if (textareaRef.current) {
      currentStart = textareaRef.current.selectionStart;
      currentEnd = textareaRef.current.selectionEnd;
      currentText = textareaRef.current.value.substring(currentStart, currentEnd);
    }

    let formatted = currentText;

    switch (format) {
      case 'bold':
        formatted = `**${currentText}**`;
        break;
      case 'italic':
        formatted = `*${currentText}*`;
        break;
      case 'code':
        formatted = `\`${currentText}\``;
        break;
      case 'quote':
        const lines = currentText.split('\n');
        const quotedLines = lines.map(line => `> ${line}`);
        formatted = quotedLines.join('\n') + '\n\n';
        break;
      case 'uppercase':
        formatted = currentText.toUpperCase();
        break;
      case 'lowercase':
        formatted = currentText.toLowerCase();
        break;
      case 'plain':
        formatted = currentText
          .replace(/\*\*/g, '')
          .replace(/\*/g, '')
          .replace(/`/g, '')
          .replace(/<[^>]+>/g, ''); // Remove HTML tags
        break;
    }

    onApplyFormat(currentStart, currentEnd, formatted);
    setSelectedText(formatted);

    const newActiveFormats = new Set(activeFormats);

    // Code format is transient/stateless for this toolbar
    if (format === 'code') {
      // Do nothing to activeFormats, or remove if it was there (though it shouldn't be)
      if (newActiveFormats.has('code')) {
        newActiveFormats.delete('code');
      }
    } else {
      if (newActiveFormats.has(format)) {
        newActiveFormats.delete(format);
      } else {
        if (['uppercase', 'lowercase', 'plain'].includes(format)) {
          newActiveFormats.clear();
        }
        newActiveFormats.add(format);
      }
    }
    setActiveFormats(newActiveFormats);
  };

  const getCodeStyleString = (config: CodeStyleConfig) => {
    const rgbaMatch = config.bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
    let bgColor = config.bgColor;
    if (rgbaMatch) {
      const [_, r, g, b] = rgbaMatch;
      bgColor = `rgba(${r}, ${g}, ${b}, ${config.opacity / 100})`;
    }

    return [
      `background-color: ${bgColor}`,
      `color: ${config.textColor}`,
      `font-size: ${config.fontSize}`,
      `border-radius: ${config.borderRadius}`,
      `padding: 0px 2px`,
      config.width !== 'auto' ? `min-width: ${config.width}` : '',
      config.height !== 'auto' ? `min-height: ${config.height}` : '',
      'display: inline-flex',
      'align-items: center',
      'justify-content: center',
      'vertical-align: middle',
      'border: 1px solid rgba(255,255,255,0.05)',
      "font-family: 'Consolas', 'Monaco', monospace",
      'line-height: 1',
      'margin: 0 1px'
    ].filter(Boolean).join('; ');
  };

  const getQuoteStyleString = (config: QuoteStyleConfig) => {
    return [
      `background-color: ${config.bgColor}`,
      `color: ${config.textColor}`,
      `border-left: ${config.borderWidth} solid ${config.borderColor}`,
      `padding: ${config.padding}`,
      `font-size: ${config.fontSize}`,
      `border-radius: ${config.borderRadius}`,
      config.italic ? 'font-style: italic' : 'font-style: normal',
      config.width !== 'auto' ? `width: ${config.width}` : '',
      config.height !== 'auto' ? `height: ${config.height}` : '',
      'overflow: visible',
      'position: relative',
      'margin-bottom: 1rem',
      'display: flex',
      'flex-direction: column',
      'justify-content: center'
    ].filter(Boolean).join('; ');
  };

  return (
    <>
      <div
        ref={toolbarRef}
        className="fixed bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-1 bg-surface/95 backdrop-blur-sm border border-white/10 rounded-xl p-1.5 shadow-[0_4px_20px_rgba(0,0,0,0.4)] z-50 pointer-events-auto animate-fade-in transition-all duration-300"
        style={{ position: 'fixed', bottom: '3rem', left: '50%', transform: 'translateX(-50%)' }}
      >
        <button
          type="button"
          onClick={() => applyFormat('bold')}
          className={`p-2 rounded-lg transition-all ${activeFormats.has('bold')
            ? 'bg-primary text-background shadow-md'
            : 'hover:bg-white/10 text-gray-400 hover:text-white'
            }`}
          title="Negrita"
        >
          <Bold size={18} strokeWidth={2.5} />
        </button>

        <button
          type="button"
          onClick={() => applyFormat('italic')}
          className={`p-2 rounded-lg transition-all ${activeFormats.has('italic')
            ? 'bg-primary text-background shadow-md'
            : 'hover:bg-white/10 text-gray-400 hover:text-white'
            }`}
          title="Cursiva"
        >
          <Italic size={18} strokeWidth={2.5} />
        </button>

        <button
          type="button"
          onClick={() => applyFormat('code')}
          className={`p-2 rounded-lg transition-all ${activeFormats.has('code')
            ? 'bg-primary text-background shadow-md'
            : 'hover:bg-white/10 text-gray-400 hover:text-white'
            }`}
          title="Código Inline"
        >
          <Code size={18} strokeWidth={2.5} />
        </button>

        <button
          type="button"
          onClick={() => applyFormat('quote')}
          className={`p-2 rounded-lg transition-all ${activeFormats.has('quote')
            ? 'bg-primary text-background shadow-md'
            : 'hover:bg-white/10 text-gray-400 hover:text-white'
            }`}
          title="Citar"
        >
          <Quote size={18} strokeWidth={2.5} />
        </button>

        <div className="w-px h-6 bg-white/10 mx-1"></div>

        <button
          type="button"
          onClick={() => applyFormat('uppercase')}
          className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-all text-xs font-bold"
          title="MAYÚSCULAS"
        >
          AA
        </button>

        <button
          type="button"
          onClick={() => applyFormat('lowercase')}
          className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-white transition-all text-xs font-bold"
          title="minúsculas"
        >
          aa
        </button>

        <button
          type="button"
          onClick={() => applyFormat('plain')}
          className="p-2 rounded-lg hover:bg-white/10 text-gray-400 hover:text-red-400 transition-all"
          title="Limpiar Formato"
        >
          <X size={18} />
        </button>

        <div className="w-px h-6 bg-white/10 mx-1"></div>

        <button
          type="button"
          onClick={() => setShowSettings(!showSettings)}
          className={`p-2 rounded-lg transition-all ${showSettings
            ? 'bg-primary text-background shadow-md'
            : 'hover:bg-white/10 text-gray-400 hover:text-white'
            }`}
          title="Configuración"
        >
          <Settings size={18} strokeWidth={2.5} />
        </button>
      </div>

      {showSettings && (
        <div
          className="fixed bottom-24 left-1/2 -translate-x-1/2 bg-[#1a1a1a] border border-white/10 rounded-xl shadow-[0_0_40px_rgba(0,0,0,0.6)] z-50 w-[380px] flex flex-col max-h-[75vh] animate-fade-in overflow-hidden"
          style={{ position: 'fixed', bottom: '7rem', left: '50%', transform: 'translateX(-50%)' }}
        >
          <StyleSettingsPanel
            styleConfig={styleConfig}
            onUpdateConfig={handleConfigUpdate}
            activeTab={settingsTab}
            onTabChange={setSettingsTab}
            onClose={handleCancelSettings}
            onConfirm={handleConfirmSettings}
          />
        </div>
      )}
    </>
  );
});
