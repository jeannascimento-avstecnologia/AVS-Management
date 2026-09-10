import * as React from 'react'
import { inputClass } from '@/lib/ui-classes'
import { cn } from '@/lib/cn'

const Textarea = React.forwardRef<HTMLTextAreaElement, React.ComponentProps<'textarea'>>(
  ({ className, ...props }, ref) => (
    <textarea
      className={cn(inputClass, 'h-auto min-h-[80px] py-2', className)}
      ref={ref}
      {...props}
    />
  ),
)
Textarea.displayName = 'Textarea'

export { Textarea }
