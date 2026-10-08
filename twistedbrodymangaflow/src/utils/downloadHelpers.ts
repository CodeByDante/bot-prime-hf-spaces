import { convertImageToFormat } from './imageOptimization';

export async function downloadImageAs(
  imageUrl: string,
  fileName: string,
  format: 'png' | 'jpg' | 'webp' | 'original',
  originalFormat?: string
): Promise<void> {
  try {
    if (format === 'original') {
      const response = await fetch(imageUrl);
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${fileName}.${originalFormat || 'jpg'}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } else {
      const blob = await convertImageToFormat(imageUrl, format);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${fileName}.${format}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }
  } catch (error) {
    console.error(`Error downloading image as ${format}:`, error);
    throw error;
  }
}

export async function downloadAllPagesAsZip(
  pages: string[],
  formats: string[],
  mangaTitle: string,
  downloadFormat: 'png' | 'jpg' | 'webp' | 'original',
  onProgress?: (progress: number) => void
): Promise<void> {
  const JSZip = (await import('jszip')).default;
  const zip = new JSZip();
  const BATCH_SIZE = 10;

  for (let batchStart = 0; batchStart < pages.length; batchStart += BATCH_SIZE) {
    const batchEnd = Math.min(batchStart + BATCH_SIZE, pages.length);
    const batchPromises = [];

    for (let i = batchStart; i < batchEnd; i++) {
      const promise = (async () => {
        try {
          let blob: Blob;
          let ext: string;

          if (downloadFormat === 'original') {
            const response = await fetch(pages[i]);
            blob = await response.blob();
            ext = formats[i] || 'jpg';
          } else {
            blob = await convertImageToFormat(pages[i], downloadFormat);
            ext = downloadFormat;
          }

          return { index: i, blob, ext };
        } catch (error) {
          console.error(`Error processing page ${i + 1}:`, error);
          return null;
        }
      })();

      batchPromises.push(promise);
    }

    const results = await Promise.all(batchPromises);

    for (const result of results) {
      if (result) {
        zip.file(`pagina_${(result.index + 1).toString().padStart(3, '0')}.${result.ext}`, result.blob);
      }
    }

    const progress = Math.round(((batchEnd / pages.length) * 100));
    onProgress?.(progress);
  }

  const content = await zip.generateAsync({ type: 'blob' });
  const url = URL.createObjectURL(content);
  const a = document.createElement('a');
  a.href = url;
  const formatLabel = downloadFormat === 'original' ? 'original' : downloadFormat.toUpperCase();
  a.download = `${mangaTitle.replace(/[^a-z0-9]/gi, '_')}_${formatLabel}.zip`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
