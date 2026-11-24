'use client';

import React, { forwardRef, useId, type SelectHTMLAttributes } from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  options: SelectOption[];
  placeholder?: string;
  /** The placeholder is a real "no value" choice (filters such as "All statuses"), not just a hint. */
  allowEmpty?: boolean;
  selectSize?: 'sm' | 'md' | 'lg';
}

const SIZE_CLASSES = {
  sm: 'h-8 text-xs',
  md: 'h-10 text-sm',
  lg: 'h-11 text-sm',
};

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      helperText,
      options,
      placeholder,
      allowEmpty = false,
      selectSize = 'md',
      className,
      id,
      value,
      onChange,
      style,
      ...props
    },
    ref,
  ) => {
    const generatedId = useId();
    const selectId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className="flex flex-col gap-1.5">
        {label ? (
          <label htmlFor={selectId} className="text-xs font-semibold text-foreground">
            {label}
            {props.required ? <span className="ml-1 text-danger-foreground">*</span> : null}
          </label>
        ) : null}
        <div
          className={cn(
            'relative flex items-center rounded-xl border bg-background transition-all focus-within:ring-2',
            SIZE_CLASSES[selectSize],
            hasError
              ? 'border-danger focus-within:border-danger focus-within:ring-danger/20'
              : 'border-input focus-within:border-primary focus-within:ring-ring/20',
            props.disabled && 'cursor-not-allowed bg-muted opacity-60',
            className,
          )}
        >
          <select
            ref={ref}
            id={selectId}
            value={value}
            onChange={onChange}
            style={{
              appearance: 'none',
              WebkitAppearance: 'none',
              MozAppearance: 'none',
              backgroundImage: 'none',
              ...style,
            }}
            className="select-clean w-full flex-1 cursor-pointer bg-transparent py-2 pl-3 pr-9 leading-5 text-foreground focus:outline-none disabled:cursor-not-allowed"
            {...props}
          >
            {placeholder ? (
              <option value="" disabled={!allowEmpty} className="bg-card text-foreground">
                {placeholder}
              </option>
            ) : null}
            {options.map((option) => (
              <option
                key={option.value}
                value={option.value}
                disabled={option.disabled}
                className="bg-card text-foreground"
              >
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={15}
            aria-hidden
            className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          />
        </div>
        {error ? <p className="text-xs font-medium text-danger-foreground">{error}</p> : null}
        {!error && helperText ? <p className="text-xs text-muted-foreground">{helperText}</p> : null}
      </div>
    );
  },
);

Select.displayName = 'Select';

export default Select;
