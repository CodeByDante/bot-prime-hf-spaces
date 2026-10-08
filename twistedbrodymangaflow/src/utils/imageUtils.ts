
// Helper to determine if we are in development mode
const isDev = import.meta.env.DEV;

// Get the base API URL (handles both dev and prod scenarios)
const getApiBaseUrl = () => {
    if (isDev) return 'http://localhost:7860';
    return ''; // Relative path for production
};

/**
 * Generates an optimized URL for a thumbnail image.
 * Uses the backend proxy to resize the image to a width suitable for cards (e.g., 600px for high DPI).
 */
export const getThumbnailUrl = (originalUrl?: string): string | undefined => {
    if (!originalUrl) return undefined;

    // If it's already a local asset or blob, return as is
    if (originalUrl.startsWith('blob:') || originalUrl.startsWith('data:')) {
        return originalUrl;
    }

    const baseUrl = getApiBaseUrl();
    const params = new URLSearchParams({
        url: originalUrl,
        width: '600', // High DPI for ~300px card
        quality: '85',
        format: 'webp'
    });

    return `${baseUrl}/api/image-proxy?${params.toString()}`;
};

/**
 * Generates a URL for the reader.
 * Currently returns the original URL but proxied to get backend caching headers.
 * Does NOT resize to preserve maximum quality.
 */
export const getReaderUrl = (originalUrl: string, format?: string): string => {
    if (!originalUrl) return '';

    // If it's already a local asset or blob, return as is
    if (originalUrl.startsWith('blob:') || originalUrl.startsWith('data:')) {
        return originalUrl;
    }

    const baseUrl = getApiBaseUrl();
    // We only pass the URL to proxy it for caching headers, no resizing
    const params = new URLSearchParams({
        url: originalUrl
    });

    if (format) {
        params.append('format', format);
    }

    return `${baseUrl}/api/image-proxy?${params.toString()}`;
};
