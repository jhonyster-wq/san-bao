import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { ExecutiveDashboard } from '../types';
import {
  DollarSign,
  GraduationCap,
  Stethoscope,
  ShieldCheck,
  Building,
} from 'lucide-react';

export const DashboardPage: React.FC = () => {
  const { activeCompany } = useAuth();
  const [dashboard, setDashboard] = useState<ExecutiveDashboard | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchDashboard = async () => {
      setLoading(true);
      try {
        const url = activeCompany?.id
          ? `/bi/dashboard/executive?company_id=${activeCompany.id}`
          : '/bi/dashboard/executive';
        const res = await api.get(url);
        setDashboard(res.data);
      } catch (err) {
        console.error('Error cargando BI dashboard:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboard();
  }, [activeCompany]);

  const formatCLP = (amount: number) => {
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 0,
    }).format(amount || 0);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#1A56B2]"></div>
      </div>
    );
  }

  const fin = dashboard?.financial;
  const acad = dashboard?.academic;
  const clin = dashboard?.clinical;

  return (
    <div className="space-y-8">
      {/* Banner de Bienvenida y Sociedad Activa */}
      <div className="bg-gradient-to-r from-[#0C1D36] via-[#102B54] to-[#1A56B2] text-white p-7 rounded-2xl shadow-md flex items-center justify-between">
        <div className="space-y-1">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wider text-blue-200 font-bold">
            <Building className="w-4 h-4 text-blue-300" />
            <span>Indicadores Consolidados de Gestión</span>
          </div>
          <h1 className="font-serif text-2xl font-bold tracking-wide">
            {dashboard?.company_name || 'San Bao SpA'}
          </h1>
          <p className="text-xs text-blue-100/80">
            Ecosistema Integrado: Instituto de Medicina China Clásica & Servicios Clínicos San Bao
          </p>
        </div>
        <div className="hidden sm:flex items-center gap-3 bg-white/10 backdrop-blur-md px-4 py-2.5 rounded-xl border border-white/20">
          <ShieldCheck className="w-5 h-5 text-blue-300" />
          <span className="text-xs font-semibold text-white">Cumplimiento Ley 20.584 Activo</span>
        </div>
      </div>

      {/* Tarjetas Financieras */}
      <section className="space-y-3">
        <h2 className="text-base font-bold text-slate-800 flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-[#1A56B2]" />
          <span>Finanzas Institucionales</span>
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow transition-shadow">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Ingresos Totales (CLP)</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {formatCLP(fin?.total_revenue || 0)}
            </div>
            <span className="text-xs text-blue-700 font-medium mt-1 inline-block">
              Aranceles + E-commerce
            </span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow transition-shadow">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Cuentas por Cobrar (Morosidad)</span>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {formatCLP(fin?.pending_receivables || 0)}
            </div>
            <span className="text-xs text-slate-400 font-medium mt-1 inline-block">
              Cuotas de arancel pendientes
            </span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow transition-shadow">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Egresos RRHH & Nómina</span>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {formatCLP(fin?.total_expenses || 0)}
            </div>
            <span className="text-xs text-slate-400 font-medium mt-1 inline-block">
              Sueldos + BHE Honorarios
            </span>
          </div>

          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm hover:shadow transition-shadow">
            <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Resultado Operativo Neto</span>
            <div className="text-2xl font-bold text-[#1A56B2] mt-1">
              {formatCLP(fin?.net_operating_result || 0)}
            </div>
            <span className="text-xs text-emerald-600 font-medium mt-1 inline-block">
              Margen de operaciones
            </span>
          </div>
        </div>
      </section>

      {/* Grid de KPIs Académicos y Clínicos */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Módulo Académico */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <GraduationCap className="w-5 h-5 text-[#1A56B2]" />
              <span>Gestión Académica & Escuela</span>
            </h3>
            <span className="text-xs font-semibold px-2.5 py-1 bg-[#EBF2FC] text-[#1A56B2] rounded-full border border-blue-200">
              Instituto SpA
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Alumnos Regulares</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {acad?.total_active_students || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Programas y Carreras</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {acad?.total_programs || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Cohortes Activas</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {acad?.active_cohorts || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Horas Prácticas Acreditadas</span>
              <div className="text-2xl font-bold text-[#1A56B2] mt-1">
                {acad?.accredited_clinical_hours || 0} hrs
              </div>
            </div>
          </div>
        </div>

        {/* Módulo Clínico */}
        <div className="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <h3 className="font-bold text-slate-800 flex items-center gap-2">
              <Stethoscope className="w-5 h-5 text-[#1A56B2]" />
              <span>Gestión Clínica Integrativa MTC</span>
            </h3>
            <span className="text-xs font-semibold px-2.5 py-1 bg-[#EBF2FC] text-[#1A56B2] rounded-full border border-blue-200">
              Clínica San Bao SpA
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Fichas de Pacientes</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {clin?.total_patients || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Terapeutas & Tutores</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {clin?.active_practitioners || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Atenciones Completadas</span>
              <div className="text-2xl font-bold text-slate-800 mt-1">
                {clin?.completed_appointments || 0}
              </div>
            </div>
            <div className="bg-[#F8FAFC] p-4 rounded-xl border border-slate-100">
              <span className="text-xs text-slate-500 font-medium">Fichas MTC Firmadas (Ley 20.584)</span>
              <div className="text-2xl font-bold text-[#1A56B2] mt-1">
                {clin?.signed_clinical_encounters || 0}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
