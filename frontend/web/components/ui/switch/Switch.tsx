'use client';

import React, { useId } from 'react';
import * as RadixSwitch from '@radix-ui/react-switch';
import { cn } from '@/lib/utils';

export interface SwitchProps {
  checked?: boolean;
  defaultChecked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  disabled?: boolean;
  label?: string;
  description?: string;
  className?: string;
}

export function Switch({
  checked,
  defaultChecked,
  onCheckedChange,
  disabled,
  label,
  description,
  className,
}: SwitchProps) {
  const id = useId();

  return (
    <div className={cn('inline-flex items-center gap-3', className)}>
      <RadixSwitch.Root
        id={id}
        checked={checked}
        defaultChecked={defaultChecked}
        onCheckedChange={onCheckedChange}
        disabled={disabled}
        className="peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent bg-input transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary"
      >
        <RadixSwitch.Thumb className="pointer-events-none block h-4 w-4 rounded-full bg-white shadow-sm transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0" />
      </RadixSwitch.Root>
      {label || description ? (
        <label htmlFor={id} className="cursor-pointer select-none">
          {label ? <span className="block text-sm font-medium text-foreground">{label}</span> : null}
          {description ? <span className="block text-xs text-muted-foreground">{description}</span> : null}
        </label>
      ) : null}
    </div>
  );
}

export default Switch;
