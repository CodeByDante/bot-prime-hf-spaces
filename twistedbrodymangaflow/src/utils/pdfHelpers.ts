import jsPDF from 'jspdf';
import { convertImageToFormat } from './imageOptimization';

export async function generatePDFFromPages(
  pages: string[],
  formats: string[],
  mangaTitle: string,
  downloadFormat: 'png' | 'jpg' | 'webp' | 'original',
  onProgress?: (progress: number) => void
): Promise<void> {
  const pdf = new jsPDF({
    orientation: 'portrait',
    unit: 'px',
    format: [1, 1],
    compress: true,
  });

  let isFirstPage = true;

  for (let i = 0; i < pages.length; i++) {
    try {
      let imageData: string;

      if (downloadFormat === 'original') {
        const response = await fetch(pages[i]);
        const blob = await response.blob();
        imageData = await blobToBase64(blob);
      } else {
        const blob = await convertImageToFormat(pages[i], downloadFormat);
        imageData = await blobToBase64(blob);
      }

      const img = await loadImage(imageData);
      const imgWidth = img.width;
      const imgHeight = img.height;

      if (isFirstPage) {
        pdf.internal.pageSize.setWidth(imgWidth);
        pdf.internal.pageSize.setHeight(imgHeight);
        isFirstPage = false;
      } else {
        pdf.addPage([imgWidth, imgHeight]);
      }

      const format = downloadFormat === 'original' ? (formats[i] === 'jpg' ? 'JPEG' : 'PNG') :
                     downloadFormat === 'jpg' ? 'JPEG' : 'PNG';

      pdf.addImage(imageData, format, 0, 0, imgWidth, imgHeight);

      const progress = Math.round(((i + 1) / pages.length) * 100);
      onProgress?.(progress);
    } catch (error) {
      console.error(`Error processing page ${i + 1}:`, error);
    }
  }

  const formatLabel = downloadFormat === 'original' ? 'original' : downloadFormat.toUpperCase();
  pdf.save(`${mangaTitle.replace(/[^a-z0-9]/gi, '_')}_${formatLabel}.pdf`);
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

function loadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}
