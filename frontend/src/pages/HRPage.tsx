import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Users, FileCheck, DollarSign, Briefcase } from 'lucide-react';

export const HRPage: React.FC = () => {
  const { activeCompany } = useAuth();
  const [employees, setEmployees] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchEmployees = async () => {
      try {
        const url = activeCompany?.id
          ? `/hr/employees?company_id=${activeCompany.id}`
          : '/hr/employees';
        const res = await api.get(url);
        setEmployees(res.data || []);
      } catch (err) {
        console.error('Error cargando colaboradores:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchEmployees();
  }, [activeCompany]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Personas & Remuneraciones</h1>
          <p className="text-sm text-gray-500">
            Contratos, Nóminas según Código del Trabajo y Boletas de Honorarios BHE
          </p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2">
            <Users className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Colaboradores & Personal Activo</h2>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 bg-emerald-50 text-emerald-700 rounded-full">
            {employees.length} Registrados
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {employees.length === 0 ? (
            <p className="text-sm text-gray-400 col-span-3 py-6 text-center">
              No hay colaboradores registrados para esta sociedad.
            </p>
          ) : (
            employees.map((emp) => (
              <div key={emp.id} className="p-4 bg-[#F8F9F8] rounded-xl border border-gray-100 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-[#2D5A47] bg-emerald-100 px-2 py-0.5 rounded">
                    {emp.employee_number}
                  </span>
                  <span className="text-xs font-semibold px-2 py-0.5 bg-gray-200 text-gray-700 rounded">
                    {emp.employee_type}
                  </span>
                </div>
                <h3 className="font-bold text-gray-800 text-base">{emp.job_title}</h3>
                <div className="text-xs text-gray-500 space-y-0.5">
                  <p>Departamento: {emp.department}</p>
                  <p>Fecha Ingreso: {emp.hire_date}</p>
                  <p className="text-emerald-700 font-medium">Estado: {emp.status}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
