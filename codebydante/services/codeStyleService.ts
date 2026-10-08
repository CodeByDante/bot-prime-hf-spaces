import { initializeApp } from 'firebase/app';
import {
  getFirestore,
  collection,
  doc,
  getDoc,
  setDoc,
  onSnapshot
} from 'firebase/firestore';

const firebaseConfig = {
  apiKey: "AIzaSyAH3jvbe0_QLzIuuv5kTMK8246HNvohvfE",
  authDomain: "twistedbrody-9d163.firebaseapp.com",
  projectId: "twistedbrody-9d163",
  storageBucket: "twistedbrody-9d163.firebasestorage.app",
  messagingSenderId: "733213514129",
  appId: "1:733213514129:web:e9694684f5c3994ed06230",
  measurementId: "G-N8TQ7MY42W"
};

const app = initializeApp(firebaseConfig);
const db = getFirestore(app);
const COLLECTION_NAME = 'code_style_config';

export interface GeneralConfig {
  cardWidth: string;
  cardHeight: string;
  cardFontSize: string;
  cardTitleSize: string;
}

export interface QuoteStyleConfig {
  textColor: string;
  bgColor: string;
  borderColor: string;
  borderWidth: string;
  fontSize: string;
  padding: string;
  borderRadius: string;
  italic: boolean;
  width: string;
  height: string;
  showCopyButton: boolean;
  showDownloadButton: boolean;
  collapsible: boolean;
  fontFamily: string;
  isCodeFont: boolean;
}

export interface CodeStyleConfig {
  textColor: string;
  bgColor: string;
  opacity: number;
  width: string;
  height: string;
  fontSize: string;
  borderRadius: string;
  fontFamily: string;
  showBackground: boolean;
  lineHeight: string;
  collapsible: boolean;
  showLineNumbers: boolean;
  wrapText: boolean;
}

export interface LinkStyleConfig {
  underlineEnabled: boolean;
}

export interface ButtonStyleConfig {
  width: string;
  height: string;
  backgroundColor: string;
  textColor: string;
  borderRadius: string;
}

export interface StyleConfig {
  general: GeneralConfig;
  code: CodeStyleConfig;
  quote: QuoteStyleConfig;
  link: LinkStyleConfig;
  button: ButtonStyleConfig;
  showCopyButton: boolean;
}

export const DEFAULT_GENERAL_STYLE: GeneralConfig = {
  cardWidth: '358px',
  cardHeight: '190px',
  cardFontSize: '12px',
  cardTitleSize: '16px'
};

export const DEFAULT_QUOTE_STYLE: QuoteStyleConfig = {
  textColor: '#9ca3af',
  bgColor: 'rgba(255, 255, 255, 0.06)',
  borderColor: '#4a4a4a',
  borderWidth: '7px',
  fontSize: '0.9em',
  padding: '8px',
  borderRadius: '3px',
  italic: true,
  width: 'auto',
  height: 'auto',
  showCopyButton: true,
  showDownloadButton: true,
  collapsible: false,
  fontFamily: 'inherit',
  isCodeFont: true
};

export const DEFAULT_CODE_STYLE: CodeStyleConfig = {
  textColor: '#c0c0c0',
  bgColor: 'rgba(85, 85, 85, 0.55)',
  opacity: 55,
  width: 'auto',
  height: 'auto',
  fontSize: '0.85em',
  borderRadius: '4px',
  fontFamily: "'Consolas', 'Monaco', monospace",
  showBackground: true,
  lineHeight: '1.5',
  collapsible: true, // Collapsible enabled by default for new blocks
  showLineNumbers: false,
  wrapText: false
};

export const DEFAULT_LINK_STYLE: LinkStyleConfig = {
  underlineEnabled: true
};

export const DEFAULT_BUTTON_STYLE: ButtonStyleConfig = {
  width: 'auto',
  height: 'auto',
  backgroundColor: '#bb86fc', // Primary color
  textColor: '#ffffff',
  borderRadius: '8px'
};

