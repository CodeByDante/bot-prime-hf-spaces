import { Search, X, ArrowUpDown, ChevronsUpDown, Filter } from 'lucide-react';
import { useState } from 'react';
import { toast } from 'sonner';

type SortType = 'random' | 'name' | 'date' | 'pages' | 'modified' | 'views';
type SortDirection = 'asc' | 'desc';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  sortType?: SortType;
  onSortTypeChange?: (sortType: SortType) => void;
  sortDirection?: SortDirection;
  onSortDirectionChange?: (direction: SortDirection) => void;
  onOpenFilter?: () => void;
}

const SORT_LABELS: Record<SortType, string> = {
  random: 'Aleatorio',
  name: 'Nombre',
  date: 'Fecha de creación',
  modified: 'Última modificación',
  pages: 'Páginas',
  views: 'Vistas',
};

export function SearchBar({
  value,
  onChange,
  placeholder = "Buscar manga...",
  sortType = 'random',
  onSortTypeChange,
  sortDirection = 'asc',
  onSortDirectionChange,
  onOpenFilter,
}: SearchBarProps) {
  const [isFocused, setIsFocused] = useState(false);

  const handleClear = () => {
    onChange('');
  };

  const handleCycleSortType = () => {
    const sortTypes: SortType[] = ['modified', 'name', 'date', 'pages', 'views', 'random'];
    const currentIndex = sortTypes.indexOf(sortType);
    const nextIndex = (currentIndex + 1) % sortTypes.length;
    const nextSortType = sortTypes[nextIndex];

    onSortTypeChange?.(nextSortType);

    // Mobile-only toast notification
    if (window.innerWidth < 640) {
      toast.success(`Ordenado por: ${SORT_LABELS[nextSortType]}`, {
        position: 'top-center',
        duration: 1500,
        className: 'bg-purple-900/90 text-white border-purple-500/50',
      });
    }
  };

  const handleToggleSortDirection = () => {
    const newDirection = sortDirection === 'asc' ? 'desc' : 'asc';
    onSortDirectionChange?.(newDirection);

    // Mobile-only toast notification
    if (window.innerWidth < 640) {
      let label = newDirection === 'asc' ? 'Ascendente (A-Z)' : 'Descendente (Z-A)';
      if (sortType === 'views') {
        label = newDirection === 'asc' ? 'Menos vistos primero' : 'Más vistos primero';
      } else if (sortType === 'date' || sortType === 'modified') {
        label = newDirection === 'asc' ? 'Más antiguos primero' : 'Más recientes primero';
      } else if (sortType === 'pages') {
        label = newDirection === 'asc' ? 'Menos páginas' : 'Más páginas';
      }

      toast.success(`Orden: ${label}`, {
        position: 'top-center',
        duration: 1500,
        className: 'bg-purple-900/90 text-white border-purple-500/50',
      });
    }
  };

  const getDirectionLabel = () => {
    if (sortType === 'views') {
      return sortDirection === 'asc' ? 'Menos vistos' : 'Más vistos';
    }
    return sortDirection === 'asc' ? 'ASC' : 'DESC';
  };

  return (
    <div className="w-full flex gap-2 items-center">
      <div className="relative flex-1">
        <Search className={`absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 pointer-events-none ${isFocused ? 'text-purple-400' : 'text-gray-400'
          }`} />
        <input
          type="text"
          placeholder={placeholder}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          className="w-full bg-[#1a1a1a] text-white rounded-lg pl-10 pr-10 py-2.5 text-sm placeholder-gray-400 border border-gray-700/50 focus:border-purple-500 focus:outline-none"
        />
        {value && (
          <button
            onClick={handleClear}
            className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400 hover:text-purple-400 transition-all p-1 hover:scale-125 hover:rotate-90 duration-300"
            title="Limpiar búsqueda"
          >
            <X className="w-4 h-4" />
          </button>
        )}
      </div>

      <button
        onClick={onOpenFilter}
        className="bg-gray-800 hover:bg-gray-700 border border-gray-700 hover:border-purple-500/50 text-white p-2.5 rounded-lg transition-all duration-300 hover:shadow-lg hover:shadow-purple-500/10 group"
        title="Filtrar por categorías"
      >
        <Filter className="w-4 h-4 text-gray-400 group-hover:text-purple-400 transition-colors" />
      </button>

      <button
        onClick={handleCycleSortType}
        className="bg-gradient-to-r from-gray-700/40 to-gray-600/40 hover:from-gray-700/60 hover:to-gray-600/60 border border-gray-600/50 hover:border-purple-500/50 text-white px-2.5 py-2.5 rounded-lg flex items-center justify-center gap-1.5 font-medium text-xs transition-all duration-300 active:scale-95 whitespace-nowrap hover:scale-110 hover:shadow-lg hover:shadow-purple-500/20 hover:border-purple-500"
        title="Cambiar tipo de ordenamiento"
      >
        <ChevronsUpDown className="w-3.5 h-3.5 transition-transform duration-300 hover:rotate-180" />
        <span className="hidden sm:inline">{SORT_LABELS[sortType]}</span>
      </button>

      <button
        onClick={handleToggleSortDirection}
        className="bg-gradient-to-r from-gray-700/40 to-gray-600/40 hover:from-gray-700/60 hover:to-gray-600/60 border border-gray-600/50 hover:border-purple-500/50 text-white px-2.5 py-2.5 rounded-lg flex items-center justify-center gap-1.5 font-medium text-xs transition-all duration-300 active:scale-95 whitespace-nowrap hover:scale-110 hover:shadow-lg hover:shadow-purple-500/20 hover:border-purple-500"
        title={sortDirection === 'asc' ? 'Cambiar a descendente' : 'Cambiar a ascendente'}
      >
        <ArrowUpDown className={`w-3.5 h-3.5 transition-all duration-500 ${sortDirection === 'desc' ? 'rotate-180' : ''} hover:scale-125`} />
        <span className="hidden sm:inline text-[10px]">{getDirectionLabel()}</span>
      </button>
    </div>
  );
}
