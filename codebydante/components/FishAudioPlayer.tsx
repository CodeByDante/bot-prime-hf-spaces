import React, { useState, useEffect } from 'react';
import { Play, Pause, Volume2, Loader2 } from 'lucide-react';

interface FishAudioPlayerProps {
  modelId: string;
  className?: string;
}

export const FishAudioPlayer: React.FC<FishAudioPlayerProps> = ({ modelId, className = "" }) => {
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = React.useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const fetchModel = async () => {
      try {
        setLoading(true);
        const response = await fetch(`https://api.fish.audio/model/${modelId}`);
        if (!response.ok) throw new Error('Failed to fetch model info');
        const data = await response.json();
        
        if (data.samples && data.samples.length > 0 && data.samples[0].audio) {
          setAudioUrl(data.samples[0].audio);
        } else {
          setError('No audio sample found');
        }
      } catch (err) {
        console.error('Error loading Fish Audio:', err);
        setError('Error loading preview');
      } finally {
        setLoading(false);
      }
    };

    if (modelId) {
      fetchModel();
    }
  }, [modelId]);

  const togglePlay = () => {
    if (!audioRef.current) return;
    
    if (isPlaying) {
      audioRef.current.pause();
    } else {
      audioRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  if (loading) {
    return (
      <div className={`flex items-center gap-3 p-4 bg-white/5 rounded-xl border border-white/10 animate-pulse ${className}`}>
        <div className="w-10 h-10 rounded-full bg-white/10 flex items-center justify-center">
          <Loader2 className="animate-spin text-primary" size={20} />
        </div>
        <div className="flex-1 space-y-2">
          <div className="h-2 bg-white/10 rounded w-1/3"></div>
          <div className="h-1 bg-white/5 rounded w-full"></div>
        </div>
      </div>
    );
  }

  if (error || !audioUrl) {
    return null; // Don't show anything if there's an error
  }

  return (
    <div className={`flex items-center gap-4 p-4 bg-primary/5 rounded-xl border border-primary/20 group hover:bg-primary/10 transition-all duration-300 ${className}`}>
      <button 
        onClick={togglePlay}
        className="w-12 h-12 rounded-full bg-primary text-background flex items-center justify-center hover:scale-105 active:scale-95 transition-transform shadow-lg shadow-primary/20"
      >
        {isPlaying ? <Pause size={24} fill="currentColor" /> : <Play size={24} fill="currentColor" className="ml-1" />}
      </button>
      
      <div className="flex-1">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs font-bold text-primary uppercase tracking-wider">Demo de Voz</span>
          <Volume2 size={14} className="text-primary/60" />
        </div>
        <div className="relative h-1.5 bg-white/10 rounded-full overflow-hidden">
          <div className={`absolute inset-0 bg-primary/30 ${isPlaying ? 'animate-shimmer' : ''}`} style={{ width: '100%', backgroundSize: '200% 100%' }}></div>
          {/* We could add a proper progress bar here if we wanted to be more fancy */}
        </div>
      </div>

      <audio 
        ref={audioRef}
        src={audioUrl}
        onEnded={() => setIsPlaying(false)}
        onPause={() => setIsPlaying(false)}
        onPlay={() => setIsPlaying(true)}
        className="hidden"
      />
    </div>
  );
};
