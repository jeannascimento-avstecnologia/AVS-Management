import * as React from 'react'
import { inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => (
    <input type={type} className={cn(inputClass, className)} ref={ref} {...props} />
  ),
)
Input.displayName = 'Input'

export { Input }
