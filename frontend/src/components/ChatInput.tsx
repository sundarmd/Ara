import { useState, useRef, useEffect, KeyboardEvent, ChangeEvent } from 'react';
import { Send, Paperclip, Loader2 } from 'lucide-react';
import { useDocuments } from '../contexts/DocumentsContext';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { cn } from '@/lib/utils';

interface ChatInputProps {
    onSend: (message: string) => void;
    disabled?: boolean;
    placeholder?: string;
}

export function ChatInput({ onSend, disabled = false, placeholder = "Ask a question..." }: ChatInputProps) {
    const [input, setInput] = useState('');
    const { uploadFiles, uploads } = useDocuments();
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    const isUploading = Object.values(uploads).some(u => u.status === 'processing');

    // Auto-resize textarea
    useEffect(() => {
        const textarea = textareaRef.current;
        if (textarea) {
            textarea.style.height = 'auto'; // Reset to calculate correct scrollHeight
            const newHeight = Math.min(textarea.scrollHeight, 200);
            textarea.style.height = `${newHeight}px`;
        }
    }, [input]);

    const handleSend = () => {
        const trimmed = input.trim();
        if (trimmed && !disabled) {
            onSend(trimmed);
            setInput('');
            // Reset height manually ensures cleaner transition
            if (textareaRef.current) {
                textareaRef.current.style.height = 'auto';
            }
        }
    };

    const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file || !file.name.toLowerCase().endsWith('.pdf')) {
            e.target.value = '';
            return;
        }

        uploadFiles([file]);
        e.target.value = '';
    };

    return (
        <div className={cn(
            "flex items-center gap-2 bg-card/60 backdrop-blur-xl rounded-xl border border-black/20 dark:border-white/10 p-2 shadow-glass transition-all duration-200 hover:shadow-glow focus-within:shadow-glow focus-within:border-primary/50",
            disabled && "opacity-50 pointer-events-none"
        )}>
            {/* Attach button */}
            <input
                ref={fileInputRef}
                type="file"
                accept=".pdf"
                onChange={handleFileSelect}
                className="hidden"
            />

            <Button
                variant="ghost"
                size="icon"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isUploading}
                className="shrink-0 h-10 w-10 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50"
                title="Attach PDF"
            >
                {isUploading ? (
                    <Loader2 className="h-5 w-5 animate-spin" />
                ) : (
                    <Paperclip className="h-5 w-5" />
                )}
            </Button>

            {/* Text input */}
            <Textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={placeholder}
                disabled={disabled}
                rows={1}
                className="min-h-[40px] max-h-[200px] border-0 focus-visible:ring-0 focus-visible:ring-offset-0 px-2 py-[9px] resize-none bg-transparent shadow-none w-full text-base leading-relaxed placeholder:text-muted-foreground/70"
                style={{ height: '40px' }} // Initial height
            />

            {/* Send button */}
            <Button
                size="icon"
                onClick={handleSend}
                disabled={disabled || !input.trim()}
                className={cn(
                    "shrink-0 h-10 w-10 rounded-lg transition-all duration-200 shadow-sm",
                    !input.trim() ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-glow"
                )}
                aria-label="Send"
            >
                <Send className="h-5 w-5" />
            </Button>
        </div>
    );
}
