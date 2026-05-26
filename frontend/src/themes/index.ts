import { createSystem, defaultConfig } from '@chakra-ui/react'
import type { SystemConfig } from '@chakra-ui/react'
import { FACTION_PALETTES, type FactionKey, type FactionColors, FACTION_KEYS } from './palettes'

function semTokensFromPalette(c: FactionColors) {
  return {
    colors: {
      bg: c.bg,
      'bg.subtle': c.bgSubtle,
      'fg': c.fg,
      'fg.muted': c.fgMuted,
      'border': c.border,
      'border.subtle': c.borderSubtle,
      'primary.DEFAULT': c.primary,
      'primary.hover': c.primaryHover,
      'primary.subtle': c.primarySubtle,
      'accent': c.accent,
      'danger.DEFAULT': c.danger,
      'danger.subtle': c.dangerSubtle,
      'success.DEFAULT': c.success,
      'success.subtle': c.successSubtle,
      'warning.DEFAULT': c.warning,
      'warning.subtle': c.warningSubtle,
      'info.DEFAULT': c.info,
      'info.subtle': c.infoSubtle,
      'nav.bg': c.navBg,
      'card.bg': c.cardBg,
      'code.bg': c.codeBg,
    },
    shadows: {
      card: c.shadow,
    },
  }
}

type TokenRecord = Record<string, Record<string, { value: unknown }>>

function makeSemanticTokens(t: ReturnType<typeof semTokensFromPalette>): TokenRecord {
  const result: TokenRecord = {}
  for (const [category, entries] of Object.entries(t)) {
    result[category] = {}
    if (category === 'colors') {
      for (const [key, val] of Object.entries(entries as Record<string, string>)) {
        result.colors![key] = { value: val }
      }
    } else if (category === 'shadows') {
      for (const [key, val] of Object.entries(entries as Record<string, string>)) {
        result.shadows![key] = { value: val }
      }
    }
  }
  return result
}

function buildSystem(tokens: ReturnType<typeof semTokensFromPalette>) {
  const systemConfig: SystemConfig = {
    conditions: defaultConfig.conditions,
    utilities: defaultConfig.utilities,
    preflight: defaultConfig.preflight,
    cssVarsPrefix: defaultConfig.cssVarsPrefix,
    cssVarsRoot: defaultConfig.cssVarsRoot,
    globalCss: defaultConfig.globalCss,
    theme: {
      breakpoints: defaultConfig.theme?.breakpoints,
      keyframes: defaultConfig.theme?.keyframes,
      tokens: defaultConfig.theme?.tokens,
      semanticTokens: makeSemanticTokens(tokens) as any,
      recipes: defaultConfig.theme?.recipes,
      slotRecipes: defaultConfig.theme?.slotRecipes,
      textStyles: defaultConfig.theme?.textStyles,
      layerStyles: defaultConfig.theme?.layerStyles,
      animationStyles: defaultConfig.theme?.animationStyles,
    },
  }
  return createSystem(systemConfig, {})
}

type SystemCache = Record<string, Record<string, ReturnType<typeof createSystem>>>
const systemCache: SystemCache = {}

function getOrCreateSystem(faction: FactionKey, mode: 'day' | 'night') {
  const key = `${faction}:${mode}`
  if (!systemCache[faction]) systemCache[faction] = {}
  if (!systemCache[faction][mode]) {
    const palette = FACTION_PALETTES[faction][mode]
    systemCache[faction][mode] = buildSystem(semTokensFromPalette(palette))
  }
  return systemCache[faction][mode]
}

export function createDuneSystem(faction: FactionKey, mode: 'day' | 'night') {
  return getOrCreateSystem(faction, mode)
}

export function getFactionName(key: FactionKey): string {
  return FACTION_PALETTES[key]?.name ?? key
}

export { FACTION_KEYS, FACTION_PALETTES }
export type { FactionKey }
