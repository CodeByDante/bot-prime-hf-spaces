import { useState, useEffect } from 'react';
import { Megaphone, Timer } from 'lucide-react';
import { subscribeToAnnouncement } from '../services/announcement';

interface AnnouncementBannerProps {
    isAdmin?: boolean;
}

export function AnnouncementBanner({ isAdmin }: AnnouncementBannerProps) {
    const [announcement, setAnnouncement] = useState<string>('');
    const [expiresAt, setExpiresAt] = useState<string | null>(null);
    const [timeLeft, setTimeLeft] = useState<string>('');
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const unsubscribe = subscribeToAnnouncement((data) => {
            if (data) {
                setAnnouncement(data.text);
                setExpiresAt(data.expiresAt);
            } else {
                setAnnouncement('');
                setExpiresAt(null);
            }
            setIsLoading(false);
        });

        return () => unsubscribe();
    }, []);

    useEffect(() => {
        if (!expiresAt) {
            setTimeLeft('');
            return;
        }

        const interval = setInterval(() => {
            const now = new Date().getTime();
            const expiration = new Date(expiresAt).getTime();
            const difference = expiration - now;

            if (difference <= 0) {
                setAnnouncement('');
                setExpiresAt(null);
                clearInterval(interval);
            } else {
                const days = Math.floor(difference / (1000 * 60 * 60 * 24));
                const hours = Math.floor((difference % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
                const minutes = Math.floor((difference % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((difference % (1000 * 60)) / 1000);

                let timeString = '';
                if (days > 0) timeString += `${days}d `;
                timeString += `${hours.toString().padStart(2, '0')}h ${minutes.toString().padStart(2, '0')}m ${seconds.toString().padStart(2, '0')}s`;
                setTimeLeft(timeString);
            }
        }, 1000);

        return () => clearInterval(interval);
    }, [expiresAt]);

    if (!announcement && !isLoading) return null;
    if (!announcement) return null;

    return (
        <div className="w-full max-w-[1800px] mx-auto px-4 sm:px-6 md:px-12 mt-6 mb-8 animate-in fade-in slide-in-from-top-4 duration-500 flex justify-center">
            <div className="bg-gradient-to-r from-[#bb86fc]/20 to-[#121212] border border-[#bb86fc]/30 rounded-xl p-6 flex flex-col items-center gap-4 shadow-lg shadow-[#bb86fc]/10 relative group backdrop-blur-sm max-w-2xl w-full text-center">

                <div className="flex items-center gap-3">
                    <div className="p-2.5 bg-[#bb86fc]/20 rounded-lg animate-pulse">
                        <Megaphone className="w-6 h-6 text-[#bb86fc]" />
                    </div>
                    <h3 className="text-sm font-bold text-[#bb86fc] uppercase tracking-wider flex items-center gap-2">
                        Información Importante
                        <span className="w-2 h-2 rounded-full bg-[#bb86fc] animate-ping" />
                    </h3>
                </div>

                <div className="text-base text-gray-200 leading-relaxed whitespace-pre-wrap font-medium max-w-lg">
                    {announcement}
                </div>

                {timeLeft && (
                    <div className="flex items-center gap-2 text-xs font-mono text-gray-400 bg-black/30 px-3 py-1.5 rounded-full border border-gray-800">
                        <Timer className="w-3.5 h-3.5" />
                        <span>Expira en: {timeLeft}</span>
                    </div>
                )}
            </div>
        </div>
    );
}
