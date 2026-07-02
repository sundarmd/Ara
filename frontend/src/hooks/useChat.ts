import { useState, useCallback, useRef, useEffect } from 'react';
import { ChatMessage, SSEEvent, ThoughtEvent } from '../types/chat';
import { api } from '../services/api';

interface UseChatReturn {
    messages: ChatMessage[];
    currentThoughts: ThoughtEvent[];
    isLoading: boolean;
    isThinking: boolean;
    thinkingStartTime: number | null;
    error: string | null;
    sendMessage: (content: string) => Promise<void>;
    clearMessages: () => void;
}

export function useChat(): UseChatReturn {
    const [messages, setMessages] = useState<ChatMessage[]>([]);

    // Derived state for current activity
    const [isLoading, setIsLoading] = useState(false);
    const [isThinking, setIsThinking] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const currentMessageId = useRef<string | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);

    // We strictly track the accumulated thoughts for the *active* generating message separately to ensure smooth updates,
    // then merge them into the message object.
    const [currentThoughts, setCurrentThoughts] = useState<ThoughtEvent[]>([]);
    const [thinkingStartTime, setThinkingStartTime] = useState<number | null>(null);

    useEffect(() => {
        return () => {
            abortControllerRef.current?.abort();
            abortControllerRef.current = null;
            currentMessageId.current = null;
        };
    }, []);

    const sendMessage = useCallback(async (content: string) => {
        abortControllerRef.current?.abort();

        // Add user message
        const userMessage: ChatMessage = {
            id: `user-${Date.now()}`,
            role: 'user',
            content,
            timestamp: new Date(),
        };

        const startTime = Date.now();

        // 1. Optimistically add user message
        setMessages((prev) => [...prev, userMessage]);

        // Reset temporary states
        setCurrentThoughts([]);
        setIsLoading(true);
        setIsThinking(true);
        setThinkingStartTime(startTime);
        setError(null);

        // 2. Create placeholder for assistant message
        const assistantId = `assistant-${Date.now()}`;
        currentMessageId.current = assistantId;
        const abortController = new AbortController();
        abortControllerRef.current = abortController;

        const placeholderMessage: ChatMessage = {
            id: assistantId,
            role: 'assistant',
            content: '',
            timestamp: new Date(),
            thoughts: [],
            thinkingStartTime: startTime,
        };

        setMessages((prev) => [...prev, placeholderMessage]);

        // Build request history (exclude the empty placeholder)
        const requestMessages = [...messages, userMessage].map(m => ({
            role: m.role,
            content: m.content,
        }));

        try {
            const url = api.getStreamUrl('/chat/stream');
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                signal: abortController.signal,
                body: JSON.stringify({ messages: requestMessages }),
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const reader = response.body?.getReader();
            if (!reader) throw new Error('No response body');

            const accumulatedThoughts: ThoughtEvent[] = [];
            let assistantContent = '';

            for await (const event of api.parseSSEStream<SSEEvent>(reader)) {
                switch (event.type) {
                    case 'thought':
                        accumulatedThoughts.push(event);
                        setCurrentThoughts([...accumulatedThoughts]);

                        // Update message with new thoughts immediately
                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === assistantId
                                    ? { ...m, thoughts: [...accumulatedThoughts] }
                                    : m
                            )
                        );
                        break;

                    case 'token':
                        if (assistantContent === '') {
                            setIsThinking(false);
                        }
                        assistantContent += event.content;

                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === assistantId
                                    ? { ...m, content: assistantContent }
                                    : m
                            )
                        );
                        break;

                    case 'complete':
                        setIsThinking(false);
                        assistantContent = event.answer;

                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === assistantId
                                    ? {
                                        ...m,
                                        content: assistantContent,
                                        sources: event.sources,
                                        thoughts: [...accumulatedThoughts] // Ensure final thoughts are synced
                                    }
                                    : m
                            )
                        );
                        break;

                    case 'error':
                        setError(event.message);
                        setIsThinking(false);
                        setMessages((prev) =>
                            prev.map((m) =>
                                m.id === assistantId
                                    ? {
                                        ...m,
                                        content: event.message,
                                        thoughts: [...accumulatedThoughts],
                                    }
                                    : m
                            )
                        );
                        return;
                }
            }

        } catch (err) {
            if (!abortController.signal.aborted && currentMessageId.current === assistantId) {
                setError(err instanceof Error ? err.message : 'Failed to send message');
                // Remove placeholder on error
                setMessages((prev) => prev.filter((m) => m.id !== assistantId));
            }
        } finally {
            if (currentMessageId.current === assistantId) {
                setIsLoading(false);
                setIsThinking(false);
                currentMessageId.current = null;
                if (abortControllerRef.current === abortController) {
                    abortControllerRef.current = null;
                }
            }
        }
    }, [messages]);

    const clearMessages = useCallback(() => {
        abortControllerRef.current?.abort();
        abortControllerRef.current = null;
        currentMessageId.current = null;
        setMessages([]);
        setCurrentThoughts([]);
        setError(null);
        setThinkingStartTime(null);
        setIsLoading(false);
        setIsThinking(false);
    }, []);

    return {
        messages,
        currentThoughts, // Still exposed for components that want to show "live" thoughts separately
        isLoading,
        isThinking,
        thinkingStartTime,
        error,
        sendMessage,
        clearMessages,
    };
}
