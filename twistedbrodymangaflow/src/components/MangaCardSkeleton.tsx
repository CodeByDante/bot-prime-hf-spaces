export function MangaCardSkeleton() {
    return (
        <div className="flex flex-col w-full max-w-xs">
            <div className="relative bg-black rounded-lg shadow-lg overflow-hidden aspect-[2/3] mb-2">
                <div className="absolute inset-0 flex items-center justify-center">
                    <div
                        className="rounded-full animate-spin"
                        style={{
                            width: '30px',
                            height: '30px',
                            borderWidth: '2px',
                            borderStyle: 'solid',
                            borderColor: 'rgba(187, 134, 252, 0.2)',
                            borderTopColor: '#bb86fc',
                            animation: 'spin 0.6s linear infinite',
                        }}
                    />
                </div>
            </div>

            <div className="flex flex-col gap-2 items-center animate-pulse">
                <div className="h-4 bg-gray-800 rounded w-3/4"></div>
                <div className="h-3 bg-gray-800 rounded w-1/2"></div>
            </div>
        </div>
    );
}
