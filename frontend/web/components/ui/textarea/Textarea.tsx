'use client';

import React, { forwardRef, useId, type TextareaHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, helperText, className, id, ...props }, ref) => {
    const generatedId = useId();
    const textareaId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label htmlFor={textareaId} className="text-xs font-semibold text-foreground">
            {label}
            {props.required ? <span className="ml-1 text-danger-foreground">*</span> : null}
          </label>
        ) : null}
        <textarea
          ref={ref}
          id={textareaId}
          className={cn(
            'min-h-[84px] w-full rounded-xl border bg-background px-3 py-2 text-sm text-foreground placeholder:text-placeholder transition-all focus:outline-none focus:ring-2 disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60',
            hasError
              ? 'border-danger focus:border-danger focus:ring-danger/20'
              : 'border-input focus:border-primary focus:ring-ring/20',
            className,
          )}
          {...props}
        />
        {error ? <p className="text-xs font-medium text-danger-foreground">{error}</p> : null}
        {!error && helperText ? <p className="text-xs text-muted-foreground">{helperText}</p> : null}
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';

export default Textarea;
