import { createContext, useCallback, useContext, useState } from 'react'

type Ctx = {
  open: boolean
  setOpen: (v: boolean) => void
  toggle: () => void
}

const CommandPaletteCtx = createContext<Ctx>({
  open: false,
  setOpen: () => {},
  toggle: () => {},
})

export function CommandPaletteProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false)
  const toggle = useCallback(() => setOpen((v) => !v), [])

  return (
    <CommandPaletteCtx.Provider value={{ open, setOpen, toggle }}>
      {children}
    </CommandPaletteCtx.Provider>
  )
}

export function useCommandPalette() {
  return useContext(CommandPaletteCtx)
}
