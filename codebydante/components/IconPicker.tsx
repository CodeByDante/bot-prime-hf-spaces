import React, { useState, useRef, useEffect } from 'react';
import {
    Github, Twitter, Globe, Download, Youtube, Twitch,
    Linkedin, Facebook, Instagram, Code, Terminal, Database,
    Server, Smartphone, Monitor, Cpu, FileText, Image,
    Music, Video, Box, Layers, Zap, Activity,
    Award, Bookmark, Calendar, Camera, Check, Clock,
    Cloud, Command, Compass, Copy, CreditCard, Flag,
    Folder, Gift, Heart, Home, Key, Link as LinkIcon,
    Lock, Mail, Map, MapPin, MessageCircle, MessageSquare,
    Mic, Moon, Mouse, Package, Paperclip, Phone,
    Play, Plus, Power, Printer, Radio, RotateCw,
    Save, Search, Send, Settings, Share, Shield,
    ShoppingBag, ShoppingCart, Info, Star, Sun, Tag,
    ThumbsUp, PenTool, Trash, Truck, Tv, Unlock,
    Upload, User, Users, Wifi, X
} from 'lucide-react';

interface IconPickerProps {
    selectedIcon?: string;
    onSelect: (iconName: string) => void;
}

const ICON_MAP: Record<string, React.FC<any>> = {
    'github': Github,
    'twitter': Twitter,
    'globe': Globe,
    'download': Download,
    'youtube': Youtube,
    'twitch': Twitch,
    'linkedin': Linkedin,
    'facebook': Facebook,
    'instagram': Instagram,
    'code': Code,
    'terminal': Terminal,
    'database': Database,
    'server': Server,
    'smartphone': Smartphone,
    'monitor': Monitor,
    'cpu': Cpu,
    'file-text': FileText,
    'image': Image,
    'music': Music,
    'video': Video,
    'box': Box,
    'layers': Layers,
    'zap': Zap,
    'activity': Activity,
    'award': Award,
    'bookmark': Bookmark,
    'calendar': Calendar,
    'camera': Camera,
    'check': Check,
    'clock': Clock,
    'cloud': Cloud,
    'command': Command,
    'compass': Compass,
    'copy': Copy,
    'credit-card': CreditCard,
    'flag': Flag,
    'folder': Folder,
    'gift': Gift,
    'heart': Heart,
    'home': Home,
    'key': Key,
    'link': LinkIcon,
    'lock': Lock,
    'mail': Mail,
    'map': Map,
    'map-pin': MapPin,
    'message-circle': MessageCircle,
    'message-square': MessageSquare,
    'mic': Mic,
    'moon': Moon,
    'mouse': Mouse,
    'package': Package,
    'paperclip': Paperclip,
    'phone': Phone,
    'play': Play,
    'plus': Plus,
    'power': Power,
    'printer': Printer,
    'radio': Radio,
    'rotate-cw': RotateCw,
    'save': Save,
    'search': Search,
    'send': Send,
    'settings': Settings,
    'share': Share,
    'shield': Shield,
    'shopping-bag': ShoppingBag,
    'shopping-cart': ShoppingCart,
    'info': Info,
    'star': Star,
    'sun': Sun,
    'tag': Tag,
    'thumbs-up': ThumbsUp,
    'tool': PenTool,
    'trash': Trash,
    'truck': Truck,
    'tv': Tv,
    'unlock': Unlock,
    'upload': Upload,
    'user': User,
    'users': Users,
    'wifi': Wifi,
    'x': X,
};

export const getIconComponent = (iconName?: string) => {
    if (!iconName) return null;
    return ICON_MAP[iconName] || null;
};

export const IconPicker: React.FC<IconPickerProps> = ({ selectedIcon, onSelect }) => {
    const [isOpen, setIsOpen] = useState(false);
    const [searchTerm, setSearchTerm] = useState('');
    const wrapperRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        function handleClickOutside(event: MouseEvent) {
            if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        }
        document.addEventListener("mousedown", handleClickOutside);
        return () => {
            document.removeEventListener("mousedown", handleClickOutside);
        };
    }, [wrapperRef]);

    const filteredIcons = Object.keys(ICON_MAP).filter(name =>
        name.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const SelectedIconComponent = getIconComponent(selectedIcon);

    return (
        <div className="relative" ref={wrapperRef}>
            <button
                type="button"
                onClick={() => setIsOpen(!isOpen)}
                className="w-12 h-[46px] rounded-lg border border-white/10 bg-background hover:bg-white/5 flex items-center justify-center transition-colors text-gray-400 hover:text-white focus:outline-none focus:ring-1 focus:ring-primary focus:border-primary"
                title="Seleccionar icono"
            >
                {SelectedIconComponent ? (
                    <SelectedIconComponent size={20} className="text-primary" />
                ) : (
                    <Box size={20} />
                )}
            </button>

            {isOpen && (
                <div className="absolute top-full left-0 mt-2 z-50 w-72 bg-surface border border-white/10 rounded-xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
                    <div className="p-3 border-b border-white/10">
                        <div className="relative">
                            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500" size={14} />
                            <input
                                type="text"
                                placeholder="Buscar icono..."
                                value={searchTerm}
                                onChange={(e) => setSearchTerm(e.target.value)}
                                className="w-full bg-background border border-white/10 rounded-lg py-1.5 pl-8 pr-3 text-sm text-gray-200 outline-none focus:border-primary"
                                autoFocus
                            />
                        </div>
                    </div>

                    <div className="p-2 grid grid-cols-5 gap-1 max-h-64 overflow-y-auto custom-scrollbar">
                        {filteredIcons.map((iconName) => {
                            const Icon = ICON_MAP[iconName];
                            const isSelected = selectedIcon === iconName;

                            return (
                                <button
                                    key={iconName}
                                    type="button"
                                    onClick={() => {
                                        onSelect(iconName);
                                        setIsOpen(false);
                                    }}
                                    className={`p-2 rounded-lg flex items-center justify-center transition-all ${isSelected
                                            ? 'bg-primary/20 text-primary'
                                            : 'text-gray-400 hover:bg-white/5 hover:text-white'
                                        }`}
                                    title={iconName}
                                >
                                    <Icon size={20} />
                                </button>
                            );
                        })}

                        {filteredIcons.length === 0 && (
                            <div className="col-span-5 py-4 text-center text-xs text-gray-500">
                                No se encontraron iconos
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
    );
};
