import { createContext, useContext, useEffect, useLayoutEffect, useState } from 'react'

export type ThemeMode = 'light' | 'dark' | 'system'

type ThemeCtx = {
  mode: ThemeMode
  resolved: 'light' | 'dark'
  setMode: (mode: ThemeMode) => void
  cycleMode: () => void
}

const STORAGE_KEY = 'avs-theme'

const Ctx = createContext<ThemeCtx>({
  mode: 'light',
  resolved: 'light',
  setMode: () => {},
  cycleMode: () => {},
})

function systemPrefersDark() {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') return systemPrefersDark() ? 'dark' : 'light'
  return mode
}

function applyTheme(resolved: 'light' | 'dark') {
  document.documentElement.classList.toggle('dark', resolved === 'dark')
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const stored = localStorage.getItem(STORAGE_KEY) as ThemeMode | null
    return stored === 'light' || stored === 'dark' || stored === 'system' ? stored : 'light'
  })
  const [resolved, setResolved] = useState<'light' | 'dark'>(() => resolveTheme(mode))

  useLayoutEffect(() => {
    const next = resolveTheme(mode)
    setResolved(next)
    applyTheme(next)
    localStorage.setItem(STORAGE_KEY, mode)
  }, [mode])

  useEffect(() => {
    if (mode !== 'system') return
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = () => {
      const next = mq.matches ? 'dark' : 'light'
      setResolved(next)
      applyTheme(next)
    }
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [mode])

  function setMode(next: ThemeMode) {
    setModeState(next)
  }

  function cycleMode() {
    setModeState((current) => {
      if (current === 'light') return 'dark'
      if (current === 'dark') return 'system'
      return 'light'
    })
  }

  return (
    <Ctx.Provider value={{ mode, resolved, setMode, cycleMode }}>
      {children}
    </Ctx.Provider>
  )
}

export function useTheme() {
  return useContext(Ctx)
}
