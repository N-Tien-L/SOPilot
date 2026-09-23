'use client';

import React from 'react';
import { clsx } from 'clsx';
import styles from './table.module.css';

export interface Column<T> {
  key: string;
  header: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (row: T, index: number) => React.ReactNode;
}

export interface TableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (row: T) => string;
  loading?: boolean;
  empty?: React.ReactNode;
  className?: string;
  onRowClick?: (row: T) => void;
  selectedKeys?: Set<string>;
  onSelectionChange?: (keys: Set<string>) => void;
}

export function Table<T>({
  columns,
  data,
  keyExtractor,
  loading,
  empty,
  className,
  onRowClick,
  selectedKeys,
  onSelectionChange,
}: TableProps<T>) {
  const renderEmpty = () => {
    if (empty) return empty;
    return (
      <tr>
        <td colSpan={columns.length} className={styles.emptyCell}>
          Không có dữ liệu
        </td>
      </tr>
    );
  };

  const renderLoading = () => {
    return (
      <>
        {Array.from({ length: 5 }).map((_, i) => (
          <tr key={`skeleton-${i}`} className={styles.skeletonRow}>
            {columns.map((col) => (
              <td key={col.key} className={styles.cell}>
                <div className={styles.skeleton} />
              </td>
            ))}
          </tr>
        ))}
      </>
    );
  };

  const allSelected = data.length > 0 && data.every((row) => selectedKeys?.has(keyExtractor(row)));
  const someSelected = data.some((row) => selectedKeys?.has(keyExtractor(row)));

  return (
    <div className={clsx(styles.wrapper, className)}>
      <div className={styles.tableContainer}>
        <table className={styles.table}>
          <thead>
            <tr>
              {onSelectionChange && (
                <th className={clsx(styles.th, styles.checkboxCell)}>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    ref={(el) => {
                      if (el) el.indeterminate = someSelected && !allSelected;
                    }}
                    onChange={(e) => {
                      if (e.target.checked) {
                        const allKeys = new Set(data.map(keyExtractor));
                        onSelectionChange(allKeys);
                      } else {
                        onSelectionChange(new Set());
                      }
                    }}
                    className={styles.checkbox}
                  />
                </th>
              )}
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={styles.th}
                  style={{ width: col.width, textAlign: col.align || 'left' }}
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading
              ? renderLoading()
              : data.length === 0
                ? renderEmpty()
                : data.map((row, index) => {
                    const key = keyExtractor(row);
                    const isSelected = selectedKeys?.has(key);
                    return (
                      <tr
                        key={key}
                        className={clsx(
                          styles.row,
                          isSelected && styles.selected,
                          onRowClick && styles.clickable,
                          loading && styles.loading
                        )}
                        onClick={onRowClick ? () => onRowClick(row) : undefined}
                      >
                        {onSelectionChange && (
                          <td className={clsx(styles.td, styles.checkboxCell)}>
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={(e) => {
                                e.stopPropagation();
                                const next = new Set(selectedKeys);
                                if (e.target.checked) {
                                  next.add(key);
                                } else {
                                  next.delete(key);
                                }
                                onSelectionChange(next);
                              }}
                              className={styles.checkbox}
                            />
                          </td>
                        )}
                        {columns.map((col) => (
                          <td
                            key={col.key}
                            className={styles.td}
                            style={{ textAlign: col.align || 'left' }}
                          >
                            {col.render
                              ? col.render(row, index)
                              : ((row as Record<string, unknown>)[col.key] as React.ReactNode)}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default Table;
