import { parseLinkText } from './src/utils/linkParser';
const text = `
==== Jungle_Party_1_(1) ====

---- WEB P LINKS ----

🚀 Para Hugging Face (Público):
(1) pagina_001.webp = https://codebydante-brodyfilestreambot.hf.space/stream/778?hash=30af00
(2) pagina_002.webp = https://codebydante-brodyfilestreambot.hf.space/stream/745?hash=1ffd23

🖥 Para tu PC Local (Pruebas):

---- ORIGINAL LINKS ----

🚀 Para Hugging Face (Público):
(1) pagina_001.webp = https://codebydante-brodyfilestreambot.hf.space/stream/778?hash=30af00_orig
(2) pagina_002.webp = https://codebydante-brodyfilestreambot.hf.space/stream/745?hash=1ffd23_orig
`;
console.log(JSON.stringify(parseLinkText(text), null, 2));
