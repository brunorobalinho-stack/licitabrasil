import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/auth-store';

export function LoginPage() {
  const { login } = useAuthStore();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [senha, setSenha] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, senha);
      navigate('/');
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold">Entrar no LicitaBrasil</h1>
          <p className="mt-1 text-sm text-muted-foreground">Acesse sua conta para gerenciar alertas e favoritos</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium">Email</label>
            <input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800"
              placeholder="seu@email.com"
            />
          </div>

          <div>
            <label htmlFor="senha" className="mb-1.5 block text-sm font-medium">Senha</label>
            <input
              id="senha"
              type="password"
              required
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800"
              placeholder="••••••"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        <p className="mt-4 text-center text-sm text-muted-foreground">
          Não tem conta?{' '}
          <Link to="/registro" className="font-medium text-primary hover:underline">Cadastre-se</Link>
        </p>

        <div className="mt-4 rounded-lg bg-blue-50 p-3 text-xs text-blue-700 dark:bg-blue-950 dark:text-blue-300">
          <strong>Demo:</strong> demo@licitabrasil.com.br / 123456
        </div>
      </div>
    </div>
  );
}
