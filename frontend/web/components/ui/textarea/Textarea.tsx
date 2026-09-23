'use client';

import React, { forwardRef, useId, type TextareaHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import styles from './textarea.module.css';

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
      <div className={styles.wrapper}>
        {label && (
          <label htmlFor={textareaId} className={styles.label}>
            {label}
            {props.required && <span className={styles.required}>*</span>}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={clsx(styles.textarea, hasError && styles.error, className)}
          {...props}
        />
        {error && <p className={styles.errorText}>{error}</p>}
        {!error && helperText && <p className={styles.helperText}>{helperText}</p>}
      </div>
    );
  }
);

Textarea.displayName = 'Textarea';

export default Textarea;
