'use client';

import React, { forwardRef, useId, type SelectHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { ChevronDown } from 'lucide-react';
import styles from './select.module.css';

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
  selectSize?: 'sm' | 'md' | 'lg';
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  (
    {
      label,
      error,
      helperText,
      options,
      placeholder,
      selectSize = 'md',
      className,
      id,
      value,
      onChange,
      ...props
    },
    ref
  ) => {
    const generatedId = useId();
    const selectId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className={styles.wrapper}>
        {label && (
          <label htmlFor={selectId} className={styles.label}>
            {label}
            {props.required && <span className={styles.required}>*</span>}
          </label>
        )}
        <div
          className={clsx(
            styles.selectWrapper,
            styles[selectSize],
            hasError && styles.error,
            props.disabled && styles.disabled,
            className
          )}
        >
          <select
            ref={ref}
            id={selectId}
            className={styles.select}
            value={value}
            onChange={onChange}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {options.map((option) => (
              <option key={option.value} value={option.value} disabled={option.disabled}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown size={16} className={styles.chevron} />
        </div>
        {error && <p className={styles.errorText}>{error}</p>}
        {!error && helperText && <p className={styles.helperText}>{helperText}</p>}
      </div>
    );
  }
);

Select.displayName = 'Select';

export default Select;
