import React, { useState } from 'react';
import { useAuth } from './context/AuthContext';
import { Layout } from './components/layout/Layout';
import { LoginPage } from './pages/LoginPage';
import { DashboardPage } from './pages/DashboardPage';
import { AcademicPage } from './pages/AcademicPage';
import { ClinicalPage } from './pages/ClinicalPage';
import { FinancePage } from './pages/FinancePage';
import { HRPage } from './pages/HRPage';
import { LMSPage } from './pages/LMSPage';

export const App: React.FC = () => {
  const { user, isLoading } = useAuth();
  const [currentPage, setCurrentPage] = useState<string>('dashboard');

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#F8F9F8] flex items-center justify-center">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-[#2D5A47]"></div>
      </div>
    );
  }

  if (!user) {
    return <LoginPage />;
  }

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <DashboardPage />;
      case 'academic':
        return <AcademicPage />;
      case 'clinical':
        return <ClinicalPage />;
      case 'finance':
        return <FinancePage />;
      case 'hr':
        return <HRPage />;
      case 'lms':
        return <LMSPage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <Layout currentPage={currentPage} onNavigate={setCurrentPage}>
      {renderPage()}
    </Layout>
  );
};
