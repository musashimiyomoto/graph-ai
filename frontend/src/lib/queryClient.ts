import { QueryClient } from '@tanstack/react-query'

import type { ApiError } from './types'

// Registers ApiError as the default error type for every useQuery/
// useMutation call app-wide, so call sites don't repeat `<T, ApiError>`
// generics — request() in api.ts always rejects with this shape.
declare module '@tanstack/react-query' {
  interface Register {
    defaultError: ApiError
  }
}

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Server state here changes only through this app's own mutations (no
      // other client writes concurrently), so a short staleness window is
      // enough to dedupe refetches across repeated modal opens/mounts
      // without risking visibly stale data.
      staleTime: 30_000,
      retry: false,
    },
  },
})
