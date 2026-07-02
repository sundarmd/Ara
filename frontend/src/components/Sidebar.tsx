import { useState, useEffect } from 'react';
import type { ComponentType } from 'react';
import type { IconProps } from '@phosphor-icons/react';
import {
    Books,
    CaretDown,
    FilePdf,
    GithubLogo,
    Moon,
    SidebarSimple,
    Sparkle,
    Sun,
    Trash,
} from '@phosphor-icons/react';
import { useDarkMode } from '../hooks/useDarkMode';
import { api } from '../services/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useDocuments } from '../contexts/DocumentsContext';
import {
    Tooltip,
    TooltipContent,
    TooltipProvider,
    TooltipTrigger,
} from "@/components/ui/tooltip"
import {
    Collapsible,
    CollapsibleContent,
    CollapsibleTrigger,
} from "@/components/ui/collapsible"

export function Sidebar() {
    const [isOpen, setIsOpen] = useState(() => {
        if (typeof window === 'undefined') {
            return true;
        }

        return window.matchMedia('(min-width: 768px)').matches;
    });
    const [isSourcesOpen, setIsSourcesOpen] = useState(true);
    const { isDark, toggle } = useDarkMode();
    const { documents, deleteDocument } = useDocuments();

    // Auto-expand sources when documents are added
    useEffect(() => {
        if (documents.length > 0) {
            setIsSourcesOpen(true);
        }
    }, [documents.length]);

    useEffect(() => {
        const query = window.matchMedia('(max-width: 767px)');
        const collapseOnMobile = () => {
            if (query.matches) {
                setIsOpen(false);
            }
        };

        collapseOnMobile();
        query.addEventListener('change', collapseOnMobile);

        return () => {
            query.removeEventListener('change', collapseOnMobile);
        };
    }, []);

    const toggleSidebar = () => setIsOpen(!isOpen);

    return (
        <TooltipProvider>
            <aside
                className={cn(
                    "sticky top-0 flex h-[100dvh] min-h-[100dvh] shrink-0 flex-col overflow-hidden border-r border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar))] text-[hsl(var(--sidebar-foreground))] shadow-[inset_-1px_0_0_hsl(var(--sidebar-edge))] transition-[width] duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
                    isOpen ? 'w-[272px]' : 'w-[76px]'
                )}
            >
                <div className={cn(
                    "relative border-b border-[hsl(var(--sidebar-border))] p-3",
                    isOpen ? "h-[76px]" : "h-[82px]"
                )}>
                    {isOpen ? (
                        <div className="flex h-full items-center gap-3">
                            <div className="flex min-w-0 flex-1 items-center gap-3 rounded-[18px] border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-panel))] px-3 py-2 shadow-[inset_0_1px_0_hsl(var(--sidebar-highlight))]">
                                <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-[14px] border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-logo-bg))] shadow-[0_12px_28px_-20px_hsl(var(--primary)/0.75)]">
                                    <img src="/ara-generated-mark.png" alt="Ara" className="h-8 w-8 object-contain" />
                                    <span className="pointer-events-none absolute inset-x-1 top-0 h-px bg-[hsl(var(--sidebar-highlight))]" />
                                </div>
                                <div className="min-w-0">
                                    <div className="flex items-baseline gap-2">
                                        <span className="truncate text-[18px] font-semibold leading-none tracking-tight">Ara</span>
                                    </div>
                                    <p className="mt-1 truncate text-[11px] font-medium uppercase tracking-[0.16em] text-[hsl(var(--sidebar-muted))]">
                                        Research OS
                                    </p>
                                </div>
                            </div>

                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={toggleSidebar}
                                        className="h-10 w-10 shrink-0 rounded-[14px] text-[hsl(var(--sidebar-muted))] transition-all duration-200 hover:bg-[hsl(var(--sidebar-panel))] hover:text-[hsl(var(--sidebar-foreground))] active:scale-[0.96]"
                                    >
                                        <SidebarSimple size={20} weight="duotone" />
                                        <span className="sr-only">Close Sidebar</span>
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                    <p>Close Sidebar</p>
                                </TooltipContent>
                            </Tooltip>
                        </div>
                    ) : (
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={toggleSidebar}
                                    className="group relative mx-auto flex h-12 w-12 shrink-0 items-center justify-center rounded-[18px] border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-panel))] shadow-[inset_0_1px_0_hsl(var(--sidebar-highlight))] transition-all duration-200 hover:-translate-y-0.5 hover:text-[hsl(var(--sidebar-foreground))] active:scale-[0.96]"
                                >
                                    <div
                                        className="absolute inset-0 flex items-center justify-center transition-all duration-200 group-hover:opacity-0 group-hover:scale-90"
                                    >
                                        <div className="relative flex h-10 w-10 items-center justify-center overflow-hidden rounded-[14px] border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-logo-bg))] shadow-[0_12px_28px_-20px_hsl(var(--primary)/0.75)]">
                                            <img src="/ara-generated-mark.png" alt="Ara" className="h-8 w-8 object-contain" />
                                            <span className="pointer-events-none absolute inset-x-1 top-0 h-px bg-[hsl(var(--sidebar-highlight))]" />
                                        </div>
                                    </div>

                                    <SidebarSimple size={20} weight="duotone" className="scale-90 opacity-0 transition-all duration-200 group-hover:scale-100 group-hover:opacity-100" />
                                    <span className="sr-only">Open Sidebar</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="right">
                                <p>Open Sidebar</p>
                            </TooltipContent>
                        </Tooltip>
                    )}
                </div>

                <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-hide">
                    <div className={cn("space-y-1.5", !isOpen && "flex flex-col items-center")}>
                        <SidebarButton
                            icon={isDark ? Sun : Moon}
                            label={isDark ? "Light Mode" : "Dark Mode"}
                            onClick={toggle}
                            isOpen={isOpen}
                        />

                        <SidebarButton
                            icon={GithubLogo}
                            label="GitHub Repo"
                            href="https://github.com/sundarmd/Ara"
                            target="_blank"
                            rel="noopener noreferrer"
                            isOpen={isOpen}
                        />

                        <div>
                            {isOpen ? (
                                <Collapsible
                                    open={isSourcesOpen}
                                    onOpenChange={setIsSourcesOpen}
                                    className="pt-2"
                                >
                                    <CollapsibleTrigger asChild>
                                        <Button
                                            variant="ghost"
                                            className="group h-11 w-full justify-between rounded-[15px] px-3 text-[hsl(var(--sidebar-muted))] transition-all duration-200 hover:bg-[hsl(var(--sidebar-panel))] hover:text-[hsl(var(--sidebar-foreground))] active:scale-[0.99]"
                                        >
                                            <div className="flex min-w-0 items-center gap-3">
                                                <Books size={19} weight="duotone" className="shrink-0" />
                                                <span className="truncate text-sm font-medium">Knowledge Base</span>
                                            </div>
                                            <div className="flex items-center gap-2">
                                                <span className="rounded-full border border-[hsl(var(--sidebar-border))] px-2 py-0.5 text-[11px] font-semibold text-[hsl(var(--sidebar-muted))]">
                                                    {documents.length}
                                                </span>
                                                <CaretDown
                                                    size={14}
                                                    weight="bold"
                                                    className={cn(
                                                        "transition-transform duration-200",
                                                        !isSourcesOpen && "-rotate-90"
                                                    )}
                                                />
                                            </div>
                                        </Button>
                                    </CollapsibleTrigger>
                                    <CollapsibleContent>
                                        <div className="mt-2 space-y-1 border-l border-[hsl(var(--sidebar-border))] pl-3">
                                            {documents.length === 0 ? (
                                                <div className="rounded-[14px] border border-dashed border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-panel))] px-3 py-3">
                                                    <div className="flex items-start gap-2 text-[hsl(var(--sidebar-muted))]">
                                                        <Sparkle size={16} weight="duotone" className="mt-0.5 shrink-0 text-primary" />
                                                        <div>
                                                            <p className="text-xs font-medium text-[hsl(var(--sidebar-foreground))]">No files uploaded</p>
                                                            <p className="mt-1 text-[11px] leading-4">Drop research PDFs anywhere in the app.</p>
                                                        </div>
                                                    </div>
                                                </div>
                                            ) : (
                                                documents.map((doc) => (
                                                    <div
                                                        key={doc.doc_id}
                                                        className="group flex min-h-10 items-center gap-1 rounded-[14px] px-2 transition-colors hover:bg-[hsl(var(--sidebar-panel))]"
                                                    >
                                                        <a
                                                            href={api.getStreamUrl(`/files/${doc.doc_id}.pdf`)}
                                                            target="_blank"
                                                            rel="noopener noreferrer"
                                                            className="flex min-w-0 flex-1 items-center gap-2 text-[hsl(var(--sidebar-muted))] transition-colors hover:text-[hsl(var(--sidebar-foreground))]"
                                                        >
                                                            <FilePdf size={16} weight="duotone" className="shrink-0" />
                                                            <span className="truncate text-sm font-medium">{doc.filename}</span>
                                                        </a>
                                                        <button
                                                            onClick={(e) => {
                                                                e.stopPropagation();
                                                                if (confirm(`Delete "${doc.filename}"?\n\nThis will permanently remove the document and all associated data.`)) {
                                                                    deleteDocument(doc.doc_id);
                                                                }
                                                            }}
                                                            className="shrink-0 rounded-lg p-1 text-[hsl(var(--sidebar-muted))] opacity-0 transition-all hover:bg-destructive/10 hover:text-destructive group-hover:opacity-100 active:scale-[0.94]"
                                                            title="Delete document"
                                                        >
                                                            <Trash size={15} weight="duotone" />
                                                        </button>
                                                    </div>
                                                ))
                                            )}
                                        </div>
                                    </CollapsibleContent>
                                </Collapsible>
                            ) : (
                                <Tooltip>
                                    <TooltipTrigger asChild>
                                        <div className="flex h-11 w-11 cursor-default items-center justify-center rounded-[15px] text-[hsl(var(--sidebar-muted))] transition-colors hover:bg-[hsl(var(--sidebar-panel))] hover:text-[hsl(var(--sidebar-foreground))]">
                                            <Books size={21} weight="duotone" />
                                        </div>
                                    </TooltipTrigger>
                                    <TooltipContent side="right">
                                        <p>Knowledge Base ({documents.length})</p>
                                    </TooltipContent>
                                </Tooltip>
                            )}
                        </div>
                    </div>
                </nav>

                <div className={cn("border-t border-[hsl(var(--sidebar-border))] p-3", !isOpen && "flex justify-center")}>
                    <div className="flex h-9 w-9 items-center justify-center rounded-full border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-panel))] text-sm font-semibold text-[hsl(var(--sidebar-foreground))] shadow-[inset_0_1px_0_hsl(var(--sidebar-highlight))]">
                        S
                    </div>
                </div>
            </aside>
        </TooltipProvider>
    );
}

