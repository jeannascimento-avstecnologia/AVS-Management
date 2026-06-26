import { useEffect, useRef, useState } from 'react'
import { Search } from 'lucide-react'
import { useCommandPalette } from '@/hooks/useCommandPalette'
import { topbarActionBtnClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

export function ExpandableSearchTrigger() {
  const { setOpen } = useCommandPalette()
  const [expanded, setExpanded] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (expanded) {
      inputRef.current?.focus()
    }
  }, [expanded])

  function openPalette() {
    setOpen(true)
    setExpanded(false)
  }

  function handleBlur() {
    window.setTimeout(() => setExpanded(false), 120)
  }

  return (
    <>
      <button
        type="button"
        aria-label="Buscar"
        className={cn(topbarActionBtnClass, 'h-10 w-10 sm:hidden')}
        onClick={openPalette}
      >
        <Search className="h-4 w-4" />
      </button>

      <div
        className={cn(
          'hidden overflow-hidden transition-[width] duration-300 ease-out sm:block',
          expanded ? 'w-[220px]' : 'w-10',
        )}
      >
        {expanded ? (
          <div className={cn(topbarActionBtnClass, 'h-10 w-full justify-start gap-2 px-3')}>
            <Search className="h-4 w-4 shrink-0" />
            <input
              ref={inputRef}
              readOnly
              placeholder="Buscar…"
              className="min-w-0 flex-1 bg-transparent text-sm font-medium text-slate-900 outline-none placeholder:text-slate-500"
              onFocus={openPalette}
              onKeyDown={(e) => {
                if (e.key === 'Enter') openPalette()
                if (e.key === 'Escape') setExpanded(false)
              }}
              onBlur={handleBlur}
            />
          </div>
        ) : (
          <button
            type="button"
            aria-label="Buscar"
            className={cn(topbarActionBtnClass, 'h-10 w-10')}
            onClick={() => setExpanded(true)}
          >
            <Search className="h-4 w-4" />
          </button>
        )}
      </div>
    </>
  )
}
