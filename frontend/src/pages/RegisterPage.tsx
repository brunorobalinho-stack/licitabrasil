import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/auth-store';

export function RegisterPage() {
  const { register } = useAuthStore();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', nome: '', senha: '', empresa: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await register(form);
      navigate('/');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const set = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [field]: e.target.value }));

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold">Criar Conta</h1>
          <p className="mt-1 text-sm text-muted-foreground">Cadastre-se para salvar buscas e receber alertas</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="nome" className="mb-1.5 block text-sm font-medium">Nome completo</label>
            <input id="nome" required value={form.nome} onChange={set('nome')}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800" />
          </div>

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium">Email</label>
            <input id="email" type="email" required value={form.email} onChange={set('email')}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800" />
          </div>

          <div>
            <label htmlFor="empresa" className="mb-1.5 block text-sm font-medium">Empresa (opcional)</label>
            <input id="empresa" value={form.empresa} onChange={set('empresa')}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800" />
          </div>

          <div>
            <label htmlFor="senha" className="mb-1.5 block text-sm font-medium">Senha (mín. 6 caracteres)</label>
            <input id="senha" type="password" required minLength={6} value={form.senha} onChange={set('senha')}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800" />
          </div>

          <button type="submit" disabled={loading}
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors">
            {loading ? 'Criando conta…' : 'Cadastrar'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          Já tem conta? <Link to="/login" className="font-medium text-primary hover:underline">Entrar</Link>
        </p>
      </div>
    </div>
  );
}
