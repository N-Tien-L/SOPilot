'use client';

import React, { useState } from 'react';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  ChevronRight,
  ChevronDown,
} from 'lucide-react';
import { Modal } from '@/components/ui/modal/Modal';
import type { ApiMetricsResponse, ApiEndpointMetrics } from '@/types';
import styles from './endpoint-details-modal.module.css';

interface EndpointDetailsModalProps {
  open: boolean;
  onClose: () => void;
  metrics: ApiMetricsResponse | null;
  titleLabel?: string;
  totalRequestsLabel?: string;
  successLabel?: string;
  errorsLabel?: string;
  noDataLabel?: string;
  colEndpoint?: string;
  colTotal?: string;
  colSuccess?: string;
  colErrors?: string;
  colRate?: string;
  colAvgResponse?: string;
  recentErrorsLabel?: string;
}

interface EndpointRowProps {
  endpoint: ApiEndpointMetrics;
  recentErrorsLabel?: string;
}

function EndpointRow({ endpoint, recentErrorsLabel = 'Recent errors' }: EndpointRowProps) {
  const [expanded, setExpanded] = useState(false);
  const successRate =
    endpoint.total > 0
      ? Math.round((endpoint.success / endpoint.total) * 100)
      : 100;

  const getHealthClass = () => {
    if (endpoint.failure === 0) return styles.successTone;
    if (successRate >= 90) return styles.warningTone;
    return styles.dangerTone;
  };

  const healthClass = getHealthClass();

  return (
    <>
      <tr
        className={styles.tr}
        onClick={() => setExpanded((v) => !v)}
        style={{ cursor: endpoint.recentErrors.length > 0 ? 'pointer' : 'default' }}
      >
        <td className={styles.td}>
          <span className={styles.path}>{endpoint.path}</span>
        </td>
        <td className={styles.td}>
          <span className={styles.total}>{endpoint.total.toLocaleString()}</span>
        </td>
        <td className={styles.td}>
          <span className={`${styles.success} ${styles.successTone}`}>
            <CheckCircle size={14} />
            {endpoint.success.toLocaleString()}
          </span>
        </td>
        <td className={styles.td}>
          {endpoint.failure > 0 ? (
            <span className={`${styles.failure} ${styles.dangerTone}`}>
              <XCircle size={14} />
              {endpoint.failure.toLocaleString()}
            </span>
          ) : (
            <span className={styles.noErrors}>
              <CheckCircle size={14} />
              0
            </span>
          )}
        </td>
        <td className={styles.td}>
          <div className={styles.rateCell}>
            <div className={styles.barBg}>
              <div
                className={styles.barFill}
                style={{ width: `${successRate}%` }}
                data-health={endpoint.failure === 0 ? 'success' : successRate >= 90 ? 'warning' : 'danger'}
              />
            </div>
            <span className={`${styles.rateValue} ${healthClass}`}>
              {successRate}%
            </span>
          </div>
        </td>
        <td className={styles.td}>
          <span className={styles.responseTime}>
            <Clock size={14} />
            {endpoint.avgResponseTime}ms
          </span>
        </td>
        <td className={styles.td}>
          {endpoint.recentErrors.length > 0 ? (
            <button
              className={styles.expandBtn}
              onClick={(e) => {
                e.stopPropagation();
                setExpanded((v) => !v);
              }}
            >
              {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
            </button>
          ) : null}
        </td>
      </tr>
      {expanded && endpoint.recentErrors.length > 0 && (
        <tr className={styles.expandedRow}>
          <td colSpan={7} className={styles.expandedCell}>
            <div className={styles.errorsList}>
              <span className={styles.errorsTitle}>{recentErrorsLabel}</span>
              {endpoint.recentErrors.map((err, i) => (
                <div key={i} className={styles.errorItem}>
                  <span className={styles.errorTime}>
                    {new Date(err.timestamp).toLocaleString('vi-VN')}
                  </span>
                  <span className={styles.errorMethod}>{err.method}</span>
                  <span
                    className={`${styles.errorStatus} ${
                      err.statusCode >= 500
                        ? styles.dangerTone
                        : err.statusCode >= 400
                          ? styles.warningTone
                          : styles.neutralTone
                    }`}
                  >
                    {err.statusCode}
                  </span>
                  <span className={styles.errorPath}>{err.path}</span>
                </div>
              ))}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export function EndpointDetailsModal({
  open,
  onClose,
  metrics,
  titleLabel = 'Endpoint Details',
  totalRequestsLabel = 'Total requests',
  successLabel = 'Success',
  errorsLabel = 'Errors',
  noDataLabel = 'No endpoint data yet',
  colEndpoint = 'Endpoint',
  colTotal = 'Total',
  colSuccess = 'Success',
  colErrors = 'Errors',
  colRate = 'Success rate',
  colAvgResponse = 'Avg response',
  recentErrorsLabel = 'Recent errors',
}: EndpointDetailsModalProps) {
  if (!metrics) return null;

  const { overall, endpoints } = metrics;
  const sorted = [...endpoints].sort((a, b) => b.failure - a.failure);

  return (
    <Modal open={open} onClose={onClose} title={titleLabel} size="xl">
      <div className={styles.summary}>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>{totalRequestsLabel}</span>
          <span className={styles.summaryValue}>{overall.totalRequests.toLocaleString()}</span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>{successLabel}</span>
          <span className={`${styles.summaryValue} ${styles.successTone}`}>
            {(overall.totalRequests - overall.totalErrors).toLocaleString()}
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>{errorsLabel}</span>
          <span className={`${styles.summaryValue} ${styles.dangerTone}`}>
            {overall.totalErrors.toLocaleString()}
          </span>
        </div>
        <div className={styles.summaryItem}>
          <span className={styles.summaryLabel}>{colRate}</span>
          <span
            className={`${styles.summaryValue} ${
              overall.successRate >= 99
                ? styles.successTone
                : overall.successRate >= 95
                  ? styles.warningTone
                  : styles.dangerTone
            }`}
          >
            {overall.successRate}%
          </span>
        </div>
      </div>

      {endpoints.length === 0 ? (
        <div className={styles.empty}>
          <AlertCircle size={32} />
          <span>{noDataLabel}</span>
        </div>
      ) : (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr className={styles.thead}>
                <th className={styles.th}>{colEndpoint}</th>
                <th className={styles.th}>{colTotal}</th>
                <th className={styles.th}>{colSuccess}</th>
                <th className={styles.th}>{colErrors}</th>
                <th className={styles.th}>{colRate}</th>
                <th className={styles.th}>{colAvgResponse}</th>
                <th className={styles.th}></th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((ep, i) => (
                <EndpointRow key={i} endpoint={ep} recentErrorsLabel={recentErrorsLabel} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Modal>
  );
}
