import React, { useState, useEffect } from 'react';
import { Lock, X, KeyRound } from 'lucide-react';
import { Button } from './Button';

interface AdminLoginModalProps {
    isOpen: boolean;
    onClose: () => void;
    onSuccess: () => void;
}

export const AdminLoginModal: React.FC<AdminLoginModalProps> = ({ isOpen, onClose, onSuccess }) => {
    const [password, setPassword] = useState('');
    const [error, setError] = useState(false);
    const [isAnimating, setIsAnimating] = useState(false);

    useEffect(() => {
        if (isOpen) {
            setIsAnimating(true);
            setPassword('');
            setError(false);
        } else {
            setTimeout(() => setIsAnimating(false), 200);
        }
    }, [isOpen]);

    if (!isOpen && !isAnimating) return null;

    const handleLogin = async () => {
        try {
            console.log('[AdminLogin] Starting login process...');

            if (!password) {
                console.log('[AdminLogin] No password entered');
                setError(true);
                return;
            }

            if (!window.crypto || !window.crypto.subtle) {
                console.error('[AdminLogin] Crypto API not available', { crypto: !!window.crypto, subtle: !!window.crypto?.subtle });
                alert('Error crítico: Tu navegador no soporta la encriptación necesaria (crypto.subtle). Por favor usa un navegador moderno o contexto seguro (HTTPS/localhost).');
                return;
            }

            const encoder = new TextEncoder();
            const data = encoder.encode(password);

            console.log('[AdminLogin] Hashing password...');
            const hashBuffer = await crypto.subtle.digest('SHA-256', data);
            const hashArray = Array.from(new Uint8Array(hashBuffer));
            const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');

            console.log('[AdminLogin] Hash generated:', hashHex);

            // Hash for 'codebydante069012*'
            const expectedHash = '19362a1b321cd1b4fe5a625b8a6647a371beebebd3daddccdb2ed271a9a7ee5d';

            if (hashHex === expectedHash) {
                console.log('[AdminLogin] Password correct!');
                onSuccess();
                onClose();
            } else {
                console.warn('[AdminLogin] Password incorrect. Expected:', expectedHash, 'Got:', hashHex);
                setError(true);
            }
        } catch (e: any) {
            console.error('[AdminLogin] Unexpected error:', e);
            alert(`Error inesperado: ${e.message || e}`);
        }
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') {
            handleLogin();
        }
    };

    return (
        <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-300 ${isOpen ? 'opacity-100 backdrop-blur-sm bg-black/50' : 'opacity-0 pointer-events-none'
                }`}
        >
            <div
                className={`bg-[#1a1a1a] border border-white/10 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl transition-all duration-300 transform ${isOpen ? 'scale-100 translate-y-0' : 'scale-95 translate-y-4'
                    }`}
            >
                {/* Header */}
                <div className="flex items-center justify-between p-6 border-b border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-primary/20 rounded-lg">
                            <Lock className="w-6 h-6 text-primary" />
                        </div>
                        <div>
                            <h2 className="text-lg font-bold text-white">Acceso Administrativo</h2>
                            <p className="text-xs text-gray-400">Introduce la credencial de seguridad</p>
                        </div>
                    </div>
                    <button
                        onClick={onClose}
                        className="text-gray-400 hover:text-white transition-colors p-1"
                    >
                        <X size={20} />
                    </button>
                </div>

                {/* Content */}
                <div className="p-6 space-y-4">
                    <div className="bg-primary/5 border border-primary/20 rounded-lg p-3 text-xs text-primary/80">
                        <p>Esta zona está protegida. Solo personal autorizado.</p>
                    </div>

                    <div className="space-y-2">
                        <label className="text-sm font-medium text-gray-300 flex items-center gap-2">
                            <KeyRound size={14} /> Tu Clave Maestra
                        </label>
                        <input
                            type="password"
                            value={password}
                            onChange={(e) => {
                                setPassword(e.target.value);
                                setError(false);
                            }}
                            onKeyDown={handleKeyDown}
                            className={`w-full bg-black/40 border rounded-lg px-4 py-3 text-white placeholder-gray-600 outline-none focus:ring-1 transition-all ${error
                                ? 'border-red-500 focus:border-red-500 focus:ring-red-500/20'
                                : 'border-white/10 focus:border-primary focus:ring-primary/20'
                                }`}
                            placeholder="••••••••••••••"
                            autoFocus
                        />
                        {error && (
                            <p className="text-xs text-red-500 animate-pulse">
                                Acceso denegado. Credencial inválida.
                            </p>
                        )}
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 pt-0 flex gap-3">
                    <Button
                        variant="danger"
                        onClick={onClose}
                        className="flex-1 bg-white/5 border-white/10 hover:bg-white/10"
                    >
                        Cancelar
                    </Button>
                    <Button
                        variant="primary"
                        onClick={handleLogin}
                        className="flex-1"
                    >
                        Acceder
                    </Button>
                </div>
            </div>
        </div>
    );
};
