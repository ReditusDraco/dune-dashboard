import { useEffect, useRef } from 'react'
import { Box, Heading } from '@chakra-ui/react'
import { Terminal as XTerm } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import { io, Socket } from 'socket.io-client'
import 'xterm/css/xterm.css'

export default function Terminal() {
  const containerRef = useRef<HTMLDivElement>(null)
  const termRef = useRef<XTerm | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const socketRef = useRef<Socket | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const term = new XTerm({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: 'Roboto Mono, monospace',
      theme: {
        background: '#1a1a1a',
        foreground: '#f0f0f0',
        cursor: '#d4af37',
        selectionBackground: '#404040',
        black: '#1a1a1a',
        red: '#c0392b',
        green: '#27ae60',
        yellow: '#f39c12',
        blue: '#4a90d9',
        magenta: '#9966cc',
        cyan: '#20b2aa',
        white: '#f0f0f0',
        brightBlack: '#404040',
        brightRed: '#ff6b6b',
        brightGreen: '#6abf6a',
        brightYellow: '#e8c962',
        brightBlue: '#6baee8',
        brightMagenta: '#c8a8e8',
        brightCyan: '#7de8d8',
        brightWhite: '#ffffff',
      },
    })

    const fitAddon = new FitAddon()
    term.loadAddon(fitAddon)
    term.open(containerRef.current)
    fitAddon.fit()

    termRef.current = term
    fitAddonRef.current = fitAddon

    const socket = io({
      transports: ['websocket'],
    })
    socketRef.current = socket

    socket.on('connect', () => {
      term.writeln('Connecting to remote shell...')
      socket.emit('shell_create', { type: 'vm' })
    })

    socket.on('shell_created', (data: any) => {
      if (data.success) {
        term.writeln('\r\nConnected to remote shell.')
      } else {
        term.writeln(`\r\nFailed to create shell: ${data.error || 'Unknown error'}`)
      }
    })

    socket.on('shell_output', (data: any) => {
      if (data.data) {
        term.write(data.data)
      }
    })

    socket.on('disconnect', () => {
      term.writeln('\r\n[Disconnected]')
    })

    term.onData((data) => {
      socket.emit('shell_input', { data })
    })

    const handleResize = () => {
      fitAddon.fit()
    }
    window.addEventListener('resize', handleResize)

    return () => {
      window.removeEventListener('resize', handleResize)
      socket.emit('shell_disconnect')
      socket.disconnect()
      term.dispose()
    }
  }, [])

  return (
    <Box h="calc(100vh - 140px)" display="flex" flexDirection="column">
      <Heading
        as="h1"
        fontSize="3xl"
        fontFamily="Playfair Display, serif"
        color="primary.DEFAULT"
        mb={4}
      >
        Remote Shell
      </Heading>
      <Box
        ref={containerRef}
        flex={1}
        bg="#1a1a1a"
        borderRadius="lg"
        borderWidth="1px"
        borderColor="border"
        overflow="hidden"
      />
    </Box>
  )
}
