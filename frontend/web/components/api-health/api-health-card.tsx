'use client';

import React from 'react';
import { Activity, AlertCircle, CheckCircle, XCircle } from 'lucide-react';
import { Card } from '@/components/ui';
import type { ApiMetricsResponse } from '@/types';
import styles from './api-health-card.module.css';

interface ApiHealthCardProps {
  metrics: ApiMetricsResponse | null;
  loading: boolean;
  onClick: () => void;
  label?: string;
  loadingLabel?: string;
  noDataLabel?: string;
  errorsLabel?: string;
  totalRequestsLabel?: string;
}

export function ApiHealthCard({
  metrics, loading, onClick,
  label = 'API Health',
  loadingLabel = 'Loading...',
  noDataLabel = 'No data',
  errorsLabel = 'errors',
  totalRequestsLabel = 'total requests',
}: ApiHealthCardProps) {
  if (loading) {
    return (
      <Card padding="md" className={styles.card}>
        <div className={styles.inner}>
          <div className={`${styles.iconWrap} ${styles.neutral}`}>
            <Activity size={22} />
          </div>
          <div className={styles.content}>
            <span className={styles.label}>{label}</span>
            <span className={styles.loading}>{loadingLabel}</span>
          </div>
        </div>
      </Card>
    );
  }

  if (!metrics) {
    return (
      <Card padding="md" className={styles.card} onClick={onClick}>
        <div className={styles.inner}>
          <div className={`${styles.iconWrap} ${styles.danger}`}>
            <AlertCircle size={22} />
          </div>
          <div className={styles.content}>
            <span className={styles.label}>{label}</span>
            <span className={styles.subValue}>{noDataLabel}</span>
          </div>
        </div>
      </Card>
    );
  }

  const { overall, endpoints } = metrics;
  const errorCount = overall.totalErrors;
  const successRate = overall.successRate;
  const failedEndpoints = endpoints.filter((e) => e.failure > 0).length;

  const getHealthStatus = () => {
    if (successRate >= 99) return { className: styles.success, icon: <CheckCircle size={22} /> };
    if (successRate >= 95) return { className: styles.warning, icon: <AlertCircle size={22} /> };
    return { className: styles.danger, icon: <XCircle size={22} /> };
  };

  const status = getHealthStatus();

  return (
    <Card
      padding="md"
      className={styles.card}
      onClick={onClick}
    >
      <div className={styles.inner}>
        <div className={`${styles.iconWrap} ${status.className}`}>
          {status.icon}
        </div>
        <div className={styles.content}>
          <span className={styles.label}>{label}</span>
          <div className={styles.row}>
            <span className={`${styles.mainValue} ${status.className}`}>
              {successRate}%
            </span>
            <span className={styles.separator}>/</span>
            <span className={styles.subValue}>
              {errorCount} {errorsLabel}
              {failedEndpoints > 0 && (
                <span className={styles.badge}>
                  {failedEndpoints} endpoint{failedEndpoints > 1 ? 's' : ''}
                </span>
              )}
            </span>
          </div>
          <span className={styles.meta}>
            {overall.totalRequests.toLocaleString()} {totalRequestsLabel}
          </span>
        </div>
        <div className={styles.arrow}>
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M6 12L10 8L6 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
      </div>
    </Card>
  );
}
