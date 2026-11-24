'use client';

import React, { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Loader2 } from 'lucide-react';
import { cn } from '@/lib/utils';

const buttonVariants = cva(
  'inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap rounded-xl font-semibold transition-all duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary:
          'bg-primary text-primary-foreground shadow-sm hover:opacity-95',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-muted/80 border border-border/60',
        ghost:
          'bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground',
        destructive:
          'bg-destructive text-destructive-foreground shadow-sm hover:opacity-95',
        outline:
          'border border-border bg-card text-foreground shadow-2xs hover:border-border-strong hover:bg-muted/60',
        success:
          'bg-success text-white shadow-sm hover:opacity-95',
        dangerOutline:
          'border border-danger/40 bg-transparent text-danger-foreground hover:bg-danger-soft',
        primaryOutline:
          'border border-primary/40 bg-transparent text-primary-strong hover:bg-primary-soft',
      },
      size: {
        sm: 'h-8 px-3 text-xs rounded-lg',
        md: 'h-10 px-4 text-sm',
        lg: 'h-11 px-5 text-sm',
        icon: 'h-9 w-9 p-0',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  },
);

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  loading?: boolean;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  fullWidth?: boolean;
}

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
    ref,
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        disabled={isDisabled}
        className={cn(
          buttonVariants({ variant, size }),
          fullWidth && 'w-full',
          className,
        )}
        {...props}
      >
        {loading ? (
          <Loader2
            size={size === 'sm' ? 14 : size === 'lg' ? 18 : 16}
            className="animate-spin shrink-0"
            aria-hidden
          />
        ) : null}
        {!loading && icon && iconPosition === 'left' ? (
          <span className="inline-flex shrink-0 items-center">{icon}</span>
        ) : null}
        {children ? <span>{children}</span> : null}
        {!loading && icon && iconPosition === 'right' ? (
          <span className="inline-flex shrink-0 items-center">{icon}</span>
        ) : null}
      </button>
    );
  },
);

Button.displayName = 'Button';

export default Button;
