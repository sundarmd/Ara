// Chat message and SSE event types

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
    sources?: Source[];
    thoughts?: ThoughtEvent[];
    thinkingStartTime?: number;
}

export interface ThoughtEvent {
    type: 'thought';
    phase: 'analyzing' | 'searching' | 'extracting' | 'generating';
    content: string;
    elapsed_ms: number;
    details?: Array<Record<string, string | number | undefined>>;
}

export interface TokenEvent {
    type: 'token';
    content: string;
}

export interface CompleteEvent {
    type: 'complete';
    answer: string;
    sources: Source[];
    recommendations: Recommendation[];
}

export interface ErrorEvent {
    type: 'error';
    message: string;
    code?: string;
}

export interface Source {
    text: string;
    citation_id?: number;
    metadata: {
        bank?: string;
        page_start?: number;
        page_end?: number;
        doc_id?: string;
        report_date?: string;
        url?: string;
        title?: string;
    };
}

export interface Recommendation {
    id: string;
    bank: string;
    asset_class: string;
    sub_asset?: string;
    stance: string;
    horizon?: string;
    rationale: string;
}

export type SSEEvent = ThoughtEvent | TokenEvent | CompleteEvent | ErrorEvent;

export interface ChatRequest {
    messages: { role: string; content: string }[];
    bank?: string;
    asset_class?: string;
}
