import { describe, it, expect, vi, beforeEach } from 'vitest';

vi.mock('../src/services/api', () => ({
  auth: {
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    me: vi.fn(),
  },
  ApiError: class extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

vi.mock('../src/lib/query-client', () => ({
  queryClient: {
    invalidateQueries: vi.fn(),
    clear: vi.fn(),
  },
}));

import { useAuthStore } from '../src/stores/auth-store';
import { auth } from '../src/services/api';

const mockAuth = vi.mocked(auth);

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ user: null, isAuthenticated: false, loading: true });
});

describe('auth-store', () => {
  it('starts with no user and loading=true', () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(true);
    expect(state.isAuthenticated).toBe(false);
  });

  it('login sets user and isAuthenticated', async () => {
    const user = { id: 'u1', email: 'test@test.com', nome: 'Test' };
    mockAuth.login.mockResolvedValue(user as any);

    await useAuthStore.getState().login('test@test.com', '123456');

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(true);
    expect(mockAuth.login).toHaveBeenCalledWith('test@test.com', '123456');
  });

  it('register sets user and isAuthenticated', async () => {
    const user = { id: 'u1', email: 'new@test.com', nome: 'New' };
    mockAuth.register.mockResolvedValue(user as any);

    await useAuthStore.getState().register({ email: 'new@test.com', nome: 'New', senha: '123456' });

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(true);
  });

  it('logout clears user and calls server', async () => {
    useAuthStore.setState({ user: { id: 'u1' } as any, isAuthenticated: true });

    await useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(mockAuth.logout).toHaveBeenCalled();
  });

  it('loadUser fetches user profile via /me', async () => {
    const user = { id: 'u1', email: 'test@test.com', nome: 'Test' };
    mockAuth.me.mockResolvedValue(user as any);

    await useAuthStore.getState().loadUser();

    const state = useAuthStore.getState();
    expect(state.user).toEqual(user);
    expect(state.isAuthenticated).toBe(true);
    expect(state.loading).toBe(false);
  });

  it('loadUser sets not authenticated when /me fails', async () => {
    mockAuth.me.mockRejectedValue(new Error('Unauthorized'));

    await useAuthStore.getState().loadUser();

    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.loading).toBe(false);
  });
});
