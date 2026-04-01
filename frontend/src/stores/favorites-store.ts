import { create } from 'zustand';
import { favoritos } from '../services/api';

interface FavoritesState {
  /** Map licitacaoId → favoritoId for O(1) lookup and deletion */
  ids: Record<string, string>;
  loading: boolean;

  load: () => Promise<void>;
  toggle: (licitacaoId: string) => Promise<void>;
  isFavorite: (licitacaoId: string) => boolean;
  clear: () => void;
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  ids: {},
  loading: false,

  async load() {
    set({ loading: true });
    try {
      const res = await favoritos.list(1, 100);
      const ids: Record<string, string> = {};
      for (const item of res.data) {
        ids[item.licitacaoId] = item.id;
      }
      set({ ids, loading: false });
    } catch {
      set({ loading: false });
    }
  },

  async toggle(licitacaoId: string) {
    const { ids } = get();
    const existingId = ids[licitacaoId];

    if (existingId) {
      // Optimistic remove
      set((s) => {
        const newIds = { ...s.ids };
        delete newIds[licitacaoId];
        return { ids: newIds };
      });
      try {
        await favoritos.remove(existingId);
      } catch {
        // Revert on error
        set((s) => ({ ids: { ...s.ids, [licitacaoId]: existingId } }));
      }
    } else {
      try {
        const res = await favoritos.add(licitacaoId);
        set((s) => ({ ids: { ...s.ids, [licitacaoId]: res.id } }));
      } catch {
        // No revert needed — we didn't optimistically add
      }
    }
  },

  isFavorite(licitacaoId: string) {
    return licitacaoId in get().ids;
  },

  clear() {
    set({ ids: {} });
  },
}));
