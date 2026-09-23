'use client';

import React, { forwardRef, useId, type InputHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import styles from './switch.module.css';

export interface SwitchProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type'> {
  label?: string;
  description?: string;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
  ({ label, description, className, id, ...props }, ref) => {
    const generatedId = useId();
    const switchId = id || generatedId;

    return (
      <div className={styles.wrapper}>
        <label htmlFor={switchId} className={styles.container}>
          <input
            ref={ref}
            type="checkbox"
            id={switchId}
            className={clsx(styles.input, className)}
            {...props}
          />
          <div className={styles.track}>
            <div className={styles.thumb} />
          </div>
          {(label || description) && (
            <div className={styles.content}>
              {label && <span className={styles.label}>{label}</span>}
              {description && <span className={styles.description}>{description}</span>}
            </div>
          )}
        </label>
      </div>
    );
  }
);

Switch.displayName = 'Switch';

export default Switch;
