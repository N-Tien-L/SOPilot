'use client';

import React from 'react';
import Image from 'next/image';
import { clsx } from 'clsx';
import styles from './avatar.module.css';

type AvatarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export interface AvatarProps {
  src?: string;
  name?: string;
  size?: AvatarSize;
  className?: string;
}

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getColorFromName(name: string): string {
  const colors = [
    '#4f46e5', '#7c3aed', '#db2777', '#ea580c',
    '#16a34a', '#0891b2', '#4338ca', '#9333ea',
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export function Avatar({ src, name, size = 'md', className }: AvatarProps) {
  const initials = name ? getInitials(name) : '?';
  const bgColor = name ? getColorFromName(name) : 'var(--muted-foreground)';

  return (
    <div className={clsx(styles.avatar, styles[size], className)}>
      {src ? (
        <Image
          src={src}
          alt={name || 'Avatar'}
          fill
          className={styles.image}
          unoptimized
        />
      ) : (
        <div className={styles.fallback} style={{ background: bgColor }}>
          <span className={styles.initials}>{initials}</span>
        </div>
      )}
    </div>
  );
}

export default Avatar;
