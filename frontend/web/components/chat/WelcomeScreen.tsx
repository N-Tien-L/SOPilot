'use client';

import React from 'react';
import { MessageSquare, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui';
import { useAuthStore } from '@/store';

interface WelcomeScreenProps {
  onSuggestionClick: (text: string) => void;
}

const SUGGESTIONS = [
  'Chính sách nhân sự mới nhất là gì?',
  'Quy trình xin nghỉ phép như thế nào?',
  'Các quy định về bảo mật thông tin?',
  'Chính sách lương và thưởng',
  'Quy trình tuyển dụng',
  'Chính sách đào tạo nhân viên',
];

export function WelcomeScreen({ onSuggestionClick }: WelcomeScreenProps) {
  const { user } = useAuthStore();

  return (
    <div className="flex flex-col items-center justify-center flex-1 px-6 py-12 max-w-2xl mx-auto w-full">
      <div className="w-20 h-20 rounded-2xl bg-primary/10 flex items-center justify-center mb-6">
        <MessageSquare size={40} className="text-primary" />
      </div>
      <h1 className="text-2xl font-bold text-foreground mb-2">
        Xin chào, {user?.username || 'bạn'}!
      </h1>
      <p className="text-muted-foreground text-center mb-8">
        Tôi có thể giúp gì cho bạn hôm nay? Hãy hỏi về chính sách, quy trình hoặc bất kỳ vấn đề nào liên quan đến công việc.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 w-full">
        {SUGGESTIONS.map((suggestion) => (
          <button
            key={suggestion}
            onClick={() => onSuggestionClick(suggestion)}
            className="text-left p-4 bg-background border border-border rounded-xl hover:border-primary/50 hover:bg-primary/5 transition-all text-sm text-foreground hover:text-primary group"
          >
            <div className="flex items-start gap-2">
              <Sparkles size={14} className="text-primary mt-0.5 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity" />
              <span>{suggestion}</span>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-8 text-center text-xs text-muted-foreground">
        <p>Câu trả lời được tạo dựa trên tài liệu trong hệ thống.</p>
        <p>Nếu câu hỏi không được trả lời, bạn có thể đánh dấu để đội ngũ xem xét.</p>
      </div>
    </div>
  );
}

export default WelcomeScreen;