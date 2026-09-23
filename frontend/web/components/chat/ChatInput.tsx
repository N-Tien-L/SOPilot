'use client';

import React, { useRef, useEffect } from 'react';
import { Send, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui';

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
  modelSelector?: React.ReactNode;
}

export function ChatInput({
  value,
  onChange,
  onSubmit,
  isLoading = false,
  disabled = false,
  placeholder = 'Nhập câu hỏi của bạn...',
  modelSelector,
}: ChatInputProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 120)}px`;
    }
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !isLoading) {
        onSubmit(value.trim());
      }
    }
  };

  const handleSubmit = () => {
    if (value.trim() && !isLoading) {
      onSubmit(value.trim());
    }
  };

  return (
    <div className="border-t border-border bg-background p-4">
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <div className="flex-1 relative">
          <textarea
            ref={textareaRef}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled || isLoading}
            rows={1}
            className="w-full resize-none bg-muted border border-input rounded-xl px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-all disabled:opacity-50 disabled:cursor-not-allowed max-h-[120px]"
            style={{ minHeight: '48px' }}
          />
        </div>
        {modelSelector}
        <Button
          onClick={handleSubmit}
          disabled={!value.trim() || isLoading || disabled}
          size="lg"
          className="flex-shrink-0 h-12 w-12 rounded-xl"
          icon={
            isLoading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : (
              <Send size={20} />
            )
          }
        />
      </div>
      <p className="text-xs text-muted-foreground text-center mt-2">
        Nhấn <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Enter</kbd> để gửi,{' '}
        <kbd className="px-1.5 py-0.5 bg-muted rounded text-[10px]">Shift + Enter</kbd> để xuống dòng
      </p>
    </div>
  );
}

export default ChatInput;