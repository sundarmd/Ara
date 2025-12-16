import { API_BASE_URL } from '../config/constants';

class ApiService {
    private baseUrl: string;

    constructor() {
        this.baseUrl = API_BASE_URL;
    }

    private async request(endpoint: string, options: RequestInit = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        try {
            const response = await fetch(url, options);
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
     * Upload a research report PDF.
     */
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

    /**
     * Parse a ReadableStream from an SSE endpoint.
     * Yields parsed JSON events.
     */
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
                if (line.startsWith('data: ')) {
                    try {
                        const jsonStr = line.slice(6);
                        if (jsonStr === '[DONE]') continue; // Skip typical SSE terminator
                        const event = JSON.parse(jsonStr);
                        yield event as T;
                    } catch (e) {
                        console.warn('Failed to parse SSE event:', line);
                    }
                }
            }
        }
    }
}

export const api = new ApiService();
