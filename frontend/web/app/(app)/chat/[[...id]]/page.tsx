'use client';

import { use } from 'react';
import { ChatView } from '@/components/chat/ChatView';
import { useSessionStore } from '@/store/session-store';

// /chat starts a conversation; /chat/<id> opens one. The view is keyed by workspace and id so
// switching either resets its local state and aborts a stream that is still open.
export default function ChatPage({ params }: { params: Promise<{ id?: string[] }> }) {
  const { id } = use(params);
  const wid = useSessionStore((s) => s.workspace?.id ?? 'none');
  const conversationId = id?.[0] ?? null;
  // Keyed by workspace too: a switch must drop the previous workspace's live turn (R7).
  return <ChatView key={`${wid}:${conversationId ?? 'new'}`} conversationId={conversationId} />;
}
