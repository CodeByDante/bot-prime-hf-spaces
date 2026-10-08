export interface ContentBlock {
  id: string;
  type: 'text' | 'markdown' | 'raw-markdown';
  content: any;
}

export interface LinkGroup {
  id: string;
  title: string;
  visitUrl?: string;
  downloadUrl?: string;
}

export interface DataItem {
  id: string;
  icon?: string;
  cardStyle?: 'bordered' | 'transparent' | 'filled'; // New field for card styling
  title: string;
  summary: string;
  content: string; // Kept for backward compatibility and search
  blocks?: ContentBlock[]; // New structure for multiple blocks
  downloadUrl?: string;
  visitUrl?: string;
  linkGroups?: LinkGroup[];
  createdAt: number;
  updatedAt?: number; // Added for modification date sorting
  tags: string[];
  categories?: string[];
  isFolder?: boolean;
  isPinned?: boolean;
  parentId?: string | null;
  isDeleted?: boolean;
  deletedAt?: number;
}

export type ViewState = 'LIST' | 'DETAIL' | 'CREATE' | 'EDIT';

export interface AlertMessage {
  type: 'success' | 'error' | 'info';
  text: string;
}