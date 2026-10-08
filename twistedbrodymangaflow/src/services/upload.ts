import { getBatchSize } from '../utils/batchSizeManager';

const UPLOAD_API_URL = 'https://codebydante-brodyfilestreambot.hf.space/upload';

export interface UploadResponse {
  success: boolean;
  message_id?: number;
  hash?: string;
  url: string;
}

// Convert base64 to File
function base64ToFile(base64: string, filename: string): File {
  const arr = base64.split(',');
  const mimeMatch = arr[0].match(/:(.*?);/);
  const mime = mimeMatch ? mimeMatch[1] : 'image/jpeg';
  const bstr = atob(arr[arr.length - 1]);
  let n = bstr.length;
  const u8arr = new Uint8Array(n);
  while(n--){
      u8arr[n] = bstr.charCodeAt(n);
  }
  return new File([u8arr], filename, {type:mime});
}

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export async function uploadImage(base64Image: string, name?: string, retries = 3): Promise<{ data: { url: string } }> {
  const filename = name ? `${name}.jpg` : 'image.jpg';
  const file = base64ToFile(base64Image, filename);
  
  const formData = new FormData();
  formData.append('file', file);

  let attempt = 0;
  while (attempt < retries) {
    attempt++;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 60000); // 60s timeout due to bot wake up

    try {
      const response = await fetch(UPLOAD_API_URL, {
        method: 'POST',
        body: formData,
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();
        if (response.status >= 500 && attempt < retries) {
          console.warn(`Upload error ${response.status}. Reintentando ${attempt}/${retries}...`);
          await delay(2000 * attempt);
          continue;
        }
        throw new Error(`Error al subir imagen: ${errorText}`);
      }

      const data: UploadResponse = await response.json();

      if (!data.success || !data.url) {
        throw new Error('Upload failed: Invalid server response');
      }

      return {
        data: {
          url: data.url
        }
      };

    } catch (error: any) {
      clearTimeout(timeoutId);
      
      const isNetworkOrTimeout = error.name === 'AbortError' || 
                                 error.message?.includes('network') || 
                                 error.message?.includes('fetch') ||
                                 error.message?.includes('Failed to fetch');

      if (isNetworkOrTimeout && attempt < retries) {
        console.warn(`Upload timeout/network error. Reintentando ${attempt}/${retries}...`, error?.message);
        await delay(2000 * attempt);
        continue;
      }

      if (error.name === 'AbortError') {
        throw new Error('La conexión al servidor tardó demasiado (Timeout).');
      }

      if (attempt >= retries) {
        throw error;
      }
    }
  }

  throw new Error('No se pudo subir la imagen tras varios intentos.');
}

export async function uploadMultipleImages(
  base64Images: string[],
  namePrefix?: string,
  onProgress?: (current: number, total: number) => void
): Promise<{ data: { url: string } }[]> {
  const BATCH_SIZE = getBatchSize() || 5; 
  const results: { data: { url: string } }[] = [];

  for (let i = 0; i < base64Images.length; i += BATCH_SIZE) {
    const batch = base64Images.slice(i, i + BATCH_SIZE);
    const uploadPromises = batch.map((image, batchIndex) => {
      const globalIndex = i + batchIndex;
      const name = namePrefix ? `${namePrefix}_${globalIndex + 1}` : undefined;
      return uploadImage(image, name);
    });

    const batchResults = await Promise.all(uploadPromises);
    results.push(...batchResults);

    if (onProgress) {
      onProgress(Math.min(i + BATCH_SIZE, base64Images.length), base64Images.length);
    }

    if (i + BATCH_SIZE < base64Images.length) {
      await delay(1000); 
    }
  }

  return results;
}
