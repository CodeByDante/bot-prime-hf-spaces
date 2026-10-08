import { MangaCard } from './MangaCard';
import { Manga } from '../types/manga';

interface MangaItem {
  id: string;
  title: string;
  author: string;
  chapterCount: number;
  pageCount: number;
  thumbnail?: string;
  manga?: Manga;
}

interface MangaGridProps {
  items: MangaItem[];
  onSelectComic?: (id: string) => void;
  onEditManga?: (manga: Manga) => void;
  onDeleteManga?: (id: string) => void;
}

export function MangaGrid({ items, onSelectComic, onEditManga, onDeleteManga }: MangaGridProps) {
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-1.5 sm:gap-2 md:gap-3 w-full justify-center items-start">
      {items.map((item) => (
        <MangaCard
          key={item.id}
          id={item.id}
          title={item.title}
          author={item.author}
          pageCount={item.pageCount}
          thumbnail={item.thumbnail}
          manga={item.manga}
          onSelect={onSelectComic}
          onEdit={onEditManga}
          onDelete={onDeleteManga}
        />
      ))}
    </div>
  );
}
