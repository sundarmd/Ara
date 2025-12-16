import { useEffect, useRef } from 'react';
import { ChatMessage } from '../types/chat';
import { Message } from './Message';

interface MessageListProps {
    messages: ChatMessage[];
    isLoading?: boolean;
    isThinking?: boolean;
}

export function MessageList({ messages, isLoading = false }: MessageListProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom on new messages
    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, isLoading]);

    if (messages.length === 0 && !isLoading) {
        return (
            <div className="flex-1 flex items-center justify-center text-center p-8">
                <div>
                    <p className="text-heading text-lg font-medium mb-2">
                        Start a conversation
                    </p>
                    <p className="text-[var(--color-text-muted)] text-sm">
                        Ask questions about cross-asset research reports, compare bank recommendations, or explore investment themes.
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.map((message, index) => {
                const isLastAssistant = message.role === 'assistant' && index === messages.length - 1;
                return (
                    <Message
                        key={message.id}
                        message={message}
                        thoughts={message.thoughts}
                        isStreaming={isLastAssistant && isLoading}
                        thinkingStartTime={message.thinkingStartTime}
                    />
                );
            })}

            <div ref={bottomRef} />
        </div>
    );
}