type SidebarIcon = ComponentType<IconProps>;

interface SidebarButtonProps {
    icon: SidebarIcon;
    label: string;
    isOpen: boolean;
    href?: string;
    target?: string;
    rel?: string;
    className?: string;
    onClick?: () => void;
    disabled?: boolean;
}

function SidebarButton({ icon: Icon, label, isOpen, href, target, rel, className, onClick, disabled }: SidebarButtonProps) {
    const content = (
        <>
            <Icon size={19} weight="duotone" className="shrink-0" />
            {isOpen && <span className="truncate text-sm font-medium">{label}</span>}
        </>
    );

    const buttonClass = cn(
        "h-11 w-full justify-start gap-3 rounded-[15px] px-3 text-[hsl(var(--sidebar-muted))] transition-all duration-200 hover:bg-[hsl(var(--sidebar-panel))] hover:text-[hsl(var(--sidebar-foreground))] active:scale-[0.98]",
        !isOpen && "h-11 w-11 justify-center px-0",
        className
    );

    if (href) {
        return (
            <Button variant="ghost" className={buttonClass} asChild>
                <a href={href} target={target} rel={rel}>
                    {content}
                </a>
            </Button>
        );
    }

    return (
        <Button variant="ghost" className={buttonClass} onClick={onClick} disabled={disabled}>
            {content}
        </Button>
    );
}
