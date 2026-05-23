import { useState, useEffect } from 'react'
import client from '../../api/client'
import { useApp } from '../../stores/AppContext'

interface FileEntry {
  name: string
  path: string
  size: number
  is_dir: boolean
  mod_time: string
}

export default function FileBrowser() {
  const [path, setPath] = useState('/')
  const [files, setFiles] = useState<FileEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [viewFile, setViewFile] = useState<{ path: string; content: string } | null>(null)
  const { dispatch } = useApp()

  const load = async (targetPath: string) => {
    setLoading(true)
    try {
      const res = await client.post('/files/list', { path: targetPath })
      if (res.data.success) {
        setFiles(res.data.data)
        setPath(targetPath)
      } else {
        dispatch({ type: 'ADD_TOAST', payload: { message: res.data.error || 'Failed', type: 'error' } })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load('/')
  }, [])

  const view = async (filePath: string) => {
    try {
      const res = await client.get(`/files/view?path=${encodeURIComponent(filePath)}`)
      if (res.data.success) {
        setViewFile({ path: filePath, content: res.data.data })
      }
    } catch (e: any) {
      dispatch({ type: 'ADD_TOAST', payload: { message: e.response?.data?.error || 'Failed', type: 'error' } })
    }
  }

  const breadcrumbs = path.split('/').filter(Boolean)

  return (
    <div>
      <h1 className="font-serif text-3xl text-primary mb-6">File Browser</h1>

      <div className="flex items-center gap-2 mb-4 text-sm">
        <button
          onClick={() => load('/')}
          className="text-primary hover:underline"
        >
          /
        </button>
        {breadcrumbs.map((crumb, i) => {
          const crumbPath = '/' + breadcrumbs.slice(0, i + 1).join('/')
          return (
            <span key={i} className="flex items-center gap-2">
              <span className="text-text-muted">/</span>
              <button
                onClick={() => load(crumbPath)}
                className="text-primary hover:underline"
              >
                {crumb}
              </button>
            </span>
          )
        })}
      </div>

      <div className="bg-card-bg border border-border rounded-lg overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border">
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Name</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Size</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Modified</th>
              <th className="text-left px-4 py-3 text-text-muted font-semibold text-[11px] uppercase">Actions</th>
            </tr>
          </thead>
          <tbody>
            {path !== '/' && (
              <tr
                className="border-b border-border hover:bg-hover/50 cursor-pointer"
                onClick={() => {
                  const parent = path.substring(0, path.lastIndexOf('/')) || '/'
                  load(parent)
                }}
              >
                <td className="px-4 py-3 text-text-primary">..</td>
                <td className="px-4 py-3">-</td>
                <td className="px-4 py-3">-</td>
                <td className="px-4 py-3">-</td>
              </tr>
            )}
            {loading ? (
              <tr><td colSpan={4} className="px-4 py-8 text-center text-text-muted">Loading...</td></tr>
            ) : (
              files.map((f) => (
                <tr
                  key={f.path}
                  className="border-b border-border last:border-0 hover:bg-hover/50 cursor-pointer"
                  onClick={() => f.is_dir && load(f.path)}
                >
                  <td className="px-4 py-3 text-text-primary">
                    {f.is_dir ? '📁' : '📄'} {f.name}
                  </td>
                  <td className="px-4 py-3 text-text-muted">{f.is_dir ? '-' : formatBytes(f.size)}</td>
                  <td className="px-4 py-3 text-text-muted">{new Date(f.mod_time).toLocaleString()}</td>
                  <td className="px-4 py-3">
                    {!f.is_dir && (
                      <button
                        onClick={(e) => { e.stopPropagation(); view(f.path) }}
                        className="text-xs text-primary hover:underline"
                      >
                        View
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {viewFile && (
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-card-bg border border-border rounded-xl shadow-2xl w-full mx-4 max-w-4xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
              <h3 className="font-serif text-lg text-text-primary truncate">{viewFile.path}</h3>
              <button
                onClick={() => setViewFile(null)}
                className="text-text-muted hover:text-text-primary text-xl leading-none"
              >
                &times;
              </button>
            </div>
            <pre className="p-5 overflow-auto flex-1 text-xs font-mono text-text-secondary bg-code-bg">
              {viewFile.content}
            </pre>
          </div>
        </div>
      )}
    </div>
  )
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
