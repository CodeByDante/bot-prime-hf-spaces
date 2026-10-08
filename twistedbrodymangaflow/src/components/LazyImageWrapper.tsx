import { useEffect, useRef, useState, ReactNode } from 'react';

interface LazyImageWrapperProps {
  children: (isVisible: boolean) => ReactNode;
  rootMargin?: string;
  minHeight?: string;
  className?: string;
}

export function LazyImageWrapper({ 
  children, 
  rootMargin = '150% 0px 150% 0px', 
  minHeight,
  className = ''
}: LazyImageWrapperProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isVisible) return; // Mantiene el componente renderizado una vez visto

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting) {
          setIsVisible(true);
        }
      },
      { rootMargin }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => {
      observer.disconnect();
    };
  }, [isVisible, rootMargin]);

  return (
    <div ref={containerRef} style={minHeight ? { minHeight } : undefined} className={`w-full flex items-center justify-center ${className}`}>
      {isVisible ? children(true) : null}
    </div>
  );
}
