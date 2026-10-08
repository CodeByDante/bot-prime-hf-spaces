export interface SearchOptions {
  caseSensitive?: boolean;
  fuzzyMatch?: boolean;
  minChars?: number;
}

function normalizeString(str: string): string {
  return str
    .toLowerCase()
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '');
}

function calculateSimilarity(str1: string, str2: string): number {
  const s1 = normalizeString(str1);
  const s2 = normalizeString(str2);

  if (s1 === s2) return 1;
  if (s1.length < 2 || s2.length < 2) return s1.includes(s2) ? 0.8 : 0;

  const longer = s1.length > s2.length ? s1 : s2;
  const shorter = s1.length > s2.length ? s2 : s1;

  const editDistance = getLevenshteinDistance(shorter, longer);
  return (longer.length - editDistance) / longer.length;
}

function getLevenshteinDistance(s1: string, s2: string): number {
  const costs = [];
  for (let i = 0; i <= s1.length; i++) {
    let lastValue = i;
    for (let j = 0; j <= s2.length; j++) {
      if (i === 0) {
        costs[j] = j;
      } else if (j > 0) {
        let newValue = costs[j - 1];
        if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
          newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
        }
        costs[j - 1] = lastValue;
        lastValue = newValue;
      }
    }
    if (i > 0) costs[s2.length] = lastValue;
  }
  return costs[s2.length];
}

export interface SearchableItem {
  id: string;
  title: string;
  author: string;
  categories?: string[];
  [key: string]: any;
}

export function searchItems<T extends SearchableItem>(
  items: T[],
  query: string,
  options: SearchOptions = {}
): { items: T[]; query: string; resultCount: number } {
  const { minChars = 1, fuzzyMatch = true } = options;

  if (!query.trim() || query.length < minChars) {
    return { items, query, resultCount: items.length };
  }

  const normalizedQuery = normalizeString(query);

  const results = items
    .map((item) => {
      let score = 0;

      const titleScore = calculateSimilarity(item.title, query);
      const authorScore = calculateSimilarity(item.author, query);

      const titleExactMatch = normalizeString(item.title).includes(normalizedQuery) ? 0.3 : 0;
      const authorExactMatch = normalizeString(item.author).includes(normalizedQuery) ? 0.2 : 0;

      let categoryScore = 0;
      let categoryExactMatch = 0;

      if (item.categories && item.categories.length > 0) {
        // Find best matching category
        const catScores = item.categories.map(cat => calculateSimilarity(cat, query));
        categoryScore = Math.max(...catScores);

        // Check for exact substring match in any category
        const catExact = item.categories.some(cat => normalizeString(cat).includes(normalizedQuery));
        categoryExactMatch = catExact ? 0.3 : 0;
      }

      score = Math.max(
        titleScore * 0.6 + titleExactMatch,
        authorScore * 0.4 + authorExactMatch,
        categoryScore * 0.5 + categoryExactMatch
      );

      return { item, score };
    })
    .filter((result) => fuzzyMatch ? result.score > 0.3 : result.score > 0.7)
    .sort((a, b) => b.score - a.score)
    .map((result) => result.item);

  return { items: results, query, resultCount: results.length };
}

export function debounce<T extends (...args: any[]) => any>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout;
  return function executedFunction(...args: Parameters<T>) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}
