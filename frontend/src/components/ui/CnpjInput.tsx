import * as React from 'react'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/cn'
import { digitsOnly, formatQueryInput, maskCnpjInput } from '@/lib/format'

type BaseProps = Omit<React.ComponentProps<typeof Input>, 'onChange' | 'value'>

type CnpjInputProps = BaseProps & {
  value: string
  onValueChange: (value: string) => void
  mode?: 'cnpj' | 'query'
}

export const CnpjInput = React.forwardRef<HTMLInputElement, CnpjInputProps>(
  ({ value, onValueChange, mode = 'cnpj', className, onPaste, ...props }, ref) => {
    const format = mode === 'query' ? formatQueryInput : maskCnpjInput

    function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
      onValueChange(format(e.target.value))
    }

    function handlePaste(e: React.ClipboardEvent<HTMLInputElement>) {
      onPaste?.(e)
      if (e.defaultPrevented) return
      e.preventDefault()
      const text = e.clipboardData.getData('text')
      onValueChange(format(text))
    }

    return (
      <Input
        ref={ref}
        value={value}
        onChange={handleChange}
        onPaste={handlePaste}
        inputMode={mode === 'cnpj' ? 'numeric' : 'text'}
        maxLength={mode === 'cnpj' ? 18 : undefined}
        className={cn('font-mono', className)}
        {...props}
      />
    )
  },
)
CnpjInput.displayName = 'CnpjInput'

export { digitsOnly }
