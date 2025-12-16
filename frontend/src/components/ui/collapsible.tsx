import * as React from "react"
import { cn } from "@/lib/utils"

const CollapsibleContext = React.createContext<{
    open: boolean
    onOpenChange: (open: boolean) => void
} | undefined>(undefined)

const Collapsible = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement> & {
        open?: boolean
        onOpenChange?: (open: boolean) => void
        defaultOpen?: boolean
    }
>(({ className, open: controlledOpen, onOpenChange, defaultOpen = false, children, ...props }, ref) => {
    const [uncontrolledOpen, setUncontrolledOpen] = React.useState(defaultOpen)
    const isControlled = controlledOpen !== undefined
    const open = isControlled ? controlledOpen : uncontrolledOpen

    const handleOpenChange = (newOpen: boolean) => {
        if (!isControlled) {
            setUncontrolledOpen(newOpen)
        }
        onOpenChange?.(newOpen)
    }

    return (
        <CollapsibleContext.Provider value={{ open: open!, onOpenChange: handleOpenChange }}>
            <div ref={ref} className={cn(className)} {...props}>
                {children}
            </div>
        </CollapsibleContext.Provider>
    )
})
Collapsible.displayName = "Collapsible"

const CollapsibleTrigger = React.forwardRef<
    HTMLButtonElement,
    React.ButtonHTMLAttributes<HTMLButtonElement> & { asChild?: boolean }
>(({ className, children, onClick, asChild, ...props }, ref) => {
    const context = React.useContext(CollapsibleContext)

    const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
        context?.onOpenChange(!context.open)
        onClick?.(e)
    }

    if (asChild && React.isValidElement(children)) {
        return React.cloneElement(children as React.ReactElement<any>, {
            ref,
            onClick: handleClick,
            ...props,
        })
    }

    return (
        <button
            ref={ref}
            className={cn(className)}
            onClick={handleClick}
            {...props}
        >
            {children}
        </button>
    )
})
CollapsibleTrigger.displayName = "CollapsibleTrigger"

const CollapsibleContent = React.forwardRef<
    HTMLDivElement,
    React.HTMLAttributes<HTMLDivElement>
>(({ className, children, ...props }, ref) => {
    const context = React.useContext(CollapsibleContext)

    if (!context?.open) return null

    return (
        <div
            ref={ref}
            className={cn("overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down", className)}
            {...props}
        >
            {children}
        </div>
    )
})
CollapsibleContent.displayName = "CollapsibleContent"

export { Collapsible, CollapsibleTrigger, CollapsibleContent }
