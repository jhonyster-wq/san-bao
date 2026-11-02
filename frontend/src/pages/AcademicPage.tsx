import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { GraduationCap, BookOpen, UserCheck, Calendar } from 'lucide-react';

export const AcademicPage: React.FC = () => {
  const [programs, setPrograms] = useState<any[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [resPrograms, resStudents] = await Promise.all([
          api.get('/academic/programs'),
          api.get('/academic/students'),
        ]);
        setPrograms(resPrograms.data?.data?.items || resPrograms.data?.data || []);
        setStudents(resStudents.data?.data?.items || resStudents.data?.data || []);
      } catch (err) {
        console.error('Error cargando datos académicos:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Gestión Académica</h1>
          <p className="text-sm text-gray-500">Instituto de Medicina China Clásica SpA</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Programas Académicos */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <GraduationCap className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Carreras & Programas Formativos</h2>
          </div>
          <div className="space-y-3">
            {programs.length === 0 ? (
              <p className="text-sm text-gray-400">No hay programas registrados aún.</p>
            ) : (
              programs.map((prog) => (
                <div key={prog.id} className="p-3.5 bg-[#F8F9F8] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold px-2 py-0.5 bg-emerald-100 text-emerald-800 rounded">
                      {prog.code}
                    </span>
                    <h3 className="font-semibold text-gray-800 mt-1">{prog.name}</h3>
                    <span className="text-xs text-gray-500">{prog.degree_title}</span>
                  </div>
                  <span className="text-xs font-medium text-gray-400">
                    {prog.total_semesters} semestres
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Estudiantes Matriculados */}
        <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
          <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
            <UserCheck className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Expedientes de Alumnos</h2>
          </div>
          <div className="space-y-3">
            {students.length === 0 ? (
              <p className="text-sm text-gray-400">No hay estudiantes activos registrados.</p>
            ) : (
              students.map((st) => (
                <div key={st.id} className="p-3.5 bg-[#F8F9F8] rounded-xl flex items-center justify-between">
                  <div>
                    <span className="text-xs font-semibold px-2 py-0.5 bg-gray-200 text-gray-700 rounded">
                      {st.student_number}
                    </span>
                    <h3 className="font-semibold text-gray-800 mt-1">
                      {st.person?.first_name} {st.person?.last_name}
                    </h3>
                    <span className="text-xs text-gray-500">RUT: {st.person?.rut}</span>
                  </div>
                  <span className="text-xs font-semibold text-emerald-600 bg-emerald-50 px-2 py-1 rounded-full">
                    {st.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
