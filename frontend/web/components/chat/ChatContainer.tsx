'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Menu, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui';
import { useAuthStore } from '@/store';
import { useUIStore } from '@/store/ui-store';
import { api } from '@/lib/api';
import type { Message, SourceDocument, FeedbackType, Conversation, ModelInfo } from '@/types';

import { ChatSidebar } from './ChatSidebar';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import { WelcomeScreen } from './WelcomeScreen';
import { ModelSelector } from './ModelSelector';
import { SourcesPanel } from './SourcesPanel';
import { DocumentViewerModal } from '@/components/documents/DocumentViewerModal';

interface ChatContainerProps {
  initialConversationId?: string;
}

export function ChatContainer({ initialConversationId }: ChatContainerProps) {
  const { user } = useAuthStore();
  const isSourcesPanelOpen = useUIStore((s) => s.isSourcesPanelOpen);

  const [selectedConversationId, setSelectedConversationId] = useState<string | undefined>(initialConversationId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [selectedModelId, setSelectedModelId] = useState('default');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const skipLoadRef = useRef(false);

  useEffect(() => {
    api.ai.getModels().then(setModels).catch(() => {});
    const saved = typeof window !== 'undefined' ? localStorage.getItem('selected-model-id') : null;
    if (saved) setSelectedModelId(saved);
    const historySaved = typeof window !== 'undefined' ? localStorage.getItem('chat-history-collapsed') : null;
    if (historySaved === 'true') setHistoryCollapsed(true);
  }, []);

  // Auto-collapse history panel on narrow viewports
  useEffect(() => {
    const handleResize = () => {
      if (typeof window === 'undefined') return;
      const isNarrow = window.innerWidth < 1280;
      const isTiny = window.innerWidth < 768;
      if (isTiny) {
        setHistoryCollapsed(true);
        setIsSidebarOpen(false);
      } else if (isNarrow) {
        setHistoryCollapsed(true);
      }
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  const toggleHistoryCollapse = () => {
    setHistoryCollapsed((prev) => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        localStorage.setItem('chat-history-collapsed', String(next));
      }
      return next;
    });
  };

  const handleModelChange = (id: string) => {
    setSelectedModelId(id);
    if (typeof window !== 'undefined') {
      localStorage.setItem('selected-model-id', id);
    }
  };

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  const loadConversation = async (conversationId: string) => {
    try {
      const convMessages = await api.ai.getMessages(conversationId);
      setMessages(convMessages);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setError('Không thể tải tin nhắn');
    }
  };

  useEffect(() => {
    if (selectedConversationId) {
      if (skipLoadRef.current) {
        skipLoadRef.current = false;
        return;
      }
      loadConversation(selectedConversationId);
    } else {
      setMessages([]);
    }
  }, [selectedConversationId]);

  const handleNewChat = () => {
    setSelectedConversationId(undefined);
    setMessages([]);
    setInput('');
    setError(null);
    setIsSidebarOpen(false);
  };

  const handleSelectConversation = (id: string) => {
    setSelectedConversationId(id);
    setIsSidebarOpen(false);
  };

  const handleSuggestionClick = (text: string) => {
    setInput(text);
  };

  const handleSubmit = async (text: string) => {
    if (!text.trim() || isLoading) return;

    const userMessage: Message = {
      id: `temp-${Date.now()}`,
      conversationId: selectedConversationId || '',
      role: 'USER',
      content: text.trim(),
      hasSources: false,
      createdAt: new Date().toISOString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setError(null);

    abortControllerRef.current = new AbortController();

    try {
      const stream = api.ai.askStream({
        question: text.trim(),
        conversationId: selectedConversationId,
        modelId: selectedModelId,
      }, abortControllerRef.current.signal);
      const reader = stream.getReader();

      let fullContent = '';
      let conversationId: string | null = null;
      let sources: SourceDocument[] = [];
      let assistantMessageId = `temp-assistant-${Date.now()}`;
      let modelUsed = selectedModelId === 'default'
        ? (models.find(m => m.isDefault)?.id || 'default')
        : selectedModelId;

      const assistantMsg: Message = {
        id: assistantMessageId,
        conversationId: selectedConversationId || '',
        role: 'ASSISTANT',
        content: '',
        sources: [],
        hasSources: false,
        isStreaming: true,
        streamingCompleted: false,
        modelRequested: selectedModelId,
        modelUsed,
        createdAt: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        switch (value.type) {
          case 'conversationId':
            conversationId = value.conversationId;
            if (!selectedConversationId) {
              skipLoadRef.current = true;
              setSelectedConversationId(value.conversationId);
            }
            break;
          case 'sources':
            sources = value.sources;
            break;
          case 'modelUsed':
            modelUsed = value.modelUsed;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, modelUsed }
                  : m
              )
            );
            break;
          case 'content':
            fullContent += value.content;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: fullContent, sources: sources.length > 0 ? sources : m.sources, modelUsed }
                  : m
              )
            );
            break;
          case 'done':
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: fullContent, sources, isStreaming: false, streamingCompleted: true, modelUsed }
                  : m
              )
            );
            break;
          case 'error':
            setError(value.error);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantMessageId
                  ? { ...m, content: 'Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.', isStreaming: false, streamingCompleted: true }
                  : m
              )
            );
            break;
        }
      }
    } catch (err) {
      console.error('Chat error:', err);
      setError(err instanceof Error ? err.message : 'Đã xảy ra lỗi');
      setMessages((prev) => [
        ...prev,
        {
          id: `error-${Date.now()}`,
          conversationId: selectedConversationId || '',
          role: 'ASSISTANT',
          content: 'Xin lỗi, đã xảy ra lỗi. Vui lòng thử lại.',
          hasSources: false,
          createdAt: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleCopy = async (content: string) => {
    await navigator.clipboard.writeText(content);
  };

  const handleFeedback = async (messageId: string, type: FeedbackType) => {
    try {
      const convId = selectedConversationId || messages.find(m => m.id === messageId)?.conversationId;
      if (convId) {
        await api.feedback.submit(convId, messageId, type);
      }
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  const handleMarkUnanswered = async (messageId: string) => {
    if (!selectedConversationId) return;
    try {
      await api.ai.markAsUnanswered(selectedConversationId, messageId);
    } catch (err) {
      console.error('Failed to mark as unanswered:', err);
    }
  };

  return (
    <div className="flex h-[calc(100vh-64px)] bg-background">
      <ChatSidebar
        selectedId={selectedConversationId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        collapsed={historyCollapsed}
        onToggleCollapse={toggleHistoryCollapse}
      />

      {/* Main chat area - shrinks when sources panel is open */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="flex items-center gap-2 p-4 border-b border-border lg:hidden">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setIsSidebarOpen(true)}
          >
            <Menu size={20} />
          </Button>
          <h1 className="font-semibold">Hỏi đáp AI</h1>
        </header>

        {messages.length === 0 ? (
          <WelcomeScreen onSuggestionClick={handleSuggestionClick} />
        ) : (
          <div className="flex-1 overflow-y-auto p-4 space-y-6">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onCopy={handleCopy}
                onFeedback={handleFeedback}
                onMarkUnanswered={handleMarkUnanswered}
              />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        {isLoading && messages.length > 0 && (
          <div className="px-4 py-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Loader2 size={16} className="animate-spin" />
              <span>Đang xử lý...</span>
            </div>
          </div>
        )}

        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={handleSubmit}
          isLoading={isLoading}
          disabled={!user}
          placeholder={user ? 'Nhập câu hỏi của bạn...' : 'Vui lòng đăng nhập để sử dụng...'}
          modelSelector={
            <ModelSelector
              models={models}
              value={selectedModelId}
              onChange={handleModelChange}
              disabled={isLoading}
            />
          }
        />
      </div>

      {/* Right sources sidebar - slides in when active */}
      {isSourcesPanelOpen && <SourcesPanel />}

      {/* Document viewer modal (portal-like overlay) */}
      <DocumentViewerModal />
    </div>
  );
}

export default ChatContainer;