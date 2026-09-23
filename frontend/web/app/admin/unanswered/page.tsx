'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useRouter } from 'next/navigation';
import {
  HelpCircle,
  Search,
  CheckCircle,
  Loader2,
} from 'lucide-react';
import {
  Button,
  Input,
  Select,
  Badge,
  Table,
  Column,
  Modal,
  ConfirmDialog,
  EmptyState,
} from '@/components/ui';
import { api } from '@/lib/api';
import { useIsManager } from '@/store';
import { Translator } from '@/lib/i18n';
import { useLanguage } from '@/providers';
import styles from './unanswered.module.css';

type UnansweredStatus = 'PENDING' | 'REVIEWING' | 'ANSWERED' | 'REJECTED';

interface UnansweredQuestion {
  id: string;
  question: string;
  askCount: number;
  departmentName?: string;
  userName?: string;
  firstAskedAt: string;
  lastAskedAt: string;
  status: UnansweredStatus;
  suggestedAnswer?: string;
}

function getStatusConfig(t: Translator) {
  return {
    PENDING: { label: t('admin.unanswered.status.pending'), variant: 'warning' as const },
    REVIEWING: { label: t('admin.unanswered.status.reviewing'), variant: 'neutral' as const },
    ANSWERED: { label: t('admin.unanswered.status.answered'), variant: 'success' as const },
    REJECTED: { label: t('admin.unanswered.status.rejected'), variant: 'destructive' as const },
  };
}

export default function UnansweredQuestionsPage() {
  const router = useRouter();
  const isManager = useIsManager();
  const { t } = useLanguage();
  const STATUS_CONFIG = getStatusConfig(t);

  const [questions, setQuestions] = useState<UnansweredQuestion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  const [resolveTarget, setResolveTarget] = useState<UnansweredQuestion | null>(null);
  const [answerText, setAnswerText] = useState('');
  const [resolving, setResolving] = useState(false);

  const [rejectTarget, setRejectTarget] = useState<UnansweredQuestion | null>(null);
  const [rejecting, setRejecting] = useState(false);

  const tRef = useRef(t);
  tRef.current = t;

  const loadQuestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.analytics.getUnansweredQuestions(
        statusFilter ? { status: statusFilter } : undefined,
      );
      setQuestions(Array.isArray(response.data) ? response.data as UnansweredQuestion[] : []);
    } catch {
      setError(tRef.current('admin.unanswered.loadError'));
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    if (!isManager) {
      router.push('/');
      return;
    }
    loadQuestions();
  }, [isManager, router, loadQuestions]);

  const handleResolve = async () => {
    if (!resolveTarget || !answerText.trim()) return;
    setResolving(true);
    setError(null);
    try {
      await api.analytics.resolveUnanswered(resolveTarget.id, { answer: answerText.trim() });
      setResolveTarget(null);
      setAnswerText('');
      loadQuestions();
    } catch {
      setError(tRef.current('admin.unanswered.answerError'));
    } finally {
      setResolving(false);
    }
  };

  const handleReject = async () => {
    if (!rejectTarget) return;
    setRejecting(true);
    setError(null);
    try {
      await api.analytics.rejectUnanswered(rejectTarget.id);
      setRejectTarget(null);
      loadQuestions();
    } catch {
      setError(tRef.current('admin.unanswered.rejectError'));
    } finally {
      setRejecting(false);
    }
  };

  const filtered = questions.filter((q) => {
    if (search && !q.question.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter && q.status !== statusFilter) return false;
    return true;
  });

  const statusOptions = [
    { value: '', label: t('admin.unanswered.filter.allStatuses') },
    { value: 'PENDING', label: t('admin.unanswered.status.pending') },
    { value: 'REVIEWING', label: t('admin.unanswered.status.reviewing') },
    { value: 'ANSWERED', label: t('admin.unanswered.status.answered') },
    { value: 'REJECTED', label: t('admin.unanswered.status.rejected') },
  ];

  const columns: Column<UnansweredQuestion>[] = [
    {
      key: 'question',
      header: t('admin.unanswered.table.question'),
      render: (q) => (
        <div className={styles.questionCell}>
          <HelpCircle size={14} />
          <span>{q.question}</span>
        </div>
      ),
    },
    {
      key: 'askCount',
      header: t('admin.unanswered.table.count'),
      align: 'center',
      render: (q) => <Badge variant="neutral">{q.askCount}</Badge>,
    },
    {
      key: 'departmentName',
      header: t('admin.unanswered.table.department'),
      render: (q) => <span className={styles.deptText}>{q.departmentName || '-'}</span>,
    },
    {
      key: 'lastAskedAt',
      header: t('admin.unanswered.table.lastAsked'),
      render: (q) => new Date(q.lastAskedAt).toLocaleDateString('vi-VN'),
    },
    {
      key: 'status',
      header: t('admin.unanswered.table.status'),
      render: (q) => {
        const s = STATUS_CONFIG[q.status as keyof typeof STATUS_CONFIG];
        return <Badge variant={s.variant}>{s.label}</Badge>;
      },
    },
    {
      key: 'actions',
      header: '',
      width: '10rem',
      align: 'right',
      render: (q) =>
        q.status !== 'ANSWERED' && q.status !== 'REJECTED' ? (
          <div className={styles.rowActions}>
            <Button variant="ghost" size="sm" onClick={() => setResolveTarget(q)}>
              {t('admin.unanswered.action.answer')}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setRejectTarget(q)}>
              {t('admin.unanswered.action.reject')}
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <div className={styles.pageWrapper}>
      {/* Page Header */}
      <div className={styles.pageHeader}>
        <div className={styles.pageHeaderInner}>
          <div>
            <h1 className={styles.pageTitle}>{t('admin.unanswered.title')}</h1>
            <p className={styles.pageSubtitle}>{t('admin.unanswered.subtitle')}</p>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className={styles.pageBody}>
        {error && <div className={styles.error}>{error}</div>}

        <div className={styles.filters}>
          <Input
            placeholder={t('admin.unanswered.search.placeholder')}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            leftIcon={<Search size={16} />}
            inputSize="sm"
            className={styles.searchInput}
          />
          <Select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            options={statusOptions}
            selectSize="sm"
            className={styles.statusSelect}
          />
        </div>

        {loading ? (
          <div className={styles.loading}>
            <Loader2 size={24} className={styles.spinner} />
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<CheckCircle size={32} />}
            title={t('admin.unanswered.empty.title')}
            description={t('admin.unanswered.empty.description')}
          />
        ) : (
          <Table columns={columns} data={filtered} keyExtractor={(q) => q.id} />
        )}

        {/* Resolve Modal */}
        <Modal
          open={!!resolveTarget}
          onClose={() => { setResolveTarget(null); setAnswerText(''); }}
          title={t('admin.unanswered.modal.answer.title')}
          size="md"
          footer={
            <>
              <Button variant="secondary" onClick={() => { setResolveTarget(null); setAnswerText(''); }}>{t('admin.unanswered.modal.answer.cancel')}</Button>
              <Button variant="primary" loading={resolving} onClick={handleResolve} disabled={!answerText.trim()}>
                {t('admin.unanswered.modal.answer.submit')}
              </Button>
            </>
          }
        >
          <div className={styles.form}>
            <div className={styles.questionPreview}>
              <HelpCircle size={16} />
              <p>{resolveTarget?.question}</p>
            </div>
            {resolveTarget?.suggestedAnswer && (
              <div className={styles.suggested}>
                <span>{t('admin.unanswered.modal.answer.suggested')}</span>
                <p>{resolveTarget.suggestedAnswer}</p>
              </div>
            )}
            <textarea
              className={styles.answerInput}
              value={answerText}
              onChange={(e) => setAnswerText(e.target.value)}
              placeholder={t('admin.unanswered.modal.answer.placeholder')}
              rows={5}
            />
          </div>
        </Modal>

        {/* Reject Confirm */}
        <ConfirmDialog
          open={!!rejectTarget}
          onClose={() => setRejectTarget(null)}
          onConfirm={handleReject}
          loading={rejecting}
          title={t('admin.unanswered.modal.reject.title')}
          message={t('admin.unanswered.modal.reject.message').replace('{question}', rejectTarget?.question || '')}
          confirmLabel={t('admin.unanswered.modal.reject.confirm')}
          cancelLabel={t('admin.unanswered.modal.reject.cancel')}
          variant="warning"
        />
      </div>
    </div>
  );
}
