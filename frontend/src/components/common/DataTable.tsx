import { ReactNode, useState } from 'react'
import { Table, Flex, Text, Spinner } from '@chakra-ui/react'
import { FiChevronUp, FiChevronDown } from 'react-icons/fi'

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
      sorted.sort((a, b) => {
        const av = (a as any)[col.accessor as string]
        const bv = (b as any)[col.accessor as string]
        if (av == null && bv == null) return 0
        if (av == null) return sortDir === 'asc' ? 1 : -1
        if (bv == null) return sortDir === 'asc' ? -1 : 1
        if (typeof av === 'string') {
          return sortDir === 'asc' ? av.localeCompare(bv) : bv.localeCompare(av)
        }
        if (typeof av === 'number') {
          return sortDir === 'asc' ? av - bv : bv - av
        }
        return 0
      })
    }
  }

  const getCellValue = (row: T, col: Column<T>): string => {
    if (typeof col.accessor === 'function') return ''
    return String((row as any)[col.accessor] ?? '')
  }

  const getCellNode = (row: T, col: Column<T>): ReactNode => {
    if (typeof col.accessor === 'function') return col.accessor(row)
    return String((row as any)[col.accessor] ?? '')
  }

  return (
    <Table.ScrollArea borderWidth="1px" borderColor="border" borderRadius="lg">
      <Table.Root variant="line" size="sm" stickyHeader>
        <Table.Header>
          <Table.Row bg="bg.subtle">
            {columns.map((col) => (
              <Table.ColumnHeader
                key={col.header}
                onClick={() => handleSort(col.header)}
                cursor="pointer"
                userSelect="none"
                textTransform="uppercase"
                fontSize="2xs"
                letterSpacing="wider"
                fontWeight="semibold"
                color="fg.muted"
                py={3}
                px={4}
                _hover={{ color: 'fg' }}
                style={{ width: col.width }}
              >
                <Flex align="center" gap={1}>
                  {col.header}
                  {sortCol === col.header && (
                    <Text as="span" color="primary.DEFAULT">
                      {sortDir === 'asc' ? <FiChevronUp size={10} /> : <FiChevronDown size={10} />}
                    </Text>
                  )}
                </Flex>
              </Table.ColumnHeader>
            ))}
          </Table.Row>
        </Table.Header>
        <Table.Body>
          {loading ? (
            <Table.Row>
              <Table.Cell colSpan={columns.length} textAlign="center" py={8}>
                <Flex align="center" justify="center" gap={2} color="fg.muted">
                  <Spinner size="sm" />
                  <Text fontSize="sm">Loading...</Text>
                </Flex>
              </Table.Cell>
            </Table.Row>
          ) : sorted.length === 0 ? (
            <Table.Row>
              <Table.Cell colSpan={columns.length} textAlign="center" py={8} color="fg.muted" fontSize="sm">
                No results found
              </Table.Cell>
            </Table.Row>
          ) : (
            sorted.map((row, i) => (
              <Table.Row
                key={i}
                onClick={() => onRowClick?.(row)}
                cursor={onRowClick ? 'pointer' : 'default'}
                _hover={{ bg: 'bg.subtle' }}
                borderBottomWidth="1px"
                borderColor="border"
                bg={i % 2 === 0 ? 'transparent' : 'bg.subtle'}
              >
                {columns.map((col) => (
                  <Table.Cell key={col.header} py={2.5} px={4} fontSize="sm">
                    {getCellNode(row, col)}
                  </Table.Cell>
                ))}
              </Table.Row>
            ))
          )}
        </Table.Body>
      </Table.Root>
    </Table.ScrollArea>
  )
}
