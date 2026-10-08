import { OptimizedImage } from './imageOptimization';

export function parseLinkText(text: string): OptimizedImage[] {
  const pagesMap = new Map<number, Partial<OptimizedImage>>();

  const lines = text.split('\n');
  let currentSection = ''; // 'WEB P LINKS' | 'ORIGINAL LINKS'
  let currentTarget = 'Hugging Face'; // Default to Hugging Face so raw lists work

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed.includes('---- WEB P LINKS ----')) {
      currentSection = 'WEB P LINKS';
      continue;
    }
    
    if (trimmed.includes('---- ORIGINAL LINKS ----')) {
      currentSection = 'ORIGINAL LINKS';
      continue;
    }

    if (trimmed.includes('---- VIDEO LINKS ----')) {
      currentSection = 'VIDEO LINKS';
      continue;
    }

    if (trimmed.includes('Para Hugging Face (Público):')) {
      currentTarget = 'Hugging Face';
      continue;
    }

    if (trimmed.includes('Para tu PC Local (Pruebas):')) {
      currentTarget = 'Local';
      continue;
    }

    // Process only Hugging Face links
    if (currentTarget === 'Hugging Face' && trimmed.match(/^\(\d+\)\s+.*?\s+=\s+http/)) {
      const match = trimmed.match(/^\(\d+\)\s+(.*?)\s+=\s+(http.*)$/);
      if (match) {
        const filename = match[1];
        const urlEnd = match[2].trim();
        
        const isVideo = currentSection === 'VIDEO LINKS' || filename.toLowerCase().endsWith('.mp4');
        const url = isVideo && !urlEnd.includes('format=mp4') 
          ? urlEnd + (urlEnd.includes('?') ? '&format=mp4' : '?format=mp4')
          : urlEnd;

        // Extract the number from the start of the line (e.g., "(1) ") or fallback to filename
        const prefixMatch = trimmed.match(/^\((\d+)\)/);
        let pageNum = prefixMatch ? parseInt(prefixMatch[1], 10) : 0;
        
        if (!pageNum) {
          const numMatch = filename.match(/^(\d+)/);
          pageNum = numMatch ? parseInt(numMatch[1], 10) : 0;
        }

        if (!pagesMap.has(pageNum)) {
          pagesMap.set(pageNum, {
            originalFormat: 'webp',
            originalBase64: '', // Indicate this is already uploaded
          });
        }
        
        const pageData = pagesMap.get(pageNum)!;

        // Force .webp extension if it isn't one (though original might not be, we don't care that much here, just use 'webp')

        if (currentSection === 'WEB P LINKS') {
          pageData.thumbnail = url;
          pageData.webpDisplay = url;
          pageData.webpCover = url;
        } else if (currentSection === 'ORIGINAL LINKS') {
          pageData.original = url;
          pageData.originalUnmodified = url;
        } else {
          // If no section explicitly defined, assign to both
          pageData.thumbnail = url;
          pageData.webpDisplay = url;
          pageData.webpCover = url;
          pageData.original = url;
          pageData.originalUnmodified = url;
        }
      }
    }
  }

  // Convert map to sorted array
  const sortedPages: OptimizedImage[] = [];
  const sortedKeys = Array.from(pagesMap.keys()).sort((a, b) => a - b);
  
  for (const key of sortedKeys) {
    const pageData = pagesMap.get(key);
    if (pageData) {
      if (!pageData.original && pageData.thumbnail) {
        // Provide fallback if original is missing
        pageData.original = pageData.thumbnail;
        pageData.originalUnmodified = pageData.thumbnail;
      } else if (!pageData.thumbnail && pageData.original) {
        // Provide fallback if thumbnail is missing (e.g., only ORIGINAL LINKS provided for JPGs)
        pageData.thumbnail = pageData.original;
        pageData.webpDisplay = pageData.original;
        pageData.webpCover = pageData.original;
      }
      
      if (pageData.thumbnail && pageData.original) {
        sortedPages.push(pageData as OptimizedImage);
      }
    }
  }

  return sortedPages;
}
