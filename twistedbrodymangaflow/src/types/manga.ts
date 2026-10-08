export interface Manga {
  id: string;
  title: string;
  author: string;
  description: string;
  thumbnail_url: string | null;
  cover_url: string | null;
  status: string;
  rating: number;
  views: number;
  created_at: string;
  updated_at: string;
  is_decensored?: boolean;
  is_bn?: boolean;
  is_color?: boolean;
  is_folder?: boolean;
  folder_id?: string;
  categories?: Category[];
  chapters?: Chapter[];
  external_links?: Array<{ name: string; url: string }>;
  is_deleted?: boolean;
  deleted_at?: string;
  section?: 'flow' | 'patreon' | 'onlyfans' | 'grok';
}

export interface Category {
  id: string;
  name: string;
  type?: 'character' | 'series' | 'genre' | 'tag' | 'other';
  created_at: string;
}

export interface Chapter {
  id: string;
  manga_id: string;
  number: number;
  title: string;
  pages: string[];
  page_formats?: string[];
  original_pages?: string[];
  created_at: string;
  updated_at: string;
}

export interface MangaCategory {
  manga_id: string;
  category_id: string;
}
