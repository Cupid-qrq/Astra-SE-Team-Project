import type { ReactNode } from 'react'
import { StatePanel } from './StatePanel'
export type Column<T> = { key: string; heading: string; render: (row: T) => ReactNode }
type Props<T> = {
  caption: string
  rows: T[]
  columns: Column<T>[]
  rowKey: (row: T) => string
  empty: string
}
export function DataTable<T>({ caption, rows, columns, rowKey, empty }: Props<T>) {
  if (!rows.length) return <StatePanel kind="empty" title={empty} />
  return (
    <div className="table-scroll" role="region" aria-label={caption} tabIndex={0}>
      <table>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th scope="col" key={column.key}>
                {column.heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((column) => (
                <td key={column.key}>{column.render(row)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
