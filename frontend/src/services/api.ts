import { API_BASE_URL, API_KEY, API_KEY_HEADER_NAME } from '../config/constants';

class ApiService {
    private baseUrl: string;

    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    getAuthHeaders(headers: HeadersInit = {}) {
        const nextHeaders = new Headers(headers);
        if (API_KEY && !nextHeaders.has(API_KEY_HEADER_NAME)) {
            nextHeaders.set(API_KEY_HEADER_NAME, API_KEY);
        }
        return nextHeaders;
    }

    private async request(endpoint: string, options: RequestInit = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        try {
            const response = await fetch(url, {
                ...options,
                headers: this.getAuthHeaders(options.headers),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
            }
            return response;
        } catch (error) {
            console.error(`API Error (${endpoint}):`, error);
            throw error;
        }
    }

    /**
     * Upload a research report PDF (Streaming).
     * Returns the raw fetch response so the caller can handle the SSE stream.
     */
    async uploadReport(file: File, metadata: { bank: string; assetClass: string; reportDate: string }) {
        const formData = new FormData();
        formData.append('file', file);
        formData.append('bank', metadata.bank);
        formData.append('asset_class', metadata.assetClass);
        formData.append('report_date', metadata.reportDate);

        // Return raw response for SSE handling
        return this.request('/upload', {
            method: 'POST',
            body: formData,
        });
    }

    /**
     * Upload one or more PDFs and return the raw streaming response.
     */
    async uploadFiles(files: File[]) {
        const formData = new FormData();
        files.forEach(file => formData.append('files', file));

        return this.request('/upload', {
            method: 'POST',
            body: formData,
        });
    }

    /**
     * List all indexed documents.
     */
    async listDocuments() {
        const response = await this.request('/documents');
        return response.json();
    }

    /**
     * Delete a document and all associated data.
     */
    async deleteDocument(docId: string) {
        const response = await this.request(`/documents/${docId}`, {
            method: 'DELETE',
        });
        return response.json();
    }

    /**
     * Get the configured API URL (useful for EventSource which handles its own connection).
     */
    getStreamUrl(endpoint: string): string {
        return `${this.baseUrl}${endpoint}`;
    }

    async openUrl(url?: string | null) {
        if (!url) return;

        const resolvedUrl = this.resolveApiUrl(url);

        if (!API_KEY || !this.isApiUrl(resolvedUrl)) {
            window.open(resolvedUrl, '_blank', 'noopener,noreferrer');
            return;
        }

        const target = new URL(resolvedUrl, window.location.origin);
        const hash = target.hash;
        target.hash = '';

        const response = await fetch(target.toString(), {
            headers: this.getAuthHeaders(),
        });
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const blobUrl = URL.createObjectURL(await response.blob());
        window.open(`${blobUrl}${hash}`, '_blank', 'noopener,noreferrer');
        setTimeout(() => URL.revokeObjectURL(blobUrl), 60_000);
    }

    private resolveApiUrl(url: string) {
        let target: URL;
        let apiUrl: URL;
        try {
            target = new URL(url, window.location.origin);
            apiUrl = new URL(this.baseUrl, window.location.origin);
        } catch {
            return url;
        }

        if (
            this.isLocalHost(target.hostname) &&
            this.isLocalHost(apiUrl.hostname) &&
            /^\/documents\/[^/]+\/file$/.test(target.pathname)
        ) {
            target.protocol = apiUrl.protocol;
            target.host = apiUrl.host;
        }

        return target.toString();
    }

    private isLocalHost(hostname: string) {
        return hostname === 'localhost' || hostname === '127.0.0.1';
    }

    private isApiUrl(url: string) {
        try {
            const target = new URL(url, window.location.origin);
            const apiUrl = new URL(this.baseUrl, window.location.origin);
            return target.origin === apiUrl.origin;
        } catch {
            return false;
        }
    }

    /**
     * Parse a ReadableStream from an SSE endpoint.
     * Yields parsed JSON events.
     */
    private parseSSELine<T>(line: string): T | undefined {
        if (!line.startsWith('data: ')) return undefined;

        try {
            const jsonStr = line.slice(6);
            if (jsonStr === '[DONE]') return undefined;
            return JSON.parse(jsonStr) as T;
        } catch (e) {
            console.warn('Failed to parse SSE event:', line);
            return undefined;
        }
    }

    async *parseSSEStream<T>(reader: ReadableStreamDefaultReader<Uint8Array>): AsyncGenerator<T, void, unknown> {
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const event = this.parseSSELine<T>(line);
                if (event !== undefined) yield event;
            }
        }

        buffer += decoder.decode();
        if (buffer) {
            for (const line of buffer.split('\n')) {
                const event = this.parseSSELine<T>(line);
                if (event !== undefined) yield event;
            }
        }
    }
}

export const api = new ApiService();
