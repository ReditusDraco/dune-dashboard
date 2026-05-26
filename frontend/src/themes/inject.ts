import { FACTION_PALETTES, type FactionKey, type FactionColors } from './palettes'

const TOKEN_MAP: [string, keyof FactionColors][] = [
  ['--chakra-colors-bg', 'bg'],
  ['--chakra-colors-bg-subtle', 'bgSubtle'],
  ['--chakra-colors-card-bg', 'cardBg'],
  ['--chakra-colors-nav-bg', 'navBg'],
  ['--chakra-colors-fg', 'fg'],
  ['--chakra-colors-fg-muted', 'fgMuted'],
  ['--chakra-colors-border', 'border'],
  ['--chakra-colors-border-subtle', 'borderSubtle'],
  ['--chakra-colors-primary-DEFAULT', 'primary'],
  ['--chakra-colors-primary-hover', 'primaryHover'],
  ['--chakra-colors-primary-subtle', 'primarySubtle'],
  ['--chakra-colors-accent', 'accent'],
  ['--chakra-colors-danger-DEFAULT', 'danger'],
  ['--chakra-colors-danger-subtle', 'dangerSubtle'],
  ['--chakra-colors-success-DEFAULT', 'success'],
  ['--chakra-colors-success-subtle', 'successSubtle'],
  ['--chakra-colors-warning-DEFAULT', 'warning'],
  ['--chakra-colors-warning-subtle', 'warningSubtle'],
  ['--chakra-colors-info-DEFAULT', 'info'],
  ['--chakra-colors-info-subtle', 'infoSubtle'],
  ['--chakra-colors-code-bg', 'codeBg'],
  ['--chakra-shadows-card', 'shadow'],
]

let injectedStyle: HTMLStyleElement | null = null

export function injectThemeVars(faction: FactionKey, mode: 'day' | 'night') {
  const palette = FACTION_PALETTES[faction]?.[mode]
  if (!palette) return

  const lines = TOKEN_MAP.map(([varName, key]) => {
    const value = palette[key]
    if (varName.startsWith('--chakra-shadows-')) {
      return `${varName}:${value};`
    }
    return `${varName}:${value};`
  })

  if (!injectedStyle) {
    injectedStyle = document.createElement('style')
    injectedStyle.id = 'dune-theme-vars'
    document.head.appendChild(injectedStyle)
  }

  injectedStyle.textContent = `:where(html, .chakra-theme) {\n  ${lines.join('\n  ')}\n}`
}
