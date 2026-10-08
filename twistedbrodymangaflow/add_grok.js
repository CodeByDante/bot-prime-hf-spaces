import fs from 'fs';

const files = [
  'src/types/manga.ts',
  'src/services/manga.ts',
  'src/components/SettingsModal.tsx',
  'src/components/SearchResults.tsx',
  'src/components/NewMangaModal.tsx',
  'src/components/NavigationDrawer.tsx',
  'src/components/MoveSectionModal.tsx',
  'src/components/CreateFolderModal.tsx',
  'src/components/MangaCard.tsx',
  'src/App.tsx'
];

files.forEach(f => {
  let content = fs.readFileSync(f, 'utf8');
  // Type change
  content = content.replace(/'flow' \| 'patreon' \| 'onlyfans'/g, "'flow' | 'patreon' | 'onlyfans' | 'grok'");
  
  if (f === 'src/App.tsx') {
    content = content.replace(/sec === 'flow' \|\| sec === 'patreon' \|\| sec === 'onlyfans'/g, "sec === 'flow' || sec === 'patreon' || sec === 'onlyfans' || sec === 'grok'");
  }
  
  fs.writeFileSync(f, content);
});

console.log('done replace types');
