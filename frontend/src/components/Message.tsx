import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ChatMessage, ThoughtEvent, Source } from '../types/chat';
import { ThoughtsPanel } from './ThoughtsPanel';
import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, FileText, Globe, Calendar, ExternalLink } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card';
import { Separator } from '@/components/ui/separator';
import { Skeleton } from '@/components/ui/skeleton';
import { api } from '@/services/api';

interface MessageProps {
    message: ChatMessage;
    thoughts?: ThoughtEvent[];
    isStreaming?: boolean;
    thinkingStartTime?: number;
}

function parseCitationIds(rawIds: string) {
    return rawIds.replace(/\s/g, '').split(',').map(Number);
}

function hasEveryCitationId(rawIds: string, citationIds: Set<number>) {
    const ids = parseCitationIds(rawIds);
    return ids.length > 0 && ids.every(id => citationIds.has(id));
}

function DistinctSourceList({ sources }: { sources: Source[] }) {
    const distinctSources = useMemo(() => {
        const unique = new Map<string, Source>();
        sources.forEach(s => {
            const key = s.metadata?.url || s.text.substring(0, 50); // Fallback key
            if (!unique.has(key)) {
                unique.set(key, s);
            }
        });
        return Array.from(unique.values());
    }, [sources]);

    // Collapsible state
    const [isOpen, setIsOpen] = useState(false);

    if (distinctSources.length === 0) return null;

    return (
        <div className="mt-6 pt-4 border-t">
            <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsOpen(!isOpen)}
                className="w-full justify-between hover:bg-accent hover:text-accent-foreground px-2 -ml-2 h-8"
            >
                <span className="text-xs font-semibold">
                    Cited Sources ({distinctSources.length})
                </span>
                {isOpen ? (
                    <ChevronDown className="w-3 h-3 text-muted-foreground" />
                ) : (
                    <ChevronRight className="w-3 h-3 text-muted-foreground" />
                )}
            </Button>

            {isOpen && (
                <div className="grid gap-2 grid-cols-1 md:grid-cols-2 mt-2 animate-in slide-in-from-top-1 fade-in duration-200">
                    {distinctSources.map((source, idx) => (
                        <button
                            key={idx}
                            type="button"
                            disabled={!source.metadata?.url}
                            onClick={() => {
                                void api.openUrl(source.metadata?.url).catch(console.error);
                            }}
                            className={cn(
                                "flex items-start gap-3 p-3 rounded-lg border bg-card hover:bg-accent/50 transition-colors group text-left",
                                !source.metadata?.url && 'pointer-events-none'
                            )}
                        >
                            <div className="mt-0.5 flex-shrink-0">
                                <span className="inline-flex items-center justify-center w-5 h-5 text-[10px] font-bold text-primary-foreground bg-primary rounded-full shadow-sm group-hover:scale-110 transition-transform">
                                    {source.citation_id}
                                </span>
                            </div>
                            <div className="min-w-0 flex-1">
                                <div className="text-xs font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                                    {source.metadata?.title || source.metadata?.bank || "Unknown Source"}
                                </div>
                                <div className="text-[10px] text-muted-foreground mt-0.5 truncate">
                                    {source.metadata?.report_date && `${source.metadata.report_date} • `}
                                    {source.metadata?.page_start ? `Pg ${source.metadata.page_start}` : 'Web/Snippet'}
                                </div>
                            </div>
                        </button>
                    ))}
                </div>
            )}
        </div>
    );
}

