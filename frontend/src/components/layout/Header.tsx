import React from 'react';
import { useAuth } from '../../context/AuthContext';
import { Building2, ChevronDown, UserCircle, LogOut } from 'lucide-react';

export const Header: React.FC = () => {
  const { user, companies, activeCompany, setActiveCompany, logout } = useAuth();

  return (
    <header className="h-16 bg-white border-b border-slate-200 px-6 flex items-center justify-between sticky top-0 z-30 shadow-sm">
      <div className="flex items-center gap-4">
        {/* Selector de Sociedad SpA activa */}
        <div className="flex items-center gap-2 bg-[#F8FAFC] border border-slate-200 rounded-xl px-3 py-1.5 shadow-sm hover:border-blue-300 transition-colors">
          <Building2 className="w-5 h-5 text-[#1A56B2]" />
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-bold uppercase leading-none">Sociedad Activa</span>
            <select
              value={activeCompany?.id || ''}
              onChange={(e) => {
                const found = companies.find((c) => c.id === e.target.value);
                if (found) setActiveCompany(found);
              }}
              className="bg-transparent text-sm font-bold text-[#0C1D36] focus:outline-none cursor-pointer"
            >
              {companies.map((comp) => (
                <option key={comp.id} value={comp.id}>
                  {comp.trade_name || comp.legal_name} ({comp.rut})
                </option>
              ))}
            </select>
          </div>
          <ChevronDown className="w-4 h-4 text-slate-400 ml-1" />
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-full bg-[#1A56B2] text-white flex items-center justify-center font-bold text-xs shadow-sm">
            {user?.username ? user.username.slice(0, 2).toUpperCase() : 'SB'}
          </div>
          <div className="flex flex-col text-right">
            <span className="text-xs font-bold text-slate-800 leading-tight">
              {user?.username}
            </span>
            <span className="text-[10px] text-slate-400 font-medium">
              {user?.is_superuser ? 'Superadministrador' : 'Usuario'}
            </span>
          </div>
        </div>

        <button
          onClick={logout}
          title="Cerrar Sesión"
          className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-xl transition-colors"
        >
          <LogOut className="w-5 h-5" />
        </button>
      </div>
    </header>
  );
};
