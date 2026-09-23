'use client';

import React from 'react';
import { clsx } from 'clsx';
import styles from './card.module.css';

export interface CardProps {
  children: React.ReactNode;
  className?: string;
  padding?: 'none' | 'sm' | 'md' | 'lg';
  onClick?: () => void;
  style?: React.CSSProperties;
}

export function Card({ children, className, padding = 'md', onClick, style }: CardProps) {
  return (
    <div
      className={clsx(styles.card, styles[`padding-${padding}`], className)}
      onClick={onClick}
      style={style}
    >
      {children}
    </div>
  );
}

export interface CardHeaderProps {
  children: React.ReactNode;
  className?: string;
}

export function CardHeader({ children, className }: CardHeaderProps) {
  return <div className={clsx(styles.header, className)}>{children}</div>;
}

export interface CardTitleProps {
  children: React.ReactNode;
  className?: string;
  as?: 'h1' | 'h2' | 'h3' | 'h4';
}

export function CardTitle({ children, className, as: Tag = 'h3' }: CardTitleProps) {
  return <Tag className={clsx(styles.title, className)}>{children}</Tag>;
}

export interface CardDescriptionProps {
  children: React.ReactNode;
  className?: string;
}

export function CardDescription({ children, className }: CardDescriptionProps) {
  return <p className={clsx(styles.description, className)}>{children}</p>;
}

export interface CardContentProps {
  children: React.ReactNode;
  className?: string;
}

export function CardContent({ children, className }: CardContentProps) {
  return <div className={clsx(styles.content, className)}>{children}</div>;
}

export interface CardFooterProps {
  children: React.ReactNode;
  className?: string;
}

export function CardFooter({ children, className }: CardFooterProps) {
  return <div className={clsx(styles.footer, className)}>{children}</div>;
}

export default Card;
