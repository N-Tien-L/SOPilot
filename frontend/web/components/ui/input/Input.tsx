'use client';

import React, { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import styles from './input.module.css';

export interface InputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'size'> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  inputSize?: 'sm' | 'md' | 'lg';
}

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
    ref
  ) => {
    const generatedId = useId();
    const inputId = id || generatedId;
    const hasError = Boolean(error);

    return (
      <div className={styles.wrapper}>
        {label && (
          <label htmlFor={inputId} className={styles.label}>
            {label}
            {props.required && <span className={styles.required}>*</span>}
          </label>
        )}
        <div
          className={clsx(
            styles.inputWrapper,
            styles[inputSize],
            hasError && styles.error,
            props.disabled && styles.disabled,
            className
          )}
        >
          {leftIcon && <span className={styles.leftIcon}>{leftIcon}</span>}
          <input
            ref={ref}
            id={inputId}
            className={clsx(styles.input, leftIcon && styles.withLeftIcon, rightIcon && styles.withRightIcon)}
            {...props}
          />
          {rightIcon && <span className={styles.rightIcon}>{rightIcon}</span>}
        </div>
        {error && <p className={styles.errorText}>{error}</p>}
        {!error && helperText && <p className={styles.helperText}>{helperText}</p>}
      </div>
    );
  }
);

Input.displayName = 'Input';

export default Input;
