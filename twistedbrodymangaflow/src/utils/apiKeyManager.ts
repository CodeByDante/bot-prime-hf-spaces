const USER_API_KEY_STORAGE = 'userApiKey';

export function saveUserApiKey(apiKey: string): void {
  if (!apiKey || apiKey.trim() === '') {
    throw new Error('API key no puede estar vacía');
  }
  localStorage.setItem(USER_API_KEY_STORAGE, apiKey.trim());
}

export function getUserApiKey(): string | null {
  return localStorage.getItem(USER_API_KEY_STORAGE);
}

export function deleteUserApiKey(): void {
  localStorage.removeItem(USER_API_KEY_STORAGE);
}

export function hasUserApiKey(): boolean {
  return !!getUserApiKey();
}