function ContentWithCitations({ content, sources: _sources }: { content: string; sources?: Source[] }) {
    const preprocessedContent = useMemo(() => {
        const citationIds = new Set(
            (_sources ?? [])
                .map(source => source.citation_id)
                .filter((id): id is number => typeof id === 'number')
        );

        // Step 0: Strip formatting around citation patterns (LLM sometimes adds these)
        // Remove backticks: `[1]` or `[1](#citation-1)` → [1] or [1](#citation-1)
        let processed = content.replace(/`((?:\[[\d,\s]+\](?:\(#citation-[\d,]+\))?)+)`/g, '$1');
        // Remove bold: **[1]** → [1]
        processed = processed.replace(/\*\*(\[[\d,\s]+\])\*\*/g, '$1');
        // Clean stray asterisks before citations
        processed = processed.replace(/\*{1,2}(?=\[[\d,\s]+\])/g, '');
        // Clean stray asterisks after citations
        processed = processed.replace(/(\](?:\(#citation-[\d,]+\))?)\*{1,2}/g, '$1');

        // Step 1: Strip any existing citation markdown links (handles multi-ID like [1, 4])
        processed = processed.replace(/\[([\d,\s]+)\]\(#citation-[\d,]+\)/g, (_, ids) => `[${ids}]`);

        // Step 2: Transform plain [1] to anchor links for rendering
        processed = processed.replace(/\[([\d,\s]+)\]/g, (originalText, p1) => {
            if (!hasEveryCitationId(p1, citationIds)) {
                return originalText;
            }
            const idsStr = p1.replace(/\s/g, '');
            return `[${p1}](#citation-${idsStr})`;
        });

        return processed;
    }, [content, _sources]);

    return (
        <div className="prose prose-sm dark:prose-invert max-w-none leading-relaxed text-foreground">
            <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                    p: ({ node: _node, ...props }) => <p {...props} className="mb-4 last:mb-0" />,
                    table: ({ node: _node, ...props }) => (
                        <div className="overflow-x-auto my-4">
                            <table {...props} className="w-full border-collapse border border-border text-sm" />
                        </div>
                    ),
                    thead: ({ node: _node, ...props }) => (
                        <thead {...props} className="bg-muted/50" />
                    ),
                    th: ({ node: _node, ...props }) => (
                        <th {...props} className="border border-border px-3 py-2 text-left font-semibold text-foreground" />
                    ),
                    td: ({ node: _node, ...props }) => (
                        <td {...props} className="border border-border px-3 py-2 text-muted-foreground" />
                    ),
                    tr: ({ node: _node, ...props }) => (
                        <tr {...props} className="hover:bg-muted/30 transition-colors" />
                    ),
                    a: ({ node: _node, href, children, ...props }) => {
                        if (href?.startsWith('#citation-')) {
                            const ids = href.replace('#citation-', '').split(',').map(Number);

                            // Render distinct bubbles for each ID with HoverCard preview
                            return (
                                <span className="inline-flex items-center gap-0.5 align-super ml-0.5 translate-y-1">
                                    {ids.map((id) => {
                                        const source = _sources?.find(s => s.citation_id === id) ?? null;
                                        const isWeb = source?.metadata?.bank === 'Web';

                                        return (
                                            <HoverCard key={id} openDelay={200} closeDelay={100}>
                                                <HoverCardTrigger asChild>
                                                    <span
                                                        className="inline-flex items-center justify-center w-4 h-4 rounded-full text-[9px] font-bold bg-primary text-primary-foreground shadow-sm cursor-pointer hover:scale-110 transition-all select-none animate-in zoom-in-50 duration-200"
                                                        onClick={(e) => {
                                                            e.preventDefault();
                                                            e.stopPropagation();
                                                            if (source?.metadata?.url) {
                                                                void api.openUrl(source.metadata.url).catch(console.error);
                                                            }
                                                        }}
                                                    >
                                                        {id}
                                                    </span>
                                                </HoverCardTrigger>
                                                <HoverCardContent className="w-80" side="top" align="center">
                                                    {source ? (
                                                        <div className="space-y-2">
                                                            {/* Header */}
                                                            <div className="flex items-start gap-3">
                                                                <div className="p-2 rounded-md bg-muted flex-shrink-0">
                                                                    {isWeb ? <Globe className="h-4 w-4" /> : <FileText className="h-4 w-4" />}
                                                                </div>
                                                                <div className="flex-1 min-w-0">
                                                                    <p className="font-semibold text-sm truncate">
                                                                        {source.metadata?.bank || 'Source'}
                                                                    </p>
                                                                    <p className="text-xs text-muted-foreground truncate">
                                                                        {source.metadata?.title || 'Document'}
                                                                    </p>
                                                                </div>
                                                            </div>

                                                            <Separator />

                                                            {/* Metadata */}
                                                            <div className="flex items-center gap-4 text-xs text-muted-foreground">
                                                                {source.metadata?.report_date && (
                                                                    <span className="flex items-center gap-1">
                                                                        <Calendar className="h-3 w-3" />
                                                                        {source.metadata.report_date}
                                                                    </span>
                                                                )}
                                                                {source.metadata?.page_start && (
                                                                    <span>Page {source.metadata.page_start}</span>
                                                                )}
                                                            </div>

                                                            {/* Preview text */}
                                                            {source.text && (
                                                                <p className="text-xs text-muted-foreground line-clamp-2 italic">
                                                                    "{source.text.slice(0, 150)}..."
                                                                </p>
                                                            )}

                                                            {/* CTA */}
                                                            <div className="flex items-center justify-end pt-1">
                                                                <span className="text-xs text-primary flex items-center gap-1">
                                                                    Click to open <ExternalLink className="h-3 w-3" />
                                                                </span>
                                                            </div>
                                                        </div>
                                                    ) : (
                                                        <p className="text-sm text-muted-foreground">Source {id}</p>
                                                    )}
                                                </HoverCardContent>
                                            </HoverCard>
                                        );
                                    })}
                                </span>
                            );
                        }
                        return <a href={href} target="_blank" rel="noopener noreferrer" {...props} className="text-primary hover:underline font-medium">{children}</a>;
                    }
                }}
            >
                {preprocessedContent}
            </ReactMarkdown>
        </div>
    );
}

export function Message({ message, thoughts = [], isStreaming = false, thinkingStartTime }: MessageProps) {
    const isUser = message.role === 'user';
    // Consider thinking if streaming and content is empty or just whitespace
    const isThinking = isStreaming && (!message.content || message.content.trim().length === 0);

    if (isUser) {
        return (
            <div className="flex justify-end mb-6">
                <div className="max-w-[85%] animate-in slide-in-from-bottom-2 fade-in duration-300">
                    <div className="rounded-2xl px-5 py-3.5 bg-primary text-primary-foreground rounded-br-sm shadow-md">
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
                    </div>
                    <p className="text-[10px] mt-1.5 text-right text-muted-foreground mr-1 font-medium opactiy-70">
                        {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="w-full max-w-4xl animate-in fade-in slide-in-from-bottom-2 duration-300 mb-8">
            {thoughts.length > 0 && (
                <ThoughtsPanel
                    thoughts={thoughts}
                    isThinking={isThinking}
                    startTime={thinkingStartTime}
                />
            )}

            {message.content && message.content.trim().length > 0 ? (
                <Card className="rounded-xl border border-white/10 shadow-sm bg-card/40 backdrop-blur-md transition-all hover:bg-card/60">
                    <CardContent className="p-6">
                        <ContentWithCitations content={message.content} sources={message.sources} />

                        {message.sources && message.sources.length > 0 && (
                            <DistinctSourceList sources={message.sources} />
                        )}

                        <div className="flex items-center justify-end gap-2 mt-4 pt-2">
                            <Button variant="ghost" size="icon" className="h-6 w-6 rounded-full hover:bg-muted" title="Copy">
                                {/* Use a Copy icon here if desired, or keep generic logic */}
                                <span className="sr-only">Copy</span>
                            </Button>
                            <span className="text-[10px] text-muted-foreground font-medium">
                                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                            </span>
                        </div>
                    </CardContent>
                </Card>
            ) : isStreaming ? (
                <Card className="rounded-xl border border-white/10 shadow-sm bg-card/40 backdrop-blur-md">
                    <CardContent className="p-6">
                        <div className="space-y-3">
                            <div className="flex items-center gap-2">
                                <Skeleton className="h-4 w-4 rounded-full" />
                                <Skeleton className="h-4 w-24" />
                            </div>
                            <Skeleton className="h-4 w-full" />
                            <Skeleton className="h-4 w-3/4" />
                            <Skeleton className="h-4 w-5/6" />
                            <div className="flex items-center gap-2 pt-2">
                                <span className="text-sm font-medium animate-pulse text-muted-foreground">
                                    Generating response...
                                </span>
                                <div className="flex gap-1 ml-1">
                                    <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                    <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                    <span className="w-1.5 h-1.5 bg-muted-foreground/60 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                </div>
                            </div>
                        </div>
                    </CardContent>
                </Card>
            ) : null}
        </div>
    );
}
