import { loadStyleConfigFromCloud, DEFAULT_STYLE_CONFIG, type CodeStyleConfig } from '../services/codeStyleService';

export const loadCodeStyle = async (): Promise<void> => {
  let codeStyle: CodeStyleConfig = DEFAULT_STYLE_CONFIG.code;

  try {
    const cloudConfig = await loadStyleConfigFromCloud();
    if (cloudConfig) {
      codeStyle = cloudConfig.code;
    }
  } catch (error) {
    console.error('Error loading from cloud, using defaults:', error);
  }

  const rgbaMatch = codeStyle.bgColor.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)/);
  let bgColorWithOpacity = codeStyle.bgColor;

  if (rgbaMatch) {
    const [_, r, g, b] = rgbaMatch;
    bgColorWithOpacity = `rgba(${r}, ${g}, ${b}, ${codeStyle.opacity / 100})`;
  }

  const widthValue = codeStyle.width === 'auto' ? 0 : parseFloat(codeStyle.width) || 0;
  const heightValue = codeStyle.height === 'auto' ? 0 : parseFloat(codeStyle.height) || 0;
  
  const existingStyle = document.getElementById('dynamic-code-style');
  if (existingStyle) {
    existingStyle.remove();
  }

  const style = document.createElement('style');
  style.id = 'dynamic-code-style';
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
      border: none !important;
      font-family: 'Consolas', monospace !important;
      line-height: 1 !important;
      margin: 0 1px !important;
    }

    button code, a code, .btn code {
      background: transparent !important;
      padding: 0 !important;
      color: inherit !important;
      border: none !important;
    }

    code::before, code::after {
      content: "" !important;
      display: none !important;
    }
  `;

  document.head.appendChild(style);
};