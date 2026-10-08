import React, { useState, useRef, useEffect } from 'react';
import { Editor } from '@tiptap/react';

interface EditorSelectionWrapperProps {
    editor: Editor | null;
    children: React.ReactNode;
    onBackgroundClick?: () => void;
}

interface SelectionBox {
    startX: number;
    startY: number;
    endX: number;
    endY: number;
}

export const EditorSelectionWrapper: React.FC<EditorSelectionWrapperProps> = ({ editor, children, onBackgroundClick }) => {
    const [isSelecting, setIsSelecting] = useState(false);
    const [selectionBox, setSelectionBox] = useState<SelectionBox | null>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const handleMouseDown = (e: React.MouseEvent) => {
        if (!editor || !containerRef.current) return;

        // Only start selection if clicking on the container background, not on content
        // We check if the target is the container itself or the ProseMirror editor div (but not its children)
        // A simple heuristic is to check if the target has specific classes or if it's not a text node wrapper
        // But the user specified: "Si el usuario hace clic y arrastra en un área vacía del editor"

        // Let's check if the click target is the main editor container or the ProseMirror element directly
        const target = e.target as HTMLElement;
        const isContent = target.closest('.ProseMirror > *'); // Clicking on a block

        if (isContent) {
            return; // Allow normal text selection
        }

        // Only trigger on double click (and hold)
        if (e.detail !== 2) {
            return;
        }

        setIsSelecting(true);
        const rect = containerRef.current.getBoundingClientRect();
        const startX = e.clientX - rect.left;
        const startY = e.clientY - rect.top;

        setSelectionBox({
            startX,
            startY,
            endX: startX,
            endY: startY
        });
    };

    const handleMouseMove = (e: React.MouseEvent) => {
        if (!isSelecting || !selectionBox || !containerRef.current) return;

        const rect = containerRef.current.getBoundingClientRect();
        const currentX = e.clientX - rect.left;
        const currentY = e.clientY - rect.top;

        setSelectionBox({
            ...selectionBox,
            endX: currentX,
            endY: currentY
        });
    };

    const handleMouseUp = () => {
        if (!isSelecting || !selectionBox || !editor || !containerRef.current) {
            setIsSelecting(false);
            setSelectionBox(null);
            return;
        }

        // Calculate intersection and select blocks
        const rect = containerRef.current.getBoundingClientRect();

        // Normalize coordinates
        const left = Math.min(selectionBox.startX, selectionBox.endX);
        const top = Math.min(selectionBox.startY, selectionBox.endY);
        const right = Math.max(selectionBox.startX, selectionBox.endX);
        const bottom = Math.max(selectionBox.startY, selectionBox.endY);

        // Convert to absolute page coordinates for comparison with getBoundingClientRect
        const absLeft = rect.left + left;
        const absTop = rect.top + top;
        const absRight = rect.left + right;
        const absBottom = rect.top + bottom;

        const proseMirrorNode = containerRef.current.querySelector('.ProseMirror');
        if (!proseMirrorNode) return;

        const children = Array.from(proseMirrorNode.children);
        let startPos: number | null = null;
        let endPos: number | null = null;

        children.forEach((child) => {
            const childRect = child.getBoundingClientRect();

            // Check intersection
            const intersects = !(
                childRect.right < absLeft ||
                childRect.left > absRight ||
                childRect.bottom < absTop ||
                childRect.top > absBottom
            );

            if (intersects) {
                try {
                    // Get Tiptap position
                    // We use editor.view.posAtDOM to find the position of the node
                    const pos = editor.view.posAtDOM(child as HTMLElement, 0);
                    if (pos >= 0) {
                        // For the end position, we need the node size
                        // We can find the node at this position
                        const node = editor.state.doc.nodeAt(pos);
                        if (node) {
                            if (startPos === null) startPos = pos;
                            endPos = pos + node.nodeSize;
                        }
                    }
                } catch (err) {
                    console.warn('Error getting pos for node', err);
                }
            }
        });

        if (startPos !== null && endPos !== null) {
            editor.chain().setTextSelection({ from: startPos, to: endPos }).run();
        }

        setIsSelecting(false);
        setSelectionBox(null);
    };

    // Global mouse up to handle release outside container
    useEffect(() => {
        const handleGlobalMouseUp = () => {
            if (isSelecting) {
                handleMouseUp();
            }
        };

        window.addEventListener('mouseup', handleGlobalMouseUp);
        return () => window.removeEventListener('mouseup', handleGlobalMouseUp);
    }, [isSelecting, selectionBox, editor]);

    const handleClick = (e: React.MouseEvent) => {
        if (e.target === e.currentTarget && onBackgroundClick) {
            e.preventDefault();
            onBackgroundClick();
        }
    };

    return (
        <div
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onClick={handleClick}
            className="relative w-full h-full cursor-text"
        >
            {children}
            {isSelecting && selectionBox && (
                <div
                    style={{
                        position: 'absolute',
                        left: Math.min(selectionBox.startX, selectionBox.endX),
                        top: Math.min(selectionBox.startY, selectionBox.endY),
                        width: Math.abs(selectionBox.endX - selectionBox.startX),
                        height: Math.abs(selectionBox.endY - selectionBox.startY),
                        border: '1px solid #a855f7',
                        backgroundColor: 'rgba(168, 85, 247, 0.1)',
                        pointerEvents: 'none', // Allow events to pass through
                        zIndex: 50
                    }}
                />
            )}
        </div>
    );
};
