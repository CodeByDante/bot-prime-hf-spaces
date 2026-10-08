import React, { useEffect, useState } from 'react';
import { NodeViewWrapper, NodeViewProps } from '@tiptap/react';
import { ExternalLink, Download, Github, Send, Twitter, Linkedin, Instagram, Youtube, Facebook, X, Code, Layers, MessageCircle, Globe, Mail, FileText } from 'lucide-react';
import { TiktokIcon } from './TiktokIcon';
import { subscribeToStyleConfig, StyleConfig, DEFAULT_STYLE_CONFIG } from '../services/codeStyleService';

export const CustomButtonComponent: React.FC<NodeViewProps> = ({ node, getPos, editor }) => {
    const { text, url, variant, backgroundColor, textColor, borderRadius, width, height } = node.attrs;
    // We no longer subscribe to live styleConfig updates to ensure existing buttons don't change
    // when the user adjusts the settings panel. Settings only affect NEW buttons.
    // Falls back to defaults if attributes are missing (legacy buttons).
    const fallbackConfig = DEFAULT_STYLE_CONFIG;

    const handleClick = (e: React.MouseEvent) => {
        if (editor.isEditable) {
            e.preventDefault();
        }
        // In read-only mode, the <a> tag handles navigation naturally
    };

    // Use node attributes if available (frozen style), otherwise fallback to DEFAULT config (not live config)
    const activeStyle = {
        width: width || (fallbackConfig.button.width === 'auto' ? 'auto' : fallbackConfig.button.width),
        height: height || (fallbackConfig.button.height === 'auto' ? 'auto' : fallbackConfig.button.height),
        backgroundColor: backgroundColor || fallbackConfig.button.backgroundColor,
        textColor: textColor || fallbackConfig.button.textColor,
        borderRadius: borderRadius || fallbackConfig.button.borderRadius,
    };

    const buttonStyle = {
        width: activeStyle.width,
        height: activeStyle.height,
        maxWidth: '100%', // Prevent overflow
        backgroundColor: 'transparent',
        color: activeStyle.backgroundColor, // Icon/Text color matches background config? Wait, usually button has background color. 
        // The original code used 'color: styleConfig.button.backgroundColor' and 'border: 1px solid ...'.
        // It seems the "backgroundColor" config actually controls the FOREGROUND color (text/icon) and border? 
        // Let's verify existing behavior. 
        // Original: color: styleConfig.button.backgroundColor, border: 1px solid ...
        // So yes, "backgroundColor" in config is used as the primary color.

        borderRadius: activeStyle.borderRadius,
        border: `1px solid ${activeStyle.backgroundColor}`,
        boxShadow: `0 0 10px ${activeStyle.backgroundColor}40`, // Glow effect
    };

    return (
        <NodeViewWrapper className="inline-block mx-1 align-middle" style={{ maxWidth: '100%' }}> {/* Reverted to inline-block to allow typing next to it */}
            <a
                href={url}
                target="_blank"
                rel="noopener noreferrer"
                onClick={handleClick}
                style={buttonStyle}
                className={`
                    inline-flex items-center justify-center gap-2 px-4 py-2 border transition-all duration-200 no-underline
                    ${editor.isEditable ? 'cursor-default' : 'cursor-pointer'}
                    hover:opacity-90
                `}
            >
                {variant === 'visit' ? (
                    <ExternalLink size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'download' ? (
                    <Download size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'github' ? (
                    <Github size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'telegram' ? (
                    <Send size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'twitter' ? (
                    <Twitter size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'linkedin' ? (
                    <Linkedin size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'instagram' ? (
                    <Instagram size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'youtube' ? (
                    <Youtube size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'facebook' ? (
                    <Facebook size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'tiktok' ? (
                    <TiktokIcon size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'x' ? (
                    <X size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'code' ? (
                    <Code size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'layers' ? (
                    <Layers size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'community' ? (
                    <MessageCircle size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'globe' ? (
                    <Globe size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'mail' ? (
                    <Mail size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : variant === 'file' ? (
                    <FileText size={16} style={{ color: activeStyle.backgroundColor }} />
                ) : (
                    <ExternalLink size={16} style={{ color: activeStyle.backgroundColor }} />
                )}
                <span className="font-medium text-sm" style={{ color: activeStyle.textColor }}>{text}</span>
            </a>
        </NodeViewWrapper>
    );
};
