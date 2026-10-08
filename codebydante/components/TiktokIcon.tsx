import React from 'react';

interface TiktokIconProps {
    size?: number;
    style?: React.CSSProperties;
    color?: string;
    className?: string; // Add className prop
}

export const TiktokIcon: React.FC<TiktokIconProps> = ({ size = 24, style, color = 'currentColor', className }) => {
    return (
        <svg
            xmlns="http://www.w3.org/2000/svg"
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke={color}
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={style}
            className={className} // Pass className to svg
        >
            <path d="M9 12a4 4 0 1 0 4 4V4a5 5 0 0 0 5 5" />
        </svg>
    );
};
