'use client';

import React from 'react';
import { ChevronLeft, ChevronRight, MoreHorizontal } from 'lucide-react';
import { clsx } from 'clsx';
import styles from './pagination.module.css';

export interface PaginationProps {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  siblingCount?: number;
  className?: string;
}

function getPageNumbers(current: number, total: number, siblingCount: number): (number | 'ellipsis')[] {
  const range = (start: number, end: number) =>
    Array.from({ length: end - start + 1 }, (_, i) => start + i);

  const leftSibling = Math.max(current - siblingCount, 1);
  const rightSibling = Math.min(current + siblingCount, total);

  const showLeftEllipsis = leftSibling > 2;
  const showRightEllipsis = rightSibling < total - 1;

  if (!showLeftEllipsis && !showRightEllipsis) {
    return range(1, total);
  }

  if (showLeftEllipsis && !showRightEllipsis) {
    return [1, 'ellipsis', ...range(total - 3, total)];
  }

  if (!showLeftEllipsis && showRightEllipsis) {
    return [...range(1, 4), 'ellipsis', total];
  }

  return [1, 'ellipsis', ...range(leftSibling, rightSibling), 'ellipsis', total];
}

export function Pagination({
  page,
  totalPages,
  onPageChange,
  siblingCount = 1,
  className,
}: PaginationProps) {
  if (totalPages <= 1) return null;

  const pageNumbers = getPageNumbers(page, totalPages, siblingCount);

  return (
    <nav
      className={clsx(styles.pagination, className)}
      aria-label="Pagination"
    >
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page === 1}
        className={styles.button}
        aria-label="Previous page"
      >
        <ChevronLeft size={18} />
      </button>

      <div className={styles.pages}>
        {pageNumbers.map((p, i) =>
          p === 'ellipsis' ? (
            <span key={`ellipsis-${i}`} className={styles.ellipsis}>
              <MoreHorizontal size={16} />
            </span>
          ) : (
            <button
              key={p}
              type="button"
              onClick={() => onPageChange(p)}
              className={clsx(styles.pageButton, p === page && styles.active)}
              aria-current={p === page ? 'page' : undefined}
            >
              {p}
            </button>
          )
        )}
      </div>

      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page === totalPages}
        className={styles.button}
        aria-label="Next page"
      >
        <ChevronRight size={18} />
      </button>
    </nav>
  );
}

export default Pagination;
