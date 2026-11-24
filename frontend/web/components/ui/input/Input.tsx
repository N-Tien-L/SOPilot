'use client';

import React, { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  inputSize?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASSES = {
  sm: 'h-8 text-xs',
  md: 'h-10 text-sm',
  lg: 'h-11 text-sm',
};

export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    {
      label,
      error,
      helperText,
      leftIcon,
      rightIcon,
      inputSize = 'md',
      className,
      id,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label htmlFor={inputId} className="text-xs font-semibold text-foreground">
            {label}
            {props.required ? <span className="ml-1 text-danger-foreground">*</span> : null}
          </label>
        ) : null}
        <div
          className={cn(
            'relative flex items-center rounded-xl border bg-background transition-all focus-within:ring-2',
            SIZE_CLASSES[inputSize],
            hasError
              ? 'border-danger focus-within:border-danger focus-within:ring-danger/20'
              : 'border-input focus-within:border-primary focus-within:ring-ring/20',
            props.disabled && 'cursor-not-allowed bg-muted opacity-60',
            className,
          )}
        >
          {leftIcon ? (
            <span className="pointer-events-none flex items-center pl-3 text-muted-foreground">
              {leftIcon}
            </span>
          ) : null}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              'h-full w-full flex-1 bg-transparent px-3 text-foreground placeholder:text-placeholder focus:outline-none disabled:cursor-not-allowed',
              leftIcon && 'pl-2',
              rightIcon && 'pr-2',
            )}
            {...props}
          />
          {rightIcon ? (
            <span className="flex items-center pr-3 text-muted-foreground">{rightIcon}</span>
          ) : null}
        </div>
        {error ? <p className="text-xs font-medium text-danger-foreground">{error}</p> : null}
        {!error && helperText ? <p className="text-xs text-muted-foreground">{helperText}</p> : null}
      </div>
    );
  },
);

Input.displayName = 'Input';

export default Input;
