import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../services/api';
import { User, Company } from '../types';

interface AuthContextType {
  user: User | null;
  companies: Company[];
  activeCompany: Company | null;
  setActiveCompany: (company: Company) => void;
  login: (username: string, password: string) => Promise<boolean>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeCompany, setActiveCompanyState] = useState<Company | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = localStorage.getItem('sanbao_token');
    const storedUser = localStorage.getItem('sanbao_user');
    const storedCompanies = localStorage.getItem('sanbao_companies');
    const storedCompanyId = localStorage.getItem('sanbao_active_company_id');

    if (token && storedUser && storedCompanies) {
      try {
        const parsedUser = JSON.parse(storedUser);
        const parsedCompanies: Company[] = JSON.parse(storedCompanies);
        setUser(parsedUser);
        setCompanies(parsedCompanies);

        const current = parsedCompanies.find((c) => c.id === storedCompanyId) || parsedCompanies[0];
        setActiveCompanyState(current || null);
      } catch (e) {
        console.error('Error restaurando sesión:', e);
        logout();
      }
    }
    setIsLoading(false);
  }, []);

  const setActiveCompany = (company: Company) => {
    setActiveCompanyState(company);
    localStorage.setItem('sanbao_active_company_id', company.id);
  };

  const login = async (username: string, password: string): Promise<boolean> => {
    try {
      const response = await api.post('/institutional/auth/login', { username, password });
      if (response.data.success) {
        const { access_token, user: userData, available_companies } = response.data.data;
        localStorage.setItem('sanbao_token', access_token);
        localStorage.setItem('sanbao_user', JSON.stringify(userData));
        localStorage.setItem('sanbao_companies', JSON.stringify(available_companies));

        setUser(userData);
        setCompanies(available_companies);

        if (available_companies.length > 0) {
          const defaultCompany = available_companies[0];
          setActiveCompanyState(defaultCompany);
          localStorage.setItem('sanbao_active_company_id', defaultCompany.id);
        }
        return true;
      }
      return false;
    } catch (err) {
      console.error('Error en autenticación:', err);
      return false;
    }
  };

  const logout = () => {
    localStorage.removeItem('sanbao_token');
    localStorage.removeItem('sanbao_user');
    localStorage.removeItem('sanbao_companies');
    localStorage.removeItem('sanbao_active_company_id');
    setUser(null);
    setCompanies([]);
    setActiveCompanyState(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        companies,
        activeCompany,
        setActiveCompany,
        login,
        logout,
        isLoading,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth debe ser utilizado dentro de un AuthProvider');
  }
  return context;
};
