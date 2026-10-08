export interface OptimizedImage {
  thumbnail: string;
  original: string; // Now stores the originalBase64 to avoid redundancy
  webpDisplay: string;
  webpCover: string; // Now stores the webpDisplay to avoid redundancy
  originalFormat: string;
  originalBase64: string;
  originalUnmodified: string;
}

const THUMBNAIL_WIDTH = 400;
const DISPLAY_WIDTH = 1200;

// Helper to resize and convert image using ImageBitmap
const resizeAndConvertBitmap = (
  bitmap: ImageBitmap,
  maxWidth: number,
  mimeType: string,
  quality: number
): string => {
  const canvas = document.createElement('canvas');
  let { width, height } = bitmap;

  if (width > maxWidth) {
    height = (height * maxWidth) / width;
    width = maxWidth;
  }

  canvas.width = width;
  canvas.height = height;

  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  if (!ctx) throw new Error('Failed to get canvas context');

  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(bitmap, 0, 0, width, height);

  return canvas.toDataURL(mimeType, quality);
};

export async function processImage(file: File, index?: number, total?: number): Promise<OptimizedImage> {
  // 1. Read file to base64
  const originalBase64 = await getOriginalBase64(file);
  const originalFormat = getFileExtension(file);

  try {
    // 2. Send to server for processing
    const response = await fetch('/api/process-image', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: originalBase64,
        name: file.name,
        index,
        total
      }),
    });

    if (!response.ok) {
      throw new Error(`Server processing failed: ${response.statusText}`);
    }

    const result = await response.json();

    if (!result.success || !result.data) {
      throw new Error('Invalid response from processing server');
    }

    // 3. Construct OptimizedImage object
    return {
      thumbnail: result.data.thumbnail,
      original: originalBase64, // Keep original for HD upload
      webpDisplay: result.data.webp, // Server processed WebP
      webpCover: result.data.webp,
      originalFormat,
      originalBase64,
      originalUnmodified: originalBase64
    };

  } catch (error) {
    console.error('Error processing image on server, falling back to local:', error);
    // You could implement a fallback here if server fails, 
    // but for now we throw to let the user know something is wrong with the server connection
    throw error;
  }
}

// Deprecated/Unused but kept if exported elsewhere (though we are replacing the file so we can remove if not used elsewhere)
// We'll keep getOriginalBase64 and getFileExtension as they are useful helpers

export async function getOriginalBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target?.result as string);
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

export function getFileExtension(file: File): string {
  const mimeType = file.type;
  if (mimeType === 'image/png') return 'png';
  if (mimeType === 'image/jpeg') return 'jpg';
  if (mimeType === 'image/gif') return 'gif';
  if (mimeType === 'image/webp') return 'webp';

  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext && ['png', 'jpg', 'jpeg', 'gif', 'webp'].includes(ext)) {
    return ext === 'jpeg' ? 'jpg' : ext;
  }

  return 'jpg';
}

export async function convertImageToFormat(
  imageUrl: string,
  format: 'png' | 'jpg' | 'webp',
  quality: number = 0.92
): Promise<Blob> {
  // For external URLs we still need to load via fetch or Image, but for local blobs/processing we might try bitmap if possible.
  // Since this takes a URL, we'll fetch it to a blob then use bitmap for speed if possible, or fallback to Image.
  // Actually, standard Image approach is safer for cross-origin URLs if CORS allows, but let's stick to standard efficient pattern.

  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = async () => {
      try {
        const bitmap = await createImageBitmap(img);
        const canvas = document.createElement('canvas');
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;

        const ctx = canvas.getContext('2d');
        if (!ctx) throw new Error('Failed to get canvas context');

        ctx.drawImage(bitmap, 0, 0);
        bitmap.close();

        const mimeType = format === 'png' ? 'image/png' :
          format === 'jpg' ? 'image/jpeg' :
            'image/webp';

        canvas.toBlob(
          (blob) => {
            if (blob) resolve(blob);
            else reject(new Error('Failed to create blob'));
          },
          mimeType,
          quality
        );
      } catch (e) {
        reject(e);
      }
    };
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = imageUrl;
  });
}

export function createImageElement(src: string, alt: string): HTMLImageElement {
  const img = document.createElement('img');
  img.src = src;
  img.alt = alt;
  img.loading = 'lazy';
  img.decoding = 'async';
  return img;
}

export async function detectImageOrientation(imageUrl: string): Promise<'portrait' | 'landscape' | 'square'> {
  // Use a quick image load
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    img.onload = () => {
      const aspectRatio = img.width / img.height;
      if (aspectRatio < 0.9) resolve('portrait');
      else if (aspectRatio > 1.1) resolve('landscape');
      else resolve('square');
    };
    img.onerror = () => reject(new Error('Failed to load image'));
    img.src = imageUrl;
  });
}
