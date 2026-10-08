import { getUserApiKey } from '../utils/apiKeyManager';
import { getBatchSize } from '../utils/batchSizeManager';

const IMGBB_API_KEY = '90ba8efe6890e9e76175089dc182a22a';
const IMGBB_UPLOAD_URL = 'https://api.imgbb.com/1/upload';

export interface ImgBBResponse {
  success: boolean;
  data: {
    url: string;
    display_url: string;
    thumb: {
      url: string;
    };
  };
}

function getActiveApiKey(): string {
  const userApiKey = getUserApiKey();
  return userApiKey || IMGBB_API_KEY;
}

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export async function uploadToImgBB(base64Image: string, name?: string, retries = 3): Promise<ImgBBResponse> {
  const base64Data = base64Image.includes(',')
    ? base64Image.split(',')[1]
    : base64Image;

  const apiKey = getActiveApiKey();
  const url = `${IMGBB_UPLOAD_URL}?key=${apiKey}`;

  const formData = new FormData();
  formData.append('image', base64Data);

  if (name) {
    formData.append('name', name);
  }

  let attempt = 0;
  while (attempt < retries) {
    attempt++;
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000); // 30 segundos timeout

    try {
      const response = await fetch(url, {
        method: 'POST',
        body: formData,
        signal: controller.signal
      });
      clearTimeout(timeoutId);

      if (!response.ok) {
        const errorText = await response.text();

        if (response.status === 429 || errorText.includes('rate limit')) {
          throw new Error('API_BURNED');
        }

        if (response.status === 403 || response.status === 401) {
          throw new Error('API_INVALID_KEY');
        }

        if (response.status >= 500 && attempt < retries) {
          console.warn(`ImgBB error ${response.status}. Reintentando ${attempt}/${retries}...`);
          await delay(1000 * attempt);
          continue;
        }

        throw new Error(`Error al subir imagen a ImgBB: ${errorText}`);
      }

      const data = await response.json();

      if (!data.success) {
        if (attempt < retries) {
          console.warn(`ImgBB success false. Reintentando ${attempt}/${retries}...`);
          await delay(1000 * attempt);
          continue;
        }
        throw new Error('API_BURNED');
      }

      return data;

    } catch (error: any) {
      clearTimeout(timeoutId);
      
      const isNetworkOrTimeout = error.name === 'AbortError' || 
                                 error.message?.includes('network') || 
                                 error.message?.includes('fetch') ||
                                 error.message?.includes('Failed to fetch');

      if (isNetworkOrTimeout && attempt < retries) {
        console.warn(`ImgBB timeout/network error. Reintentando ${attempt}/${retries}...`, error?.message);
        await delay(1000 * attempt);
        continue;
      }

      if (error.message === 'API_BURNED' || error.message === 'API_INVALID_KEY') {
        throw error;
      }

      if (error.name === 'AbortError') {
        throw new Error('La conexión con ImgBB tardó demasiado (Timeout).');
      }

      if (attempt >= retries) {
        throw error;
      }
    }
  }

  throw new Error('No se pudo subir la imagen a ImgBB tras varios intentos.');
}

export async function uploadMultipleToImgBB(
  base64Images: string[],
  namePrefix?: string,
  onProgress?: (current: number, total: number) => void
): Promise<ImgBBResponse[]> {
  const BATCH_SIZE = getBatchSize();
  const results: ImgBBResponse[] = [];

  if (BATCH_SIZE === 0 || BATCH_SIZE >= base64Images.length) {
    const uploadPromises = base64Images.map((image, index) => {
      const name = namePrefix ? `${namePrefix}_${index + 1}` : undefined;
      return uploadToImgBB(image, name);
    });

    const allResults = await Promise.all(uploadPromises);
    results.push(...allResults);

    if (onProgress) {
      onProgress(base64Images.length, base64Images.length);
    }
  } else {
    for (let i = 0; i < base64Images.length; i += BATCH_SIZE) {
      const batch = base64Images.slice(i, i + BATCH_SIZE);
      const uploadPromises = batch.map((image, batchIndex) => {
        const globalIndex = i + batchIndex;
        const name = namePrefix ? `${namePrefix}_${globalIndex + 1}` : undefined;
        return uploadToImgBB(image, name);
      });

      const batchResults = await Promise.all(uploadPromises);
      results.push(...batchResults);

      if (onProgress) {
        onProgress(Math.min(i + BATCH_SIZE, base64Images.length), base64Images.length);
      }

      if (i + BATCH_SIZE < base64Images.length) {
        await delay(500); // Pequeña pausa entre lotes para evitar bloqueos
      }
    }
  }

  return results;
}
