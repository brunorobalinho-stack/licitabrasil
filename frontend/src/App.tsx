import { Routes, Route } from 'react-router-dom';
import { useEffect, lazy, Suspense } from 'react';
import { Header } from './components/layout/Header';
import { SearchPage } from './pages/SearchPage';
import { useAuthStore } from './stores/auth-store';
import { useFavoritesStore } from './stores/favorites-store';

// Lazy-loaded routes (not needed on initial page load)
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const LicitacaoDetailPage = lazy(() => import('./pages/LicitacaoDetailPage').then(m => ({ default: m.LicitacaoDetailPage })));
const LoginPage = lazy(() => import('./pages/LoginPage').then(m => ({ default: m.LoginPage })));
const RegisterPage = lazy(() => import('./pages/RegisterPage').then(m => ({ default: m.RegisterPage })));
const FavoritosPage = lazy(() => import('./pages/FavoritosPage').then(m => ({ default: m.FavoritosPage })));
const ForgotPasswordPage = lazy(() => import('./pages/ForgotPasswordPage').then(m => ({ default: m.ForgotPasswordPage })));
const ResetPasswordPage = lazy(() => import('./pages/ResetPasswordPage').then(m => ({ default: m.ResetPasswordPage })));
const ScraperStatusPage = lazy(() => import('./pages/ScraperStatusPage').then(m => ({ default: m.ScraperStatusPage })));

function PageFallback() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
    </div>
  );
}

export function App() {
  const { loadUser } = useAuthStore();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const loadFavorites = useFavoritesStore((s) => s.load);
  const clearFavorites = useFavoritesStore((s) => s.clear);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (isAuthenticated) {
      loadFavorites();
    } else {
      clearFavorites();
    }
  }, [isAuthenticated, loadFavorites, clearFavorites]);

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-950">
      <Header />
      <main>
        <Suspense fallback={<PageFallback />}>
          <Routes>
            <Route path="/" element={<SearchPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
            <Route path="/licitacao/:id" element={<LicitacaoDetailPage />} />
            <Route path="/favoritos" element={<FavoritosPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/registro" element={<RegisterPage />} />
            <Route path="/esqueci-senha" element={<ForgotPasswordPage />} />
            <Route path="/redefinir-senha" element={<ResetPasswordPage />} />
            <Route path="/scrapers" element={<ScraperStatusPage />} />
          </Routes>
        </Suspense>
      </main>
      <footer className="border-t py-6 text-center text-sm text-muted-foreground dark:border-gray-800">
        <p>LicitaBrasil &copy; 2026 — Pesquisa unificada de licitações públicas</p>
        <p className="mt-1 text-xs">Dados públicos coletados de PNCP, Querido Diário e outras fontes oficiais</p>
      </footer>
    </div>
  );
}
