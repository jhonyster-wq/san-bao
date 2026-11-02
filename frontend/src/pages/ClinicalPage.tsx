import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { Stethoscope, User, Calendar, Shield, Activity, CheckCircle2 } from 'lucide-react';

export const ClinicalPage: React.FC = () => {
  const [patients, setPatients] = useState<any[]>([]);
  const [appointments, setAppointments] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchClinicalData = async () => {
      try {
        const [resPatients, resApp] = await Promise.all([
          api.get('/clinical/patients'),
          api.get('/clinical/appointments'),
        ]);
        setPatients(resPatients.data?.data?.items || resPatients.data?.data || []);
        setAppointments(resApp.data?.data?.items || resApp.data?.data || []);
      } catch (err) {
        console.error('Error cargando datos clínicos:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchClinicalData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gestión Clínica & Ficha MTC</h1>
          <p className="text-sm text-gray-500">Servicios Clínicos San Bao SpA • Ley N° 20.584</p>
        </div>
      </div>

      {/* Grid Clínico */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Pacientes Registrados */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <User className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Fichas de Pacientes</h2>
          </div>
          <div className="space-y-3">
            {patients.length === 0 ? (
              <p className="text-sm text-gray-400">No hay pacientes registrados.</p>
            ) : (
              patients.map((pat) => (
                <div key={pat.id} className="p-3.5 bg-[#F8F9F8] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold px-2 py-0.5 bg-blue-100 text-blue-800 rounded">
                      {pat.record_number}
                    </span>
                    <h3 className="font-semibold text-gray-800 mt-1">
                      {pat.person?.first_name} {pat.person?.last_name}
                    </h3>
                    <span className="text-xs text-gray-500">RUT: {pat.person?.rut}</span>
                  </div>
                  <span className="text-xs font-semibold text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                    {pat.blood_type || 'N/R'}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Agenda de Atención y Boxes */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <Calendar className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Agenda & Boxes Clínicos</h2>
          </div>
          <div className="space-y-3">
            {appointments.length === 0 ? (
              <p className="text-sm text-gray-400">No hay citas agendadas.</p>
            ) : (
              appointments.map((app) => (
                <div key={app.id} className="p-3.5 bg-[#F8F9F8] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold text-gray-700">
                      {app.appointment_date} • {app.start_time} - {app.end_time}
                    </span>
                    <h3 className="font-semibold text-gray-800 mt-0.5">
                      {app.patient?.person?.first_name} {app.patient?.person?.last_name}
                    </h3>
                    <span className="text-xs text-emerald-700 font-medium">Box: {app.room?.name}</span>
                  </div>
                  <span className="text-xs font-semibold px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full">
                    {app.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Modelo Semiología MTC y Trazabilidad */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <Activity className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Semiología MTC & Reglas</h2>
          </div>
          <div className="text-sm text-gray-600 space-y-3">
            <div className="p-3 bg-[#F8F9F8] rounded-xl">
              <h4 className="font-semibold text-gray-800 text-xs uppercase tracking-wider text-[#2D5A47]">
                Diagnóstico Tradicional
              </h4>
              <p className="text-xs text-gray-500 mt-1">
                Inspección de Lengua (Cuerpo, Saburra), Palpación de Pulsos radiales (Cun, Guan, Chi) y Diferenciación de Síndromes Zang-Fu.
              </p>
            </div>

            <div className="p-3 bg-[#F8F9F8] rounded-xl">
              <h4 className="font-semibold text-gray-800 text-xs uppercase tracking-wider text-[#2D5A47]">
                Trazabilidad Ley N° 20.584
              </h4>
              <p className="text-xs text-gray-500 mt-1">
                Registro inmutable de accesos clínicos (`clinical.access_logs`) y validación de firma electrónica por tutor clínico.
              </p>
            </div>

            <div className="p-3 bg-emerald-50 border border-emerald-100 rounded-xl flex items-center gap-2 text-emerald-800 text-xs">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <span>Acreditación automática de horas prácticas con firma de tutor.</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
