import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Bot, FileText, Mail, DollarSign,
  Bell, Users, LogOut,
} from 'lucide-react';
import { useAuthStore } from '../../stores/auth-store';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Painel' },
  { to: '/agents', icon: Bot, label: 'Agentes' },
  { to: '/contracts', icon: FileText, label: 'Contratos' },
  { to: '/emails', icon: Mail, label: 'E-mails' },
  { to: '/cashflow', icon: DollarSign, label: 'Fluxo de Caixa' },
  { to: '/alerts', icon: Bell, label: 'Alertas' },
];

export function Sidebar() {
  const { user, logout } = useAuthStore();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 bg-slate-900 text-white flex flex-col z-40">
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-xl font-bold">LicitaBrasil</h1>
        <p className="text-sm text-slate-400 mt-1">Backoffice</p>
      </div>

      <nav className="flex-1 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-6 py-3 text-sm transition-colors ${
                isActive
                  ? 'bg-blue-600 text-white border-r-3 border-blue-400'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <item.icon size={18} />
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="p-4 border-t border-slate-700">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold">
            {user?.name?.charAt(0) || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{user?.name}</p>
            <p className="text-xs text-slate-400 truncate">{user?.role}</p>
          </div>
        </div>
        <button
          onClick={logout}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors w-full"
        >
          <LogOut size={16} />
          Sair
        </button>
      </div>
    </aside>
  );
}
