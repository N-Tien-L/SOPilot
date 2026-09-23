'use client';

import React from 'react';
import Link from 'next/link';
import { ChevronRight } from 'lucide-react';
import { clsx } from 'clsx';
import styles from './breadcrumb.module.css';

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[];
  className?: string;
  separator?: React.ReactNode;
}

export function Breadcrumb({ items, className, separator }: BreadcrumbProps) {
  const resolvedSeparator = separator || <ChevronRight size={14} className={styles.separator} />;

  return (
    <nav aria-label="Breadcrumb" className={clsx(styles.breadcrumb, className)}>
      <ol className={styles.list}>
        {items.map((item, index) => {
          const isLast = index === items.length - 1;
          return (
            <li key={index} className={styles.item}>
              {!isLast && item.href ? (
                <>
                  <Link href={item.href} className={styles.link}>
                    {item.label}
                  </Link>
                  {resolvedSeparator}
                </>
              ) : (
                <>
                  <span className={clsx(styles.link, styles.current)}>{item.label}</span>
                  {!isLast && resolvedSeparator}
                </>
              )}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

export default Breadcrumb;
