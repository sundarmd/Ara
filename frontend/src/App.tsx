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
            <div className="flex flex-col h-[calc(100vh-5rem)]">
              {hasMessages ? (
                <>
                  {/* Messages area */}
                  <MessageList messages={messages} isLoading={isLoading} isThinking={isThinking} />

                  {/* Error display */}
                  {error && (
                    <div className="mx-4 mb-4 p-3 rounded-lg bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 text-sm">
                      {error}
                    </div>
                  )}

                  {/* Input at bottom */}
                  <div className="p-4 border-t border-[var(--color-border)]">
                    <div className="max-w-3xl mx-auto">
                      <ChatInput onSend={sendMessage} disabled={isLoading} />
                    </div>
                  </div>
                </>
              ) : (
                /* Empty state - centered */
                <div className="flex-1 flex flex-col items-center justify-center px-4">
                  <p className="text-[var(--color-text-muted)] max-w-md text-center mb-8">
                    Ask questions about cross-asset research reports, compare bank recommendations, or explore investment themes.
                  </p>

                  <div className="w-full max-w-2xl">
                    <ChatInput onSend={sendMessage} disabled={isLoading} />
                  </div>
                </div>
              )}
            </div>
          </Layout>
        </DropZone>
      </DocumentsProvider>
    </TooltipProvider>
  );
}

export default App;
