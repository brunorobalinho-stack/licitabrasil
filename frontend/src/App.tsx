import { Routes, Route } from 'react-router-dom';
import { useEffect } from 'react';
import { Header } from './components/layout/Header';
import { SearchPage } from './pages/SearchPage';
import { DashboardPage } from './pages/DashboardPage';
import { LicitacaoDetailPage } from './pages/LicitacaoDetailPage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { useAuthStore } from './stores/auth-store';

export function App() {
  const { loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Header />
      <main>
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/licitacao/:id" element={<LicitacaoDetailPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/registro" element={<RegisterPage />} />
        </Routes>
      </main>
      <footer className="border-t py-6 text-center text-sm text-muted-foreground dark:border-gray-800">
        <p>LicitaBrasil &copy; 2026 — Pesquisa unificada de licitações públicas</p>
        <p className="mt-1 text-xs">Dados públicos coletados de PNCP, Querido Diário e outras fontes oficiais</p>
      </footer>
    </div>
  );
}
