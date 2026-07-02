import { useState, useEffect, useRef, useMemo } from 'react';
import { ChevronRight, ChevronDown, Brain } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { ThoughtEvent } from '../types/chat';
import { Skeleton } from '@/components/ui/skeleton';

interface SourceDetail {
    bank: string;
    pages: string;
    preview?: string;
}

interface ThoughtsPanelProps {
    thoughts: ThoughtEvent[];
    isThinking: boolean;
    startTime?: number;
}

export function ThoughtsPanel({ thoughts, isThinking, startTime }: ThoughtsPanelProps) {
    const [isExpanded, setIsExpanded] = useState(false);
    const [elapsedTime, setElapsedTime] = useState(0);
    const intervalRef = useRef<number | null>(null);

    // Extract sources from thoughts
    const sources: SourceDetail[] = useMemo(() => {
        return thoughts
            .filter(t => t.phase === 'searching' && t.details)
            .flatMap(t => t.details || [])
            .filter(d => d.bank && d.pages) as unknown as SourceDetail[];
    }, [thoughts]);

    // Live elapsed time counter
    useEffect(() => {
        if (isThinking && startTime) {
            const updateElapsed = () => {
                setElapsedTime(Date.now() - startTime);
            };
            updateElapsed();
            intervalRef.current = window.setInterval(updateElapsed, 100);

            return () => {
                if (intervalRef.current) {
                    clearInterval(intervalRef.current);
                }
            };
        } else if (!isThinking && startTime) {
            setElapsedTime(Date.now() - startTime);
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
            }
        }
    }, [isThinking, startTime]);

    // Auto-expand/collapse logic
    useEffect(() => {
        if (isThinking) {
            setIsExpanded(true);
        } else {
            // Auto-collapse when thinking is done and content starts
            setIsExpanded(false);
        }
        // User requesting "Turn-based" experience: keep thought panel open to see the process.
        // We do *not* auto-collapse when thinking finishes, letting user see the history.
        // Only collapse if user manually closes it.
    }, [isThinking]);

    if (thoughts.length === 0 && !isThinking) {
        return null;
    }

    const formatTime = (ms: number) => {
        return (ms / 1000).toFixed(1) + 's';
    };

    return (
        <div className="w-full mb-4">
            {/* Header */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="flex items-center gap-2 text-sm text-[var(--color-text-muted)] hover:text-[var(--color-text)] transition-colors"
                type="button"
            >
                {isExpanded ? (
                    <ChevronDown className="w-4 h-4" />
                ) : (
                    <ChevronRight className="w-4 h-4" />
                )}

                <Brain className={`w-4 h-4 ${isThinking ? 'animate-pulse text-primary' : ''}`} />

                <span>
                    {isThinking ? (
                        <>Thinking... ({formatTime(elapsedTime)})</>
                    ) : (
                        <>Thought for {formatTime(elapsedTime)}</>
                    )}
                </span>

                {sources.length > 0 && (
                    <span className="text-xs bg-[var(--color-bg)] px-2 py-0.5 rounded">
                        {sources.length} sources
                    </span>
                )}
            </button>

            {/* Expanded content */}
            {isExpanded && (
                <div className="w-full mt-3 space-y-2 p-6 rounded-lg bg-muted/30 border border-border/30 animate-in fade-in slide-in-from-top-2 duration-200">
                    {/* Thought steps - compact list */}
                    <div className="w-full space-y-1.5 prose prose-sm dark:prose-invert max-w-none">
                        {thoughts.length === 0 && isThinking ? (
                            // Skeleton loading while waiting for first thought
                            <div className="space-y-2">
                                <Skeleton className="h-3 w-full" />
                                <Skeleton className="h-3 w-4/5" />
                            </div>
                        ) : (
                            thoughts.map((thought, index) => (
                                <div
                                    key={index}
                                    className={`text-[var(--color-text-muted)] leading-relaxed ${isThinking && index === thoughts.length - 1 ? 'animate-pulse' : ''
                                        }`}
                                >
                                    <ReactMarkdown
                                        components={{
                                            p: ({ node, ...props }) => <span {...props} />,
                                            strong: ({ node, ...props }) => <span {...props} className="font-semibold text-[var(--color-text)]" />
                                        }}
                                    >
                                        {thought.content}
                                    </ReactMarkdown>
                                </div>
                            ))
                        )}
                    </div>

                    {/* Source cards - compact horizontal scroll */}
                    {sources.length > 0 && (
                        <div className="flex gap-1.5 overflow-x-auto pb-1 mt-2">
                            {sources.map((source, index) => (
                                <div
                                    key={index}
                                    className="flex-shrink-0 flex items-center gap-1.5 px-2 py-1 rounded bg-card/50 border border-border/50 text-[10px]"
                                >
                                    <span className="font-medium text-[var(--color-text)]">{source.bank}</span>
                                    <span className="text-[var(--color-text-muted)]">{source.pages}</span>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
