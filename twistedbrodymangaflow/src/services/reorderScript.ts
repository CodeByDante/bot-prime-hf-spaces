import { db } from '../lib/firebase';
import { collection, getDocs, doc, updateDoc, query, where } from 'firebase/firestore';

export type ReorderProgressCallback = (currentManga: string, current: number, total: number) => void;

interface PageData {
  url: string;
  originalUrl: string;
  format: string;
  pageNum: number;
}

export async function reorderAllMangasPages(onProgress?: ReorderProgressCallback): Promise<{ updated: number, errors: number }> {
  let updatedCount = 0;
  let errorCount = 0;

  try {
    const mangasRef = collection(db, 'mangas');
    const mangasSnap = await getDocs(mangasRef);
    const mangas = mangasSnap.docs;
    
    let processed = 0;

    for (const mangaDoc of mangas) {
      const mangaData = mangaDoc.data();
      const mangaId = mangaDoc.id;
      
      processed++;
      if (onProgress) {
        onProgress(mangaData.title || mangaId, processed, mangas.length);
      }

      try {
        const chaptersQuery = query(collection(db, 'chapters'), where('manga_id', '==', mangaId));
        const chaptersSnap = await getDocs(chaptersQuery);

        for (const chapterDoc of chaptersSnap.docs) {
          const chapterData = chapterDoc.data();
          const pages: string[] = chapterData.pages || [];
          const originalPages: string[] = chapterData.original_pages || [];
          const pageFormats: string[] = chapterData.page_formats || [];

          if (pages.length === 0) continue;

          // Gather page data to sort
          const mappedPages: PageData[] = [];
          
          for (let i = 0; i < pages.length; i++) {
            const url = pages[i];
            const originalUrl = originalPages[i] || url;
            const format = pageFormats[i] || 'webp';
            
            // Check if it's a Hugging Face URL
            if (url.includes('hf.space')) {
              try {
                // Change out URL to use proxy
                const proxyUrl = url.replace('https://codebydante-brodyfilestreambot.hf.space', '/hf-proxy');
                
                // Fetch header
                const response = await fetch(proxyUrl, { method: 'HEAD' });
                
                if (response.ok) {
                  const contentDisposition = response.headers.get('content-disposition');
                  let pageNum = -1;
                  
                  if (contentDisposition) {
                    // Extract filename="10.jpg_waifu..." -> "10.jpg_waifu..."
                    const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
                    if (filenameMatch) {
                      const filename = filenameMatch[1];
                      const numMatch = filename.match(/^(\d+)/);
                      if (numMatch) {
                        pageNum = parseInt(numMatch[1], 10);
                      }
                    }
                  }
                  
                  // if we couldn't parse it, fallback to index
                  mappedPages.push({
                    url,
                    originalUrl,
                    format,
                    pageNum: pageNum !== -1 ? pageNum : i
                  });
                } else {
                  // Fallback to index if request fails
                  mappedPages.push({ url, originalUrl, format, pageNum: i });
                }
              } catch (e) {
                console.error(`Failed to fetch headers for ${url}`, e);
                mappedPages.push({ url, originalUrl, format, pageNum: i });
              }
            } else {
              // Not a HF url, just keep relative order
              mappedPages.push({ url, originalUrl, format, pageNum: i });
            }
          }

          // Sort mapped pages
          mappedPages.sort((a, b) => a.pageNum - b.pageNum);

          // Update chapter document with new arrays
          const newPages = mappedPages.map(p => p.url);
          const newOriginalPages = mappedPages.map(p => p.originalUrl);
          const newPageFormats = mappedPages.map(p => p.format);

          await updateDoc(doc(db, 'chapters', chapterDoc.id), {
            pages: newPages,
            original_pages: newOriginalPages,
            page_formats: newPageFormats,
          });
        }
        
        updatedCount++;
      } catch (err) {
        console.error(`Error processing chapter for manga ${mangaId}`, err);
        errorCount++;
      }
    }
    
    return { updated: updatedCount, errors: errorCount };
  } catch (error) {
    console.error("Error fetching mangas for reorder: ", error);
    throw error;
  }
}
