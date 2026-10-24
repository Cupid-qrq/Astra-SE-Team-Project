import { QueryClient } from '@tanstack/react-query'
import { createApiClient, type Session } from '../lib/api/client'
import { activateDraftAccount } from '../features/assignments/drafts'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: false, staleTime: 15_000, refetchOnWindowFocus: true },
    mutations: { retry: false },
  },
})
export const sessionKey = ['session'] as const
export function identityKey(session: Session) {
  const user = session.authenticated ? session.user : null
  return user ? `${user.user_id}:${user.role}:${user.status}:${user.revision}` : 'anonymous'
}
export function reconcileSession(next: Session): Session {
  const previous = queryClient.getQueryData<Session>(sessionKey)
  if (next.user && (!previous?.user || previous.user.user_id !== next.user.user_id))
    activateDraftAccount(next.user.user_id)
  if (previous && identityKey(previous) !== identityKey(next)) {
    const accountQueries = {
      predicate: (query: { queryKey: readonly unknown[] }) => query.queryKey[0] !== 'session',
    }
    void queryClient.cancelQueries(accountQueries)
    queryClient.removeQueries(accountQueries)
  }
  return next
}
export function clearSession() {
  void queryClient.cancelQueries()
  queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== 'session' })
  queryClient.setQueryData<Session>(sessionKey, {
    authenticated: false,
    user: null,
    csrf_token: '',
    server_time: new Date().toISOString(),
  })
}
const transport = createApiClient({ onUnauthorized: clearSession })
export const api = {
  ...transport,
  session: async () => reconcileSession(await transport.session()),
  login: async (...args: Parameters<typeof transport.login>) =>
    reconcileSession(await transport.login(...args)),
}
