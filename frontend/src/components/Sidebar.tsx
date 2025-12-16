import { useState, useEffect } from 'react';
import {
    Github,
    Sun,
    FileText,
    BookOpen,
    PanelLeft,
    ChevronDown,
    Trash2
} from 'lucide-react';
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
    const [isOpen, setIsOpen] = useState(true);
    const [isSourcesOpen, setIsSourcesOpen] = useState(true);
    const { isDark, toggle } = useDarkMode();
    const { documents, deleteDocument } = useDocuments();

    // Auto-expand sources when documents are added
    useEffect(() => {
        if (documents.length > 0) {
            setIsSourcesOpen(true);
        }
    }, [documents.length]);

    const toggleSidebar = () => setIsOpen(!isOpen);

    return (
        <TooltipProvider>
            <aside
                className={cn(
                    "flex flex-col border-r bg-card transition-all duration-300 ease-in-out h-screen sticky top-0 z-20",
                    isOpen ? 'w-[240px]' : 'w-[68px]'
                )}
            >
                {/* Header */}
                <div className={cn(
                    "flex items-center transition-all duration-300 backdrop-blur-md bg-card/80 z-30 sticky top-0",
                    isOpen ? "h-12 px-3 flex-row" : "h-auto py-4 flex-col justify-center gap-4"
                )}>
                    {isOpen ? (
                        <>
                            {/* Expanded: Logo Left, Toggle Right */}
                            <div className="flex-1 flex items-center gap-2 font-semibold text-primary whitespace-nowrap overflow-hidden animate-in fade-in duration-300 min-w-0">
                                <div className="dark:bg-white dark:rounded dark:p-0.5 flex items-center shrink-0">
                                    <img
                                        src="/allianz-logo.png"
                                        alt="Allianz Global Investors"
                                        className="h-6 w-auto"
                                    />
                                </div>
                            </div>

                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <Button
                                        variant="ghost"
                                        size="icon"
                                        onClick={toggleSidebar}
                                        className="text-muted-foreground hover:text-foreground h-8 w-8 shrink-0 ml-2"
                                    >
                                        <PanelLeft className="w-5 h-5" />
                                        <span className="sr-only">Close Sidebar</span>
                                    </Button>
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                    <p>Close Sidebar</p>
                                </TooltipContent>
                            </Tooltip>
                        </>
                    ) : (
                        /* Collapsed: Icon transforms to Toggle on Hover */
                        <Tooltip>
                            <TooltipTrigger asChild>
                                <Button
                                    variant="ghost"
                                    size="icon"
                                    onClick={toggleSidebar}
                                    className="h-9 w-9 shrink-0 group relative flex items-center justify-center"
                                >
                                    {/* Default: Allianz Icon */}
                                    <div
                                        className="absolute inset-0 flex items-center justify-center transition-opacity duration-200 group-hover:opacity-0"
                                    >
                                        <div className="w-8 h-8 flex items-center justify-center dark:bg-white dark:rounded-full dark:p-0.5">
                                            <img
                                                src="/allianz-icon.png"
                                                alt="AGI"
                                                className="w-8 h-8 object-contain"
                                            />
                                        </div>
                                    </div>

                                    {/* Hover: Toggle Icon */}
                                    <PanelLeft className="w-5 h-5 opacity-0 scale-90 transition-all duration-200 group-hover:opacity-100 group-hover:scale-100 text-muted-foreground group-hover:text-foreground" />
                                    <span className="sr-only">Open Sidebar</span>
                                </Button>
                            </TooltipTrigger>
                            <TooltipContent side="right">
                                <p>Open Sidebar</p>
                            </TooltipContent>
                        </Tooltip>
                    )}
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto py-1 px-2 space-y-0 scrollbar-hide">
                    {/* Dark Mode Button */}
                    <SidebarButton
                        icon={Sun}
                        label={isDark ? "Light Mode" : "Dark Mode"}
                        onClick={toggle}
                        isOpen={isOpen}
                    />

                    {/* GitHub Button */}
                    <SidebarButton
                        icon={Github}
                        label="GitHub Repo"
                        href="https://github.com/sundarmd/agi-technical-challenge"
                        target="_blank"
                        rel="noopener noreferrer"
                        isOpen={isOpen}
                    />

                    {/* Sources Section - Collapsible */}
                    <div>
                        {isOpen ? (
                            <Collapsible
                                open={isSourcesOpen}
                                onOpenChange={setIsSourcesOpen}
                                className="space-y-0"
                            >
                                <CollapsibleTrigger asChild>
                                    <Button
                                        variant="ghost"
                                        className="w-full justify-between h-8 px-2 hover:bg-muted/50 text-muted-foreground hover:text-foreground group"
                                    >
                                        <div className="flex items-center gap-3">
                                            <BookOpen className="w-4 h-4 shrink-0" />
                                            <span className="font-medium text-sm">Knowledge Base ({documents.length})</span>
                                        </div>
                                        <ChevronDown className={cn(
                                            "w-3 h-3 transition-transform duration-200",
                                            !isSourcesOpen && "-rotate-90"
                                        )} />
                                    </Button>
                                </CollapsibleTrigger>
                                <CollapsibleContent className="animate-slide-down">
                                    <div className="pb-1">
                                        {documents.length === 0 ? (
                                            <div className="px-2 py-1 text-xs text-muted-foreground italic pl-9">
                                                No files uploaded
                                            </div>
                                        ) : (
                                            documents.map((doc) => (
                                                <div
                                                    key={doc.doc_id}
                                                    className="group flex items-center gap-1 h-8 px-2 rounded-md hover:bg-muted/50 transition-colors"
                                                >
                                                    <a
                                                        href={api.getStreamUrl(`/files/${doc.doc_id}.pdf`)}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="flex-1 flex items-center gap-3 min-w-0 text-muted-foreground hover:text-foreground transition-colors"
                                                    >
                                                        <FileText className="w-3.5 h-3.5 shrink-0" />
                                                        <span className="truncate text-sm">{doc.filename}</span>
                                                    </a>
                                                    <button
                                                        onClick={(e) => {
                                                            e.stopPropagation();
                                                            if (confirm(`Delete "${doc.filename}"?\n\nThis will permanently remove the document and all associated data.`)) {
                                                                deleteDocument(doc.doc_id);
                                                            }
                                                        }}
                                                        className="opacity-0 group-hover:opacity-100 p-1 hover:bg-destructive/10 hover:text-destructive rounded transition-all shrink-0"
                                                        title="Delete document"
                                                    >
                                                        <Trash2 className="w-3.5 h-3.5" />
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
                                    <div className="flex justify-center py-2 text-muted-foreground hover:text-foreground cursor-default transition-colors">
                                        <BookOpen className="w-5 h-5" />
                                    </div>
                                </TooltipTrigger>
                                <TooltipContent side="right">
                                    <p>Knowledge Base ({documents.length})</p>
                                </TooltipContent>
                            </Tooltip>
                        )}
                    </div>
                </div>
            </aside>
        </TooltipProvider>
    );
}

interface SidebarButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    icon: React.ElementType;
    label: string;
    isOpen: boolean;
    href?: string;
    target?: string;
    rel?: string;
}

function SidebarButton({ icon: Icon, label, isOpen, href, className, ...props }: SidebarButtonProps) {
    const content = (
        <>
            <Icon className="w-4 h-4 shrink-0" />
            {isOpen && <span className="truncate text-sm">{label}</span>}
        </>
    );

    const buttonClass = cn(
        "w-full justify-start items-center gap-3 h-8 px-2 font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50",
        !isOpen && "justify-center px-0",
        className
    );

    if (href) {
        return (
            <Button variant="ghost" className={buttonClass} asChild>
                <a href={href} {...props as any}>
                    {content}
                </a>
            </Button>
        );
    }

    return (
        <Button variant="ghost" className={buttonClass} {...props}>
            {content}
        </Button>
    );
}
