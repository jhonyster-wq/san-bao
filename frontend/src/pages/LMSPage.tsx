import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { BookOpen, Video, Award, Clock } from 'lucide-react';

export const LMSPage: React.FC = () => {
  const [courses, setCourses] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchLMS = async () => {
      try {
        const res = await api.get('/lms/courses');
        setCourses(res.data?.data?.items || res.data?.data || []);
      } catch (err) {
        console.error('Error cargando cursos LMS:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchLMS();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">LMS • Aula Virtual & Formación Continua</h1>
          <p className="text-sm text-gray-500">Cursos Online, Materiales de Estudio y Evaluaciones San Bao</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {courses.length === 0 ? (
          <p className="text-sm text-gray-400 col-span-3 py-6 text-center">
            No hay cursos virtuales disponibles actualmente.
          </p>
        ) : (
          courses.map((c) => (
            <div key={c.id} className="bg-white rounded-2xl border border-gray-200 overflow-hidden shadow-sm flex flex-col">
              <div className="h-32 bg-gradient-to-r from-[#2D5A47] to-[#4E876E] p-4 flex items-end">
                <span className="text-xs font-semibold px-2.5 py-1 bg-white/20 backdrop-blur-sm text-white rounded-md">
                  {c.code}
                </span>
              </div>
              <div className="p-5 flex-1 flex flex-col justify-between space-y-3">
                <div>
                  <h3 className="font-bold text-gray-800 text-lg leading-snug">{c.title}</h3>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{c.description}</p>
                </div>
                <div className="pt-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" /> {c.duration_hours || 40} horas
                  </span>
                  <span className="text-emerald-700 font-semibold">Aula Habilitada</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
