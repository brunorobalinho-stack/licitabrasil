import { create } from 'zustand';
import type { Usuario } from '../types';
import { auth } from '../services/api';

interface AuthState {
  user: Usuario | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, senha: string) => Promise<void>;
  register: (data: { email: string; nome: string; senha: string; empresa?: string }) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  loading: true,
  isAuthenticated: auth.isAuthenticated(),

  async login(email, senha) {
    const user = await auth.login(email, senha);
    set({ user, isAuthenticated: true });
  },

  async register(data) {
    const user = await auth.register(data);
    set({ user, isAuthenticated: true });
  },

  logout() {
    auth.logout();
    set({ user: null, isAuthenticated: false });
  },

  async loadUser() {
    if (!auth.isAuthenticated()) {
      set({ loading: false });
      return;
    }
    try {
      const user = await auth.me();
      set({ user, isAuthenticated: true, loading: false });
    } catch {
      set({ user: null, isAuthenticated: false, loading: false });
    }
  },
}));
