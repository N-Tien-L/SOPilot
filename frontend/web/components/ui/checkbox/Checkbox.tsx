'use client';

import React, { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
  error?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, description, error, className, id, ...props }, ref) => {
    const generatedId = useId();
    const checkboxId = id || generatedId;

    return (
      <div className="flex flex-col gap-1">
        <label
          htmlFor={checkboxId}
          className={cn(
            'inline-flex cursor-pointer items-start gap-2.5 select-none',
            props.disabled && 'cursor-not-allowed opacity-50',
          )}
        >
          <span className="relative mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
            <input
              ref={ref}
              type="checkbox"
              id={checkboxId}
              className={cn(
                'peer h-4 w-4 cursor-pointer appearance-none rounded-[5px] border border-input bg-background transition-all checked:border-primary checked:bg-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed',
                error && 'border-danger',
                className,
              )}
              {...props}
            />
            <svg
              viewBox="0 0 12 10"
              fill="none"
              aria-hidden
              className="pointer-events-none absolute h-2.5 w-2.5 scale-75 text-primary-foreground opacity-0 transition-all peer-checked:scale-100 peer-checked:opacity-100"
            >
              <path
                d="M1.5 5L4.5 8L10.5 2"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          {label || description ? (
            <span className="flex flex-col">
              {label ? <span className="text-sm font-medium text-foreground">{label}</span> : null}
              {description ? <span className="text-xs text-muted-foreground">{description}</span> : null}
            </span>
          ) : null}
        </label>
        {error ? <p className="text-xs font-medium text-danger-foreground">{error}</p> : null}
      </div>
    );
  },
);

Checkbox.displayName = 'Checkbox';

export default Checkbox;
