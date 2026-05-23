import { ReactNode, useState } from 'react'

interface Column<T> {
  header: string
  accessor: keyof T | ((row: T) => ReactNode)
  width?: string
}

interface DataTableProps<T> {
  columns: Column<T>[]
  data: T[]
  onRowClick?: (row: T) => void
  loading?: boolean
}

export default function DataTable<T extends object>({
  columns,
  data,
  onRowClick,
  loading,
}: DataTableProps<T>) {
  const [sortCol, setSortCol] = useState<string | null>(null)
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  const handleSort = (header: string) => {
    if (sortCol === header) {
      setSortDir(sortDir === 'asc' ? 'desc' : 'asc')
    } else {
      setSortCol(header)
      setSortDir('asc')
    }
  }

  let sorted = [...data]
  if (sortCol) {
    const col = columns.find((c) => c.header === sortCol)
    if (col && typeof col.accessor === 'string') {
      sorted.sort((a: any, b: any) => {
        const av = a[col.accessor]
        const bv = b[col.accessor]
        if (av == null && bv == null) return 0
        if (av == null) return sortDir === 'asc' ? 1 : -1
        if (bv == null) return sortDir === 'asc' ? -1 : 1
        if (typeof av === 'string') {
          return sortDir === 'asc'
            ? av.localeCompare(bv)
            : bv.localeCompare(av)
        }
        if (typeof av === 'number') {
          return sortDir === 'asc' ? av - bv : bv - av
        }
        return 0
      })
    }
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.header}
                className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase tracking-wider cursor-pointer hover:text-text-primary select-none"
                style={{ width: col.width }}
                onClick={() => handleSort(col.header)}
              >
                <div className="flex items-center gap-1">
                  {col.header}
                  {sortCol === col.header && (
                    <span className="text-primary">
                      {sortDir === 'asc' ? ' ▲' : ' ▼'}
                    </span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-text-muted">
                Loading...
              </td>
            </tr>
          ) : sorted.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-8 text-center text-text-muted">
                No results found
              </td>
            </tr>
          ) : (
            sorted.map((row, i) => (
              <tr
                key={i}
                onClick={() => onRowClick?.(row)}
                className={`border-b border-border last:border-0 transition-colors ${
                  onRowClick ? 'cursor-pointer hover:bg-hover' : 'hover:bg-hover/50'
                }`}
              >
                {columns.map((col) => (
                  <td key={col.header} className="px-4 py-3 whitespace-nowrap">
                    {typeof col.accessor === 'function'
                      ? col.accessor(row)
                      : String(row[col.accessor] ?? '')}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}
