import React, { useEffect, useState } from 'react';
import api from '../services/api';
import { useAuth } from '../context/AuthContext';
import { Receipt, FileText, CheckCircle2, Clock, Send } from 'lucide-react';

export const FinancePage: React.FC = () => {
  const { activeCompany } = useAuth();
  const [dtes, setDtes] = useState<any[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const fetchFinance = async () => {
      try {
        const url = activeCompany?.id
          ? `/integrations/dte?company_id=${activeCompany.id}`
          : '/integrations/dte';
        const res = await api.get(url);
        setDtes(res.data || []);
      } catch (err) {
        console.error('Error cargando DTEs:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchFinance();
  }, [activeCompany]);

  const formatCLP = (amount: number) => {
    return new Intl.NumberFormat('es-CL', {
      style: 'currency',
      currency: 'CLP',
      maximumFractionDigits: 0,
    }).format(amount || 0);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Finanzas & Facturación Electrónica DTE</h1>
          <p className="text-sm text-gray-500">Documentos Tributarios Electrónicos SII • Boletas y Facturas</p>
        </div>
      </div>

      <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm space-y-4">
        <div className="flex items-center justify-between border-b border-gray-100 pb-3">
          <div className="flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#2D5A47]" />
            <h2 className="font-bold text-gray-800">Documentos Tributarios Emitidos</h2>
          </div>
          <span className="text-xs font-semibold px-2.5 py-1 bg-gray-100 text-gray-700 rounded-full">
            Folios SII Asignados
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-400 uppercase">
                <th className="py-3 px-4 font-semibold">Tipo DTE</th>
                <th className="py-3 px-4 font-semibold">Folio</th>
                <th className="py-3 px-4 font-semibold">Emisor / Receptor</th>
                <th className="py-3 px-4 font-semibold">Monto Total</th>
                <th className="py-3 px-4 font-semibold">Estado SII</th>
                <th className="py-3 px-4 font-semibold">Timbre TED</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {dtes.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-gray-400">
                    No hay documentos tributarios emitidos para esta sociedad.
                  </td>
                </tr>
              ) : (
                dtes.map((doc) => (
                  <tr key={doc.id} className="hover:bg-gray-50 transition-colors">
                    <td className="py-3.5 px-4">
                      <span className="font-semibold text-gray-800">
                        {doc.dte_type === 41
                          ? 'Boleta Exenta (41)'
                          : doc.dte_type === 39
                          ? 'Boleta Afecta (39)'
                          : doc.dte_type === 33
                          ? 'Factura Afecta (33)'
                          : `DTE ${doc.dte_type}`}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono font-bold text-[#2D5A47]">#{doc.folio}</td>
                    <td className="py-3.5 px-4">
                      <div className="font-medium text-gray-800">{doc.receiver_name}</div>
                      <div className="text-xs text-gray-400">{doc.receiver_rut}</div>
                    </td>
                    <td className="py-3.5 px-4 font-bold text-gray-900">
                      {formatCLP(doc.total_amount)}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-50 text-emerald-700">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        {doc.sii_status}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-xs font-mono text-gray-400 truncate max-w-[150px]">
                      {doc.digital_stamp ? 'TED OK' : 'Pendiente'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
