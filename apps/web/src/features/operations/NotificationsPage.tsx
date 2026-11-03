import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../../app/runtime'
import { Button } from '../../components/ui/Button'
import { StatePanel } from '../../components/ui/StatePanel'
import { beijingTime } from '../assignments/time'

export function NotificationsPage() {
  const cache = useQueryClient()
  const query = useInfiniteQuery({
    queryKey: ['notifications'],
    queryFn: ({ pageParam }) => api.notifications(pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (page) => page.next_cursor || undefined,
    refetchInterval: 20000,
  })
  const read = useMutation({
    mutationFn: api.markNotificationRead,
    onSuccess: () => cache.invalidateQueries({ queryKey: ['notifications'] }),
  })
  return (
    <>
      <h1>通知</h1>
      {query.isPending ? (
        <StatePanel kind="loading" title="正在读取通知…" />
      ) : query.isError ? (
        <StatePanel kind="error" title="通知不可用" description={query.error.message} />
      ) : (
        <>
          {!query.data.pages.some((page) => page.items.length) && (
            <StatePanel kind="empty" title="暂无通知" />
          )}
          {query.data.pages
            .flatMap((page) => page.items)
            .map((item) => (
              <article className="panel stack" key={item.notification_id}>
                <h2>{item.title}</h2>
                <p className="template-text">{item.body}</p>
                <p>
                  {beijingTime(item.created_at)} · {item.read_at ? '已读' : '未读'}
                </p>
                {!item.read_at && (
                  <Button onClick={() => read.mutate(item.notification_id)} busy={read.isPending}>
                    标记已读
                  </Button>
                )}
              </article>
            ))}
          {query.hasNextPage && (
            <Button onClick={() => void query.fetchNextPage()}>加载更多通知</Button>
          )}
        </>
      )}
      {read.error && <p role="alert">{read.error.message}</p>}
    </>
  )
}
