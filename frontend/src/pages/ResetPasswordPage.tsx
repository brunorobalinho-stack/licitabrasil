import { useState } from 'react';
import { Link, useSearchParams, useNavigate } from 'react-router-dom';

export function ResetPasswordPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [senha, setSenha] = useState('');
  const [confirmar, setConfirmar] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (senha !== confirmar) {
      setError('As senhas não coincidem');
      return;
    }

    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, senha }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Erro ao redefinir senha');
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center px-4">
        <div className="w-full max-w-md rounded-xl border bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-900 text-center">
          <p className="text-red-600">Link inválido. Solicite um novo link de redefinição.</p>
          <Link to="/esqueci-senha" className="mt-4 inline-block font-medium text-primary hover:underline">
            Esqueci minha senha
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-[70vh] items-center justify-center px-4">
      <div className="w-full max-w-md rounded-xl border bg-white p-8 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <div className="mb-6 text-center">
          <h1 className="text-2xl font-bold">Redefinir senha</h1>
          <p className="mt-1 text-sm text-muted-foreground">Crie uma nova senha para sua conta</p>
        </div>

        {success ? (
          <div className="rounded-lg bg-green-50 p-4 text-sm text-green-700 dark:bg-green-950 dark:text-green-300">
            <p>Senha redefinida com sucesso!</p>
            <p className="mt-2">Redirecionando para o login...</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-600 dark:bg-red-950 dark:text-red-400">
                {error}
              </div>
            )}
            <div>
              <label htmlFor="senha" className="mb-1.5 block text-sm font-medium">Nova senha</label>
              <input
                id="senha"
                type="password"
                required
                minLength={6}
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800"
                placeholder="••••••"
              />
            </div>
            <div>
              <label htmlFor="confirmar" className="mb-1.5 block text-sm font-medium">Confirmar senha</label>
              <input
                id="confirmar"
                type="password"
                required
                minLength={6}
                value={confirmar}
                onChange={(e) => setConfirmar(e.target.value)}
                className="w-full rounded-lg border px-3 py-2.5 text-sm focus:border-primary focus:outline-none dark:border-gray-600 dark:bg-gray-800"
                placeholder="••••••"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-primary py-2.5 text-sm font-medium text-white hover:bg-primary/90 disabled:opacity-50 transition-colors"
            >
              {loading ? 'Redefinindo…' : 'Redefinir senha'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