export const DEFAULT_STYLE_CONFIG: StyleConfig = {
  general: DEFAULT_GENERAL_STYLE,
  code: DEFAULT_CODE_STYLE,
  quote: DEFAULT_QUOTE_STYLE,
  link: DEFAULT_LINK_STYLE,
  button: DEFAULT_BUTTON_STYLE,
  showCopyButton: false
};

const getUserId = (): string => {
  let userId = localStorage.getItem('codebydate_user_id');
  if (!userId) {
    userId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    localStorage.setItem('codebydate_user_id', userId);
  }
  return userId;
};

export const saveStyleConfigToCloud = async (config: StyleConfig): Promise<void> => {
  try {
    const userId = getUserId();
    const docRef = doc(db, COLLECTION_NAME, userId);

    await setDoc(docRef, {
      ...config,
      userId,
      updatedAt: new Date().toISOString()
    }, { merge: true });

    console.log('Style config saved to cloud:', config);
  } catch (error) {
    console.error('Error saving style config to cloud:', error);
    throw error;
  }
};

export const loadStyleConfigFromCloud = async (): Promise<StyleConfig | null> => {
  try {
    const userId = getUserId();
    const docRef = doc(db, COLLECTION_NAME, userId);
    const docSnap = await getDoc(docRef);

    if (docSnap.exists()) {
      const data = docSnap.data();
      return {
        general: {
          cardWidth: data.general?.cardWidth || DEFAULT_GENERAL_STYLE.cardWidth,
          cardHeight: data.general?.cardHeight || DEFAULT_GENERAL_STYLE.cardHeight,
          cardFontSize: data.general?.cardFontSize || DEFAULT_GENERAL_STYLE.cardFontSize,
          cardTitleSize: data.general?.cardTitleSize || DEFAULT_GENERAL_STYLE.cardTitleSize,
        },
        code: {
          textColor: data.code?.textColor || DEFAULT_CODE_STYLE.textColor,
          bgColor: data.code?.bgColor || DEFAULT_CODE_STYLE.bgColor,
          opacity: data.code?.opacity || DEFAULT_CODE_STYLE.opacity,
          width: data.code?.width || DEFAULT_CODE_STYLE.width,
          height: data.code?.height || DEFAULT_CODE_STYLE.height,
          fontSize: data.code?.fontSize || DEFAULT_CODE_STYLE.fontSize,
          borderRadius: data.code?.borderRadius || DEFAULT_CODE_STYLE.borderRadius,
          fontFamily: data.code?.fontFamily || DEFAULT_CODE_STYLE.fontFamily,
          showBackground: data.code?.showBackground !== undefined ? data.code.showBackground : DEFAULT_CODE_STYLE.showBackground,
          lineHeight: data.code?.lineHeight || DEFAULT_CODE_STYLE.lineHeight,
          collapsible: data.code?.collapsible !== undefined ? data.code.collapsible : DEFAULT_CODE_STYLE.collapsible,
          showLineNumbers: data.code?.showLineNumbers !== undefined ? data.code.showLineNumbers : DEFAULT_CODE_STYLE.showLineNumbers,
          wrapText: data.code?.wrapText !== undefined ? data.code.wrapText : DEFAULT_CODE_STYLE.wrapText
        },
        quote: {
          textColor: data.quote?.textColor || DEFAULT_QUOTE_STYLE.textColor,
          bgColor: data.quote?.bgColor || DEFAULT_QUOTE_STYLE.bgColor,
          borderColor: data.quote?.borderColor || DEFAULT_QUOTE_STYLE.borderColor,
          borderWidth: data.quote?.borderWidth || DEFAULT_QUOTE_STYLE.borderWidth,
          fontSize: data.quote?.fontSize || DEFAULT_QUOTE_STYLE.fontSize,
          padding: data.quote?.padding || DEFAULT_QUOTE_STYLE.padding,
          borderRadius: data.quote?.borderRadius || DEFAULT_QUOTE_STYLE.borderRadius,
          italic: data.quote?.italic !== undefined ? data.quote.italic : DEFAULT_QUOTE_STYLE.italic,
          width: data.quote?.width || DEFAULT_QUOTE_STYLE.width,
          height: data.quote?.height || DEFAULT_QUOTE_STYLE.height,
          showCopyButton: data.quote?.showCopyButton !== undefined ? data.quote.showCopyButton : DEFAULT_QUOTE_STYLE.showCopyButton,
          showDownloadButton: data.quote?.showDownloadButton !== undefined ? data.quote.showDownloadButton : DEFAULT_QUOTE_STYLE.showDownloadButton,
          collapsible: data.quote?.collapsible !== undefined ? data.quote.collapsible : DEFAULT_QUOTE_STYLE.collapsible,
          fontFamily: data.quote?.fontFamily || DEFAULT_QUOTE_STYLE.fontFamily,
          isCodeFont: data.quote?.isCodeFont !== undefined ? data.quote.isCodeFont : DEFAULT_QUOTE_STYLE.isCodeFont,
        },
        link: {
          underlineEnabled: data.link?.underlineEnabled !== undefined ? data.link.underlineEnabled : DEFAULT_LINK_STYLE.underlineEnabled
        },
        button: {
          width: data.button?.width || DEFAULT_BUTTON_STYLE.width,
          height: data.button?.height || DEFAULT_BUTTON_STYLE.height,
          backgroundColor: data.button?.backgroundColor || DEFAULT_BUTTON_STYLE.backgroundColor,
          textColor: data.button?.textColor || DEFAULT_BUTTON_STYLE.textColor,
          borderRadius: data.button?.borderRadius || DEFAULT_BUTTON_STYLE.borderRadius
        },
        showCopyButton: data.showCopyButton !== undefined ? data.showCopyButton : DEFAULT_STYLE_CONFIG.showCopyButton
      };
    }

    return null;
  } catch (error) {
    console.error('Error loading style config from cloud:', error);
    return null;
  }
};

