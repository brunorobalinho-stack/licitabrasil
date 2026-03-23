import { Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { Sidebar } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { AgentsPage } from './pages/AgentsPage';
import { ContractsPage } from './pages/ContractsPage';
import { EmailsPage } from './pages/EmailsPage';
import { CashFlowPage } from './pages/CashFlowPage';
import { AlertsPage } from './pages/AlertsPage';
import { LoginPage } from './pages/LoginPage';
import { useAuthStore } from './stores/auth-store';
import { Spinner } from './components/ui/Spinner';

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex">
      <Sidebar />
      <main className="flex-1 ml-64 p-6 min-h-screen">
        {children}
      </main>
    </div>
  );
}

export function App() {
  const { user, isLoading, loadUser } = useAuthStore();

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (!user) {
    return (
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <ProtectedLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/contracts" element={<ContractsPage />} />
        <Route path="/emails" element={<EmailsPage />} />
        <Route path="/cashflow" element={<CashFlowPage />} />
        <Route path="/alerts" element={<AlertsPage />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ProtectedLayout>
  );
}
