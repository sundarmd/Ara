import { Toaster } from 'sonner';
import { DropZone } from './components/DropZone';
import { Layout } from './components/Layout';
import { ChatInput } from './components/ChatInput';
import { MessageList } from './components/MessageList';
import { useChat } from './hooks/useChat';
import { DocumentsProvider } from './contexts/DocumentsContext';
import { TooltipProvider } from './components/ui/tooltip';

function App() {
  const { messages, isLoading, isThinking, error, sendMessage } = useChat();
  const hasMessages = messages.length > 0;

  return (
    <TooltipProvider delayDuration={200}>
      <Toaster
        position="bottom-right"
        richColors
        closeButton
        toastOptions={{
          style: {
            background: 'var(--color-surface)',
            border: '1px solid var(--color-border)',
            color: 'var(--color-text)',
          },
        }}
      />
      <DocumentsProvider>
        <DropZone>
          <Layout>
            <div className="flex h-[calc(100dvh-3rem)] min-h-[560px] flex-col">
              {hasMessages ? (
                <>
                  <MessageList messages={messages} isLoading={isLoading} isThinking={isThinking} />

                  {error && (
                    <div className="mx-4 mb-4 rounded-[16px] border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
                      {error}
                    </div>
                  )}

                  <div className="border-t border-border/70 p-4">
                    <div className="mx-auto max-w-3xl">
                      <ChatInput onSend={sendMessage} disabled={isLoading} />
                    </div>
                  </div>
                </>
              ) : (
                <EmptyChatState onPrompt={sendMessage} isLoading={isLoading} />
              )}
            </div>
          </Layout>
        </DropZone>
      </DocumentsProvider>
    </TooltipProvider>
  );
}

function EmptyChatState({ onPrompt, isLoading }: { onPrompt: (message: string) => void; isLoading: boolean }) {
  return (
    <div className="flex min-w-0 flex-1 flex-col items-center justify-center px-2 py-10">
      <p className="mb-7 max-w-4xl text-center text-base leading-relaxed text-muted-foreground">
        Ask Ara to compare cross-asset research, evaluate portfolio views, and cite source pages.
      </p>

      <div className="w-full min-w-0 max-w-3xl">
        <ChatInput onSend={onPrompt} disabled={isLoading} placeholder="Ask about cross-asset research..." />
      </div>
    </div>
  );
}

export default App;
