import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,    // 5 min — dados ficam "fresh" por 5 min
      gcTime: 10 * 60 * 1000,      // 10 min — cache removido após 10 min sem uso
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});
