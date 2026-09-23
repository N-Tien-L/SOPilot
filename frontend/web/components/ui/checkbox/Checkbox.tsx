'use client';

import React, { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import styles from './checkbox.module.css';

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
      <div className={styles.wrapper}>
        <label htmlFor={checkboxId} className={styles.container}>
          <input
            ref={ref}
            type="checkbox"
            id={checkboxId}
            className={clsx(styles.input, error && styles.error, className)}
            {...props}
          />
          <div className={styles.control}>
            <svg viewBox="0 0 12 10" fill="none" className={styles.icon}>
              <path
                d="M1.5 5L4.5 8L10.5 2"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </div>
          {(label || description) && (
            <div className={styles.content}>
              {label && <span className={styles.label}>{label}</span>}
              {description && <span className={styles.description}>{description}</span>}
            </div>
          )}
        </label>
        {error && <p className={styles.errorText}>{error}</p>}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';

export default Checkbox;
