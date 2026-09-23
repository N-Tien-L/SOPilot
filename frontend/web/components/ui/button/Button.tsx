'use client';

import React, { forwardRef, type ButtonHTMLAttributes } from 'react';
import { clsx } from 'clsx';
import { Loader2 } from 'lucide-react';
import styles from './button.module.css';

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'destructive' | 'outline' | 'success' | 'dangerOutline' | 'primaryOutline';
type ButtonSize = 'sm' | 'md' | 'lg' | 'icon';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  fullWidth?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary: styles.primary,
  secondary: styles.secondary,
  ghost: styles.ghost,
  destructive: styles.destructive,
  outline: styles.outline,
  success: styles.success,
  dangerOutline: styles.dangerOutline,
  primaryOutline: styles.primaryOutline,
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: styles.sm,
  md: styles.md,
  lg: styles.lg,
  icon: styles.icon,
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading = false,
      icon,
      iconPosition = 'left',
      fullWidth = false,
      disabled,
      children,
      className,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={clsx(
          styles.button,
          variantClasses[variant],
          sizeClasses[size],
          fullWidth && styles.fullWidth,
          loading && styles.loading,
          className
        )}
        {...props}
      >
        {loading && (
          <Loader2 size={size === 'sm' ? 14 : size === 'lg' ? 20 : 16} className={styles.spinner} />
        )}
        {!loading && icon && iconPosition === 'left' && (
          <span className={styles.iconWrapper}>{icon}</span>
        )}
        {children && <span>{children}</span>}
        {!loading && icon && iconPosition === 'right' && (
          <span className={styles.iconWrapper}>{icon}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;
