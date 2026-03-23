import { create } from 'zustand';
import { api } from '../services/api';
import type { User } from '../types';

interface AuthState {
  user: User | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isLoading: true,

  login: async (email, password) => {
    const data = await api.login(email, password);
    localStorage.setItem('backoffice_token', data.access_token);
    set({ user: data.user });
  },

  logout: () => {
    localStorage.removeItem('backoffice_token');
    set({ user: null });
  },

  loadUser: async () => {
    const token = localStorage.getItem('backoffice_token');
    if (!token) {
      set({ isLoading: false });
      return;
    }
    try {
      const user = await api.me();
      set({ user, isLoading: false });
    } catch {
      localStorage.removeItem('backoffice_token');
      set({ user: null, isLoading: false });
    }
  },
}));
