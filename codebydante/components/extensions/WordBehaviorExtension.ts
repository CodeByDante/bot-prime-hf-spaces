import { Extension } from '@tiptap/core';
import { Plugin, PluginKey } from 'prosemirror-state';

export const WordBehaviorExtension = Extension.create({
    name: 'wordBehavior',

    addProseMirrorPlugins() {
        return [
            new Plugin({
                key: new PluginKey('wordBehaviorPasteHandler'),
                props: {
                    transformPastedHTML(html) {
                        // Limpia divs vacíos y saltos dobles innecesarios generados al copiar de webs
                        let cleaned = html.replace(/<div[^>]*>\s*<\/div>/gi, '');
                        // Reemplaza dobles br por un párrafo nuevo y ordenado
                        cleaned = cleaned.replace(/(<br\s*\/?>\s*){2,}/gi, '</p><p>');
                        // Elimina la proliferación de párrafos vacíos pegados accidentalmente
                        cleaned = cleaned.replace(/(<p>\s*<\/p>\s*){2,}/gi, '<p></p>');
                        // Quita los espacios &nbsp; inútiles al principio o fin de fragmentos
                        cleaned = cleaned.replace(/&nbsp;/g, ' ');

                        return cleaned;
                    }
                }
            })
        ];
    },

    addKeyboardShortcuts() {
        return {
            // Shift-Enter asegura un hard break sin romper el bloque estructural actual
            'Shift-Enter': () => {
                return this.editor.commands.setHardBreak();
            },
            
            // Comportamiento de sangría al estilo procesador de textos para listas
            'Tab': () => {
                if (this.editor.isActive('listItem')) {
                    return this.editor.commands.sinkListItem('listItem');
                }
                // Previene que inserte un tabulador como espacio manual si no está en un bloque soportado
                // Si preferimos que "Tab" ponga un espacio literal en párrafos, retornamos false
                return false;
            },
            
            'Shift-Tab': () => {
                if (this.editor.isActive('listItem')) {
                    return this.editor.commands.liftListItem('listItem');
                }
                return false;
            },

            'Control-Space': () => {
                const { state } = this.editor;
                const { selection } = state;
                const { $from, empty } = selection;

                // Si estamos al inicio de un punto de lista
                if (empty && this.editor.isActive('listItem') && $from.parentOffset === 0) {
                    // Calculamos la posición exacta antes del listItem
                    const pos = $from.before($from.depth - 1);
                    
                    // Insertamos un párrafo vacío y nos aseguramos de que no se convierta en lista
                    this.editor.chain()
                        .focus()
                        .insertContentAt(pos, { type: 'paragraph' })
                        .run();
                    return true;
                }
                return false;
            }
        };
    }
});
