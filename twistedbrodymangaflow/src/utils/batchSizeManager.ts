const BATCH_SIZE_STORAGE_KEY = 'imageBatchSize';
const DEFAULT_BATCH_SIZE = 10;

export function saveBatchSize(size: number): void {
  if (size < 0) {
    throw new Error('El tamaño del lote no puede ser negativo');
  }
  localStorage.setItem(BATCH_SIZE_STORAGE_KEY, size.toString());
}

export function getBatchSize(): number {
  const stored = localStorage.getItem(BATCH_SIZE_STORAGE_KEY);
  if (!stored) {
    return DEFAULT_BATCH_SIZE;
  }
  const parsed = parseInt(stored, 10);
  if (isNaN(parsed) || parsed < 0) {
    return DEFAULT_BATCH_SIZE;
  }
  if (parsed >= 999999) {
    return 0;
  }
  return parsed;
}

export function resetBatchSize(): void {
  localStorage.removeItem(BATCH_SIZE_STORAGE_KEY);
}
