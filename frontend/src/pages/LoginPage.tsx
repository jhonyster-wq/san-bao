import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Lock, User, AlertCircle } from 'lucide-react';

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('AdminSanBao2026!');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const success = await login(username, password);
    setLoading(false);
    if (!success) {
      setError('Credenciales institucionales incorrectas o usuario inactivo.');
    }
  };

  return (
    <div className="min-h-screen bg-[#F8FAFC] flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-3xl p-8 shadow-md border border-slate-200 space-y-6">
        
        {/* Cabecera con Logotipo Oficial San Bao */}
        <div className="text-center space-y-2">
          <div className="w-36 h-36 mx-auto flex items-center justify-center p-1">
            <img
              src="/logo_sanbao.png"
              alt="San Bao - Escuela de Medicina China Clásica"
              className="max-h-full max-w-full object-contain filter drop-shadow-sm"
            />
          </div>
          <div>
            <p className="text-xs text-[#1A56B2] uppercase tracking-wider font-bold">
              Sistema Integral SpA • Acceso Único
            </p>
            <p className="text-[10px] text-slate-400 font-mono mt-0.5">
              神 (Shén) • 精 (Jīng) • 氣 (Qì)
            </p>
          </div>
        </div>

        {error && (
          <div className="p-3.5 bg-red-50 border border-red-200 text-red-700 text-xs rounded-xl flex items-center gap-2">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Usuario Institucional
            </label>
            <div className="relative">
              <User className="w-5 h-5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-[#F8FAFC] border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-[#1A56B2] focus:ring-1 focus:ring-[#1A56B2]"
                placeholder="admin o alumno"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-700 uppercase mb-1">
              Contraseña
            </label>
            <div className="relative">
              <Lock className="w-5 h-5 text-slate-400 absolute left-3 top-2.5" />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-[#F8FAFC] border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-[#1A56B2] focus:ring-1 focus:ring-[#1A56B2]"
                placeholder="••••••••"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-[#1A56B2] hover:bg-[#15458F] text-white font-semibold text-sm rounded-xl transition-all shadow-md hover:shadow-lg flex items-center justify-center"
          >
            {loading ? 'Ingresando al Sistema...' : 'Iniciar Sesión'}
          </button>
        </form>

        <div className="pt-2 border-t border-slate-100 space-y-2">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block text-center">
            Accesos Rápidos de Prueba
          </span>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => {
                setUsername('admin');
                setPassword('AdminSanBao2026!');
              }}
              className="py-1.5 px-2 bg-slate-50 hover:bg-slate-100 text-slate-700 text-xs font-semibold rounded-lg border border-slate-200 transition-colors"
            >
              👑 Administrador
            </button>
            <button
              type="button"
              onClick={() => {
                setUsername('alumno');
                setPassword('AlumnoSanBao2026!');
              }}
              className="py-1.5 px-2 bg-blue-50 hover:bg-blue-100 text-[#1A56B2] text-xs font-semibold rounded-lg border border-blue-200 transition-colors"
            >
              🎓 Alumno (Diego)
            </button>
          </div>
        </div>

        <div className="text-center pt-2 border-t border-slate-100">
          <p className="text-[11px] text-slate-400">
            Instituto de Medicina China Clásica SpA &bull; Servicios Clínicos SpA
          </p>
        </div>
      </div>
    </div>
  );
};
