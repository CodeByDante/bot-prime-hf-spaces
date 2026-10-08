/// <reference types="vite/client" />

declare global {
    interface Window {
        Telegram: {
            WebApp: {
                ready: () => void;
                close: () => void;
                sendData: (data: string) => void;
                initData: string;
                initDataUnsafe: any;
            };
        };
    }
}
