interface LoadingSpinnerProps {
  size?: number;
  borderWidth?: number;
  className?: string;
}

export function LoadingSpinner({ size = 40, borderWidth = 2, className = '' }: LoadingSpinnerProps) {
  return (
    <div className={`flex items-center justify-center ${className}`}>
      <div className="relative" style={{ width: `${size}px`, height: `${size}px` }}>
        <div
          className="rounded-full animate-spin"
          style={{
            width: `${size}px`,
            height: `${size}px`,
            borderWidth: `${borderWidth}px`,
            borderStyle: 'solid',
            borderColor: 'rgba(187, 134, 252, 0.3)',
            borderTopColor: '#bb86fc',
            animation: 'spin 1.2s linear infinite',
            boxShadow: '0 0 20px rgba(139, 92, 246, 0.2)',
          }}
        />
      </div>
    </div>
  );
}
