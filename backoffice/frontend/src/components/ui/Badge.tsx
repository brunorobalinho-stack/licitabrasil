import type { ReactNode } from 'react';

const variants: Record<string, string> = {
  info: 'bg-blue-100 text-blue-800',
  success: 'bg-emerald-100 text-emerald-800',
  warning: 'bg-amber-100 text-amber-800',
  critical: 'bg-red-100 text-red-800',
  default: 'bg-slate-100 text-slate-800',
  alta: 'bg-red-100 text-red-800',
  media: 'bg-amber-100 text-amber-800',
  baixa: 'bg-slate-100 text-slate-600',
  ativo: 'bg-emerald-100 text-emerald-800',
  vencido: 'bg-red-100 text-red-800',
  proximo_vencimento: 'bg-amber-100 text-amber-800',
  cancelado: 'bg-slate-100 text-slate-500',
  completed: 'bg-emerald-100 text-emerald-800',
  running: 'bg-blue-100 text-blue-800',
  failed: 'bg-red-100 text-red-800',
};

interface BadgeProps {
  variant?: string;
  children: ReactNode;
}

export function Badge({ variant = 'default', children }: BadgeProps) {
  const cls = variants[variant] || variants.default;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {children}
    </span>
  );
}