export const subscribeToStyleConfig = (callback: (config: StyleConfig) => void) => {
  const userId = getUserId();
  const docRef = doc(db, COLLECTION_NAME, userId);

  // Load initial config immediately
  getDoc(docRef).then((docSnap) => {
    if (docSnap.exists()) {
      const data = docSnap.data();
      const config: StyleConfig = {
        general: {
          cardWidth: data.general?.cardWidth || DEFAULT_GENERAL_STYLE.cardWidth,
          cardHeight: data.general?.cardHeight || DEFAULT_GENERAL_STYLE.cardHeight,
          cardFontSize: data.general?.cardFontSize || DEFAULT_GENERAL_STYLE.cardFontSize,
          cardTitleSize: data.general?.cardTitleSize || DEFAULT_GENERAL_STYLE.cardTitleSize,
        },
        code: {
          textColor: data.code?.textColor || DEFAULT_CODE_STYLE.textColor,
          bgColor: data.code?.bgColor || DEFAULT_CODE_STYLE.bgColor,
          opacity: data.code?.opacity || DEFAULT_CODE_STYLE.opacity,
          width: data.code?.width || DEFAULT_CODE_STYLE.width,
          height: data.code?.height || DEFAULT_CODE_STYLE.height,
          fontSize: data.code?.fontSize || DEFAULT_CODE_STYLE.fontSize,
          borderRadius: data.code?.borderRadius || DEFAULT_CODE_STYLE.borderRadius,
          fontFamily: data.code?.fontFamily || DEFAULT_CODE_STYLE.fontFamily,
          showBackground: data.code?.showBackground !== undefined ? data.code.showBackground : DEFAULT_CODE_STYLE.showBackground,
          lineHeight: data.code?.lineHeight || DEFAULT_CODE_STYLE.lineHeight,
          collapsible: data.code?.collapsible !== undefined ? data.code.collapsible : DEFAULT_CODE_STYLE.collapsible,
          showLineNumbers: data.code?.showLineNumbers !== undefined ? data.code.showLineNumbers : DEFAULT_CODE_STYLE.showLineNumbers,
          wrapText: data.code?.wrapText !== undefined ? data.code.wrapText : DEFAULT_CODE_STYLE.wrapText
        },
        quote: {
          textColor: data.quote?.textColor || DEFAULT_QUOTE_STYLE.textColor,
          bgColor: data.quote?.bgColor || DEFAULT_QUOTE_STYLE.bgColor,
          borderColor: data.quote?.borderColor || DEFAULT_QUOTE_STYLE.borderColor,
          borderWidth: data.quote?.borderWidth || DEFAULT_QUOTE_STYLE.borderWidth,
          fontSize: data.quote?.fontSize || DEFAULT_QUOTE_STYLE.fontSize,
          padding: data.quote?.padding || DEFAULT_QUOTE_STYLE.padding,
          borderRadius: data.quote?.borderRadius || DEFAULT_QUOTE_STYLE.borderRadius,
          italic: data.quote?.italic !== undefined ? data.quote.italic : DEFAULT_QUOTE_STYLE.italic,
          width: data.quote?.width || DEFAULT_QUOTE_STYLE.width,
          height: data.quote?.height || DEFAULT_QUOTE_STYLE.height,
          showCopyButton: data.quote?.showCopyButton !== undefined ? data.quote.showCopyButton : DEFAULT_QUOTE_STYLE.showCopyButton,
          showDownloadButton: data.quote?.showDownloadButton !== undefined ? data.quote.showDownloadButton : DEFAULT_QUOTE_STYLE.showDownloadButton,
          collapsible: data.quote?.collapsible !== undefined ? data.quote.collapsible : DEFAULT_QUOTE_STYLE.collapsible,
          fontFamily: data.quote?.fontFamily || DEFAULT_QUOTE_STYLE.fontFamily,
          isCodeFont: data.quote?.isCodeFont !== undefined ? data.quote.isCodeFont : DEFAULT_QUOTE_STYLE.isCodeFont,
        },
        link: {
          underlineEnabled: data.link?.underlineEnabled !== undefined ? data.link.underlineEnabled : DEFAULT_LINK_STYLE.underlineEnabled
        },
        button: {
          width: data.button?.width || DEFAULT_BUTTON_STYLE.width,
          height: data.button?.height || DEFAULT_BUTTON_STYLE.height,
          backgroundColor: data.button?.backgroundColor || DEFAULT_BUTTON_STYLE.backgroundColor,
          textColor: data.button?.textColor || DEFAULT_BUTTON_STYLE.textColor,
          borderRadius: data.button?.borderRadius || DEFAULT_BUTTON_STYLE.borderRadius
        },
        showCopyButton: data.showCopyButton !== undefined ? data.showCopyButton : DEFAULT_STYLE_CONFIG.showCopyButton
      };
      callback(config);
    } else {
      callback(DEFAULT_STYLE_CONFIG);
    }
  }).catch((error) => {
    console.error('Error loading initial style config:', error);
    callback(DEFAULT_STYLE_CONFIG);
  });

  // Subscribe to real-time updates
  return onSnapshot(docRef, (docSnap) => {
    if (docSnap.exists()) {
      const data = docSnap.data();
      const config: StyleConfig = {
        general: {
          cardWidth: data.general?.cardWidth || DEFAULT_GENERAL_STYLE.cardWidth,
          cardHeight: data.general?.cardHeight || DEFAULT_GENERAL_STYLE.cardHeight,
          cardFontSize: data.general?.cardFontSize || DEFAULT_GENERAL_STYLE.cardFontSize,
          cardTitleSize: data.general?.cardTitleSize || DEFAULT_GENERAL_STYLE.cardTitleSize,
        },
        code: {
          textColor: data.code?.textColor || DEFAULT_CODE_STYLE.textColor,
          bgColor: data.code?.bgColor || DEFAULT_CODE_STYLE.bgColor,
          opacity: data.code?.opacity || DEFAULT_CODE_STYLE.opacity,
          width: data.code?.width || DEFAULT_CODE_STYLE.width,
          height: data.code?.height || DEFAULT_CODE_STYLE.height,
          fontSize: data.code?.fontSize || DEFAULT_CODE_STYLE.fontSize,
          borderRadius: data.code?.borderRadius || DEFAULT_CODE_STYLE.borderRadius,
          fontFamily: data.code?.fontFamily || DEFAULT_CODE_STYLE.fontFamily,
          showBackground: data.code?.showBackground !== undefined ? data.code.showBackground : DEFAULT_CODE_STYLE.showBackground,
          lineHeight: data.code?.lineHeight || DEFAULT_CODE_STYLE.lineHeight,
          collapsible: data.code?.collapsible !== undefined ? data.code.collapsible : DEFAULT_CODE_STYLE.collapsible,
          showLineNumbers: data.code?.showLineNumbers !== undefined ? data.code.showLineNumbers : DEFAULT_CODE_STYLE.showLineNumbers,
          wrapText: data.code?.wrapText !== undefined ? data.code.wrapText : DEFAULT_CODE_STYLE.wrapText
        },
        quote: {
          textColor: data.quote?.textColor || DEFAULT_QUOTE_STYLE.textColor,
          bgColor: data.quote?.bgColor || DEFAULT_QUOTE_STYLE.bgColor,
          borderColor: data.quote?.borderColor || DEFAULT_QUOTE_STYLE.borderColor,
          borderWidth: data.quote?.borderWidth || DEFAULT_QUOTE_STYLE.borderWidth,
          fontSize: data.quote?.fontSize || DEFAULT_QUOTE_STYLE.fontSize,
          padding: data.quote?.padding || DEFAULT_QUOTE_STYLE.padding,
          borderRadius: data.quote?.borderRadius || DEFAULT_QUOTE_STYLE.borderRadius,
          italic: data.quote?.italic !== undefined ? data.quote.italic : DEFAULT_QUOTE_STYLE.italic,
          width: data.quote?.width || DEFAULT_QUOTE_STYLE.width,
          height: data.quote?.height || DEFAULT_QUOTE_STYLE.height,
          showCopyButton: data.quote?.showCopyButton !== undefined ? data.quote.showCopyButton : DEFAULT_QUOTE_STYLE.showCopyButton,
          showDownloadButton: data.quote?.showDownloadButton !== undefined ? data.quote.showDownloadButton : DEFAULT_QUOTE_STYLE.showDownloadButton,
          collapsible: data.quote?.collapsible !== undefined ? data.quote.collapsible : DEFAULT_QUOTE_STYLE.collapsible,
          fontFamily: data.quote?.fontFamily || DEFAULT_QUOTE_STYLE.fontFamily,
          isCodeFont: data.quote?.isCodeFont !== undefined ? data.quote.isCodeFont : DEFAULT_QUOTE_STYLE.isCodeFont,
        },
        link: {
          underlineEnabled: data.link?.underlineEnabled !== undefined ? data.link.underlineEnabled : DEFAULT_LINK_STYLE.underlineEnabled
        },
        button: {
          width: data.button?.width || DEFAULT_BUTTON_STYLE.width,
          height: data.button?.height || DEFAULT_BUTTON_STYLE.height,
          backgroundColor: data.button?.backgroundColor || DEFAULT_BUTTON_STYLE.backgroundColor,
          textColor: data.button?.textColor || DEFAULT_BUTTON_STYLE.textColor,
          borderRadius: data.button?.borderRadius || DEFAULT_BUTTON_STYLE.borderRadius
        },

        showCopyButton: data.showCopyButton !== undefined ? data.showCopyButton : DEFAULT_STYLE_CONFIG.showCopyButton
      };
      callback(config);
    } else {
      callback(DEFAULT_STYLE_CONFIG);
    }
  }, (error) => {
    console.error('Error subscribing to style config:', error);
    callback(DEFAULT_STYLE_CONFIG);
  });
};
