import React from 'react';
import {
  LayoutDashboard,
  GraduationCap,
  Stethoscope,
  Receipt,
  Users,
  BookOpen,
  Sparkles,
} from 'lucide-react';

interface SidebarProps {
  currentPage: string;
  onNavigate: (page: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentPage, onNavigate }) => {
  const menuItems = [
    { id: 'dashboard', label: 'Dashboard Ejecutivo', icon: LayoutDashboard },
    { id: 'academic', label: 'Gestión Académica', icon: GraduationCap },
    { id: 'clinical', label: 'Gestión Clínica MTC', icon: Stethoscope },
    { id: 'finance', label: 'Finanzas & DTE SII', icon: Receipt },
    { id: 'hr', label: 'Personas & Nóminas', icon: Users },
    { id: 'lms', label: 'LMS Aula Virtual', icon: BookOpen },
  ];

  return (
    <aside className="w-64 bg-[#0C1D36] text-white flex flex-col min-h-screen border-r border-[#192E4F] select-none">
      {/* Logotipo Oficial San Bao */}
      <div className="h-24 px-5 flex items-center gap-3.5 border-b border-[#192E4F] bg-[#0A182E]">
        <div className="w-14 h-14 bg-white rounded-xl p-1 flex items-center justify-center shadow-md flex-shrink-0">
          <img src="/logo_sanbao.png" alt="San Bao - Escuela de Medicina China Clásica" className="h-full w-full object-contain" />
        </div>
        <div className="flex flex-col">
          <span className="font-serif font-bold text-base tracking-wider text-white leading-tight">SAN BAO</span>
          <span className="text-[9px] text-blue-300 font-semibold tracking-wider uppercase">
            Escuela Med. China Clásica
          </span>
          <span className="text-[8px] text-blue-400/80 font-mono tracking-widest">神 • 精 • 氣</span>
        </div>
      </div>

      {/* Navegación modular */}
      <nav className="p-4 space-y-1.5 flex-1 overflow-y-auto">
        <div className="px-3 pb-2 text-[10px] font-bold tracking-wider text-blue-300/60 uppercase">
          Ecosistema
        </div>
        {menuItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentPage === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive
                  ? 'bg-[#1A56B2] text-white shadow-sm'
                  : 'text-slate-300 hover:text-white hover:bg-[#14294A]'
              }`}
            >
              <Icon className={`w-5 h-5 ${isActive ? 'text-blue-200' : 'text-slate-400'}`} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* Pie institucional */}
      <div className="p-4 border-t border-[#192E4F] bg-[#0A182E] space-y-1">
        <div className="flex items-center gap-2 text-xs text-blue-200">
          <Sparkles className="w-4 h-4 text-blue-400" />
          <span className="font-medium">Ley N° 20.584 • DTE SII OK</span>
        </div>
        <p className="text-[10px] text-blue-400/60">Instituto SpA & Clínica SpA</p>
      </div>
    </aside>
  );
};
