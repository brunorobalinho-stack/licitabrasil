import { Link, useNavigate } from 'react-router-dom';
import { Search, Bell, Star, LayoutDashboard, LogOut, Menu, X, Sun, Moon } from 'lucide-react';
import { useState, useEffect } from 'react';
import { useAuthStore } from '../../stores/auth-store';

export function Header() {
  const { user, isAuthenticated, logout } = useAuthStore();
  const navigate = useNavigate();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dark, setDark] = useState(() => document.documentElement.classList.contains('dark'));

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
  }, [dark]);

  const handleLogout = () => {
    logout();
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-50 border-b bg-white/80 backdrop-blur dark:bg-gray-950/80 dark:border-gray-800">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4">
        {/* Logo */}
        <Link to="/" className="flex items-center gap-2 font-bold text-xl text-primary">
          <span className="text-2xl">🏛️</span>
          <span>Licita<span className="text-green-600">Brasil</span></span>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-6">
          <Link to="/" className="flex items-center gap-1.5 text-sm font-medium hover:text-primary transition-colors">
            <Search size={16} /> Buscar
          </Link>
          <Link to="/dashboard" className="flex items-center gap-1.5 text-sm font-medium hover:text-primary transition-colors">
            <LayoutDashboard size={16} /> Dashboard
          </Link>
          {isAuthenticated && (
            <>
              <Link to="/favoritos" className="flex items-center gap-1.5 text-sm font-medium hover:text-primary transition-colors">
                <Star size={16} /> Favoritos
              </Link>
              <Link to="/alertas" className="flex items-center gap-1.5 text-sm font-medium hover:text-primary transition-colors">
                <Bell size={16} /> Alertas
              </Link>
            </>
          )}
        </nav>

        {/* Right side */}
        <div className="hidden md:flex items-center gap-3">
          <button
            onClick={() => setDark(!dark)}
            className="rounded-lg p-2 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label="Alternar tema"
          >
            {dark ? <Sun size={18} /> : <Moon size={18} />}
          </button>

          {isAuthenticated ? (
            <div className="flex items-center gap-3">
              <span className="text-sm text-muted-foreground">{user?.nome}</span>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                <LogOut size={16} /> Sair
              </button>
            </div>
          ) : (
            <div className="flex gap-2">
              <Link
                to="/login"
                className="rounded-lg px-4 py-2 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
              >
                Entrar
              </Link>
              <Link
                to="/registro"
                className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-white hover:bg-primary/90 transition-colors"
              >
                Cadastrar
              </Link>
            </div>
          )}
        </div>

        {/* Mobile menu button */}
        <button className="md:hidden p-2" onClick={() => setMobileOpen(!mobileOpen)}>
          {mobileOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile nav */}
      {mobileOpen && (
        <nav className="md:hidden border-t bg-white dark:bg-gray-950 p-4 space-y-3">
          <Link to="/" className="block py-2 text-sm font-medium" onClick={() => setMobileOpen(false)}>🔍 Buscar</Link>
          <Link to="/dashboard" className="block py-2 text-sm font-medium" onClick={() => setMobileOpen(false)}>📊 Dashboard</Link>
          {isAuthenticated && (
            <>
              <Link to="/favoritos" className="block py-2 text-sm font-medium" onClick={() => setMobileOpen(false)}>⭐ Favoritos</Link>
              <Link to="/alertas" className="block py-2 text-sm font-medium" onClick={() => setMobileOpen(false)}>🔔 Alertas</Link>
              <button onClick={handleLogout} className="block py-2 text-sm font-medium text-red-600">Sair</button>
            </>
          )}
          {!isAuthenticated && (
            <Link to="/login" className="block py-2 text-sm font-medium text-primary" onClick={() => setMobileOpen(false)}>Entrar / Cadastrar</Link>
          )}
        </nav>
      )}
    </header>
  );
}
