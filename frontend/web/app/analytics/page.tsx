'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  MessageSquare,
  ThumbsUp,
  FileText,
  Users,
  Download,
  TrendingUp,
  LogIn,
} from 'lucide-react';
import {
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';
import {
  Button,
  Select,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Spinner,
  EmptyState,
} from '@/components/ui';
import { MainLayout } from '@/components/layout';
import { api } from '@/lib/api';
import { useIsManager } from '@/store';
import { useLanguage } from '@/providers';
import { ApiHealthCard, EndpointDetailsModal } from '@/components/api-health';
import type { DashboardStats, AnalyticsOverview, ApiMetricsResponse } from '@/types';
import styles from './analytics.module.css';

type Period = 'today' | 'week' | 'month';

const PIE_COLORS = ['var(--primary)', 'var(--success)', 'var(--warning)', 'var(--danger)'];

const DEFAULT_STATS: DashboardStats = {
  totalQuestions: 0, questionsToday: 0, questionsThisWeek: 0, questionsThisMonth: 0,
  activeDocuments: 0, totalDocuments: 0, activeUsers: 0, totalUsers: 0,
};

const DEFAULT_OVERVIEW: AnalyticsOverview = {
  stats: DEFAULT_STATS,
  questionTrend: [],
  questionsByDepartment: [],
  topQuestions: [],
  topDocuments: [],
  satisfaction: { likes: 0, dislikes: 0, rate: 0 },
};

export default function AnalyticsPage() {
  const router = useRouter();
  const isManager = useIsManager();
  const { t } = useLanguage();

  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [period, setPeriod] = useState<Period>('today');
  const [initialLoadDone, setInitialLoadDone] = useState(false);

  const [apiMetrics, setApiMetrics] = useState<ApiMetricsResponse | null>(null);
  const [apiMetricsLoading, setApiMetricsLoading] = useState(true);
  const [endpointModalOpen, setEndpointModalOpen] = useState(false);

  const [trends, setTrends] = useState<{
    date: string; questions: number; likes: number; dislikes: number;
    avgResponseTime?: number; uniqueUsers?: number;
  }[]>([]);
  const [topQuestions, setTopQuestions] = useState<{
    question: string; askCount: number; lastAskedAt: string;
  }[]>([]);
  const [topDocuments, setTopDocuments] = useState<{
    documentId: string; title: string; totalCitations: number; citationsLast7Days: number;
  }[]>([]);
  const [loginStats, setLoginStats] = useState<{
    loginsThisMonth: number; failedLoginsThisMonth: number;
  } | null>(null);

  const loadData = useCallback(async (currentPeriod: Period) => {
    if (!initialLoadDone) setLoading(true);
    const days = currentPeriod === 'today' ? 1 : currentPeriod === 'week' ? 7 : 30;

    const results = await Promise.allSettled([
      api.analytics.getDashboard().catch(() => null),
      api.analytics.getOverview().catch(() => null),
      api.analytics.getTrends(days).catch(() => []),
      api.analytics.getTopQuestions(5).catch(() => []),
      api.analytics.getTopDocuments(100).catch(() => []),
      api.auth.getLoginStats(days).catch(() => null),
      api.documents.getAll({ limit: 1 }).catch(() => null),
      api.documents.getAll({ limit: 1, status: 'READY' }).catch(() => null),
      api.users.search({ limit: 1 }).catch(() => null),
      api.users.search({ limit: 1, status: 'ACTIVE' }).catch(() => null),
    ]);

    const [
      statsData, overviewData, trendsData, questionsData, docsData, loginData,
      totalDocsData, activeDocsData, totalUsersData, activeUsersData
    ] = results as [
      PromiseFulfilledResult<DashboardStats | null>,
      PromiseFulfilledResult<AnalyticsOverview | null>,
      PromiseFulfilledResult<typeof trends | []>,
      PromiseFulfilledResult<typeof topQuestions | []>,
      PromiseFulfilledResult<typeof topDocuments | []>,
      PromiseFulfilledResult<{ loginSuccessCount: number; loginFailedCount: number } | null>,
      PromiseFulfilledResult<{ pagination: { total: number } } | null>,
      PromiseFulfilledResult<{ pagination: { total: number } } | null>,
      PromiseFulfilledResult<{ pagination: { total: number } } | null>,
      PromiseFulfilledResult<{ pagination: { total: number } } | null>,
    ];

    const resolvedStats = statsData.status === 'fulfilled' ? statsData.value : null;
    const resolvedOverview = overviewData.status === 'fulfilled' ? overviewData.value : null;
    const resolvedTrends = trendsData.status === 'fulfilled' ? trendsData.value : [];
    const resolvedQuestions = questionsData.status === 'fulfilled' ? questionsData.value : [];
    const resolvedDocs = docsData.status === 'fulfilled' ? docsData.value : [];
    const resolvedLogin = loginData.status === 'fulfilled' ? loginData.value : null;
    
    const realTotalDocs = totalDocsData.status === 'fulfilled' ? totalDocsData.value?.pagination?.total ?? 0 : 0;
    const realActiveDocs = activeDocsData.status === 'fulfilled' ? activeDocsData.value?.pagination?.total ?? 0 : 0;
    const realTotalUsers = totalUsersData.status === 'fulfilled' ? totalUsersData.value?.pagination?.total ?? 0 : 0;
    const realActiveUsers = activeUsersData.status === 'fulfilled' ? activeUsersData.value?.pagination?.total ?? 0 : 0;

    const baseStats = resolvedStats ?? DEFAULT_STATS;
    setStats({
      ...baseStats,
      totalDocuments: realTotalDocs || baseStats.totalDocuments,
      activeDocuments: realActiveDocs || baseStats.activeDocuments,
      totalUsers: realTotalUsers || baseStats.totalUsers,
      activeUsers: realActiveUsers || baseStats.activeUsers,
    });
    
    setOverview(resolvedOverview ?? DEFAULT_OVERVIEW);
    setTrends(Array.isArray(resolvedTrends) ? resolvedTrends : []);
    setTopQuestions(Array.isArray(resolvedQuestions) ? resolvedQuestions : []);
    setTopDocuments(Array.isArray(resolvedDocs) ? resolvedDocs.slice(0, 5) : []);
    setLoginStats(resolvedLogin ? {
      loginsThisMonth: resolvedLogin.loginSuccessCount,
      failedLoginsThisMonth: resolvedLogin.loginFailedCount,
    } : null);
    
    const allFailed = !resolvedStats && !resolvedOverview && !resolvedTrends?.length && !resolvedQuestions?.length && !resolvedDocs?.length;
    if (allFailed) {
      setError(t('analytics.loadError'));
    } else {
      setError(null);
    }
    setLoading(false);
    setInitialLoadDone(true);
  }, [t, initialLoadDone]);

  const loadApiMetrics = useCallback(async (currentPeriod: Period) => {
    setApiMetricsLoading(true);
    try {
      const days = currentPeriod === 'today' ? 1 : currentPeriod === 'week' ? 7 : 30;
      const data = await api.metrics.getApiHealth(days);
      setApiMetrics(data);
    } catch {
      setApiMetrics(null);
    } finally {
      setApiMetricsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!isManager) {
      router.push('/');
      return;
    }
    loadData(period);
    loadApiMetrics(period);
  }, [isManager, period, loadData, loadApiMetrics, router]);

  useEffect(() => {
    if (!isManager) return;
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
        loadData(period);
        loadApiMetrics(period);
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [isManager, period, loadData, loadApiMetrics]);

  const getStatValue = (key: keyof DashboardStats) => {
    if (!stats) return 0;
    if (key === 'questionsToday') {
      return (period === 'today' ? stats.questionsToday
        : period === 'week' ? stats.questionsThisWeek
        : stats.questionsThisMonth) ?? 0;
    }
    return (stats[key] as number) ?? 0;
  };

  const { likes: likeCount = 0, dislikes: dislikeCount = 0 } = overview?.satisfaction || {};
  const totalFeedback = likeCount + dislikeCount;
  const satisfactionRate = totalFeedback > 0 ? Math.round((likeCount / totalFeedback) * 100) : 0;

  const currentPeriodQuestions = period === 'today' ? (stats?.questionsToday ?? 0)
    : period === 'week' ? (stats?.questionsThisWeek ?? 0)
    : (stats?.questionsThisMonth ?? 0);
  const previousPeriodQuestions = period === 'today' ? (stats?.questionsThisWeek ?? 0) - (stats?.questionsToday ?? 0)
    : period === 'week' ? (stats?.questionsThisMonth ?? 0) - (stats?.questionsThisWeek ?? 0)
    : (stats?.totalQuestions ?? 0) - (stats?.questionsThisMonth ?? 0);
  const questionsChange = previousPeriodQuestions > 0
    ? Math.round(((currentPeriodQuestions - previousPeriodQuestions) / previousPeriodQuestions) * 100)
    : 0;

  const pieData = [
    { name: t('analytics.chart.useful'), value: likeCount },
    { name: t('analytics.chart.notUseful'), value: dislikeCount },
  ].filter((d) => d.value > 0);

  const periodOptions = [
    { value: 'today', label: t('analytics.period.today') },
    { value: 'week', label: t('analytics.period.week') },
    { value: 'month', label: t('analytics.period.month') },
  ];

  if (loading) {
    return (
      <MainLayout>
        <div className={styles.loading}>
          <Spinner size="lg" label={t('analytics.loading')} />
        </div>
      </MainLayout>
    );
  }

  if (error || !stats) {
    return (
      <MainLayout>
        <div className={styles.container}>
          <EmptyState
            icon={<TrendingUp size={32} />}
            title={t('analytics.empty')}
            description={error || t('analytics.loadError')}
            action={<Button variant="secondary" onClick={() => loadData(period)}>{t('analytics.retry')}</Button>}
          />
        </div>
      </MainLayout>
    );
  }

  return (
    <MainLayout>
      <div className={styles.container}>
        {/* Header */}
        <div className={styles.header}>
          <div>
            <h1 className={styles.title}>{t('analytics.title')}</h1>
            <p className={styles.subtitle}>{t('analytics.subtitle')}</p>
          </div>
          <div className={styles.actions}>
            <Select
              value={period}
              onChange={(e) => setPeriod(e.target.value as Period)}
              options={periodOptions}
              selectSize="sm"
              className={styles.periodSelect}
            />
            <Button
              variant="secondary"
              size="sm"
              icon={<Download size={16} />}
              onClick={() => router.push('/analytics/reports')}
            >
              {t('analytics.export')}
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className={styles.statsGrid}>
          <Card padding="md">
            <div className={styles.statCardInner}>
              <div className={`${styles.statIconWrap} ${styles.statIconPrimary}`}>
                <MessageSquare size={22} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statLabel}>{t('analytics.stat.questions')}</span>
                <div className={styles.statValueRow}>
                  <span className={styles.statValue}>{getStatValue('questionsToday').toLocaleString()}</span>
                  {questionsChange !== 0 && (
                    <span className={`${styles.changeBadge} ${questionsChange > 0 ? styles.changePositive : styles.changeNegative}`}>
                      {questionsChange > 0 ? '+' : ''}{questionsChange}%
                    </span>
                  )}
                </div>
                {(stats.questionsThisWeek ?? 0) > 0 && (
                  <span className={styles.statMeta}>
                    {(stats.questionsThisMonth ?? 0).toLocaleString()} {t('analytics.stat.questionsMonth')}
                  </span>
                )}
              </div>
            </div>
          </Card>

          <Card padding="md">
            <div className={styles.statCardInner}>
              <div className={`${styles.statIconWrap} ${styles.statIconSuccess}`}>
                <ThumbsUp size={22} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statLabel}>{t('analytics.stat.satisfaction')}</span>
                <span className={styles.statValue}>{satisfactionRate}%</span>
                <span className={styles.statMeta}>
                  {likeCount} {t('analytics.chart.useful')} / {dislikeCount} {t('analytics.chart.notUseful')}
                </span>
              </div>
            </div>
          </Card>

          <Card padding="md">
            <div className={styles.statCardInner}>
              <div className={`${styles.statIconWrap} ${styles.statIconInfo}`}>
                <FileText size={22} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statLabel}>{t('analytics.stat.activeDocuments')}</span>
                <span className={styles.statValue}>{stats.activeDocuments}</span>
                <span className={styles.statMeta}>{stats.totalDocuments} {t('analytics.stat.totalDocuments')}</span>
              </div>
            </div>
          </Card>

          <Card padding="md">
            <div className={styles.statCardInner}>
              <div className={`${styles.statIconWrap} ${styles.statIconWarning}`}>
                <Users size={22} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statLabel}>{t('analytics.stat.activeUsers')}</span>
                <span className={styles.statValue}>{stats.activeUsers}</span>
                <span className={styles.statMeta}>{stats.totalUsers} {t('analytics.stat.totalUsers')}</span>
              </div>
            </div>
          </Card>

          <ApiHealthCard
            metrics={apiMetrics}
            loading={apiMetricsLoading}
            onClick={() => setEndpointModalOpen(true)}
            label={t('analytics.apiHealth.label')}
            loadingLabel={t('analytics.apiHealth.loading')}
            noDataLabel={t('analytics.apiHealth.noData')}
            errorsLabel={t('analytics.apiHealth.errors')}
            totalRequestsLabel={t('analytics.apiHealth.totalRequests')}
          />

          <Card padding="md">
            <div className={styles.statCardInner}>
              <div className={`${styles.statIconWrap} ${styles.statIconSuccess}`}>
                <LogIn size={22} />
              </div>
              <div className={styles.statContent}>
                <span className={styles.statLabel}>{t('analytics.stat.logins')}</span>
                <span className={styles.statValue}>{(loginStats?.loginsThisMonth ?? 0).toLocaleString()}</span>
              </div>
            </div>
          </Card>

        </div>

        {/* Charts Row */}
        <div className={styles.chartsGrid}>
          {/* Trends Chart */}
          <Card padding="md" className={styles.chartCard}>
            <CardHeader>
              <CardTitle as="h3">{t('analytics.chart.trends')}</CardTitle>
            </CardHeader>
            <CardContent>
              {trends.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={trends}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                      tickFormatter={(v) => {
                        const d = new Date(v);
                        return `${d.getDate()}/${d.getMonth() + 1}`;
                      }}
                    />
                    <YAxis tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }} />
                    <Tooltip
                      contentStyle={{
                        background: 'var(--card)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        fontSize: '0.8125rem',
                      }}
                    />
                    <Legend wrapperStyle={{ fontSize: '0.8125rem' }} />
                    <Line type="monotone" dataKey="questions" stroke="var(--primary)" strokeWidth={2} name={t('analytics.chart.question')} dot={false} />
                    <Line type="monotone" dataKey="likes" stroke="var(--success)" strokeWidth={2} name={t('analytics.chart.useful')} dot={false} />
                    <Line type="monotone" dataKey="dislikes" stroke="var(--danger)" strokeWidth={2} name={t('analytics.chart.notUseful')} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className={styles.chartEmpty}>
                  <TrendingUp size={32} />
                  <span>{t('analytics.chart.empty')}</span>
                </div>
              )}
              {trends.length > 0 && (() => {
                const avgRT = trends.reduce((sum, t) => sum + (t.avgResponseTime ?? 0), 0) / (trends.length || 1);
                const totalUsers = trends.reduce((sum, t) => sum + (t.uniqueUsers ?? 0), 0);
                return (
                  <div className={styles.trendMetrics}>
                    <span>{t('analytics.trendMetrics.avgResponse')}: {avgRT > 0 ? `${Math.round(avgRT)}ms` : '-'}</span>
                    <span>{t('analytics.trendMetrics.uniqueUsers')}: {totalUsers > 0 ? totalUsers.toLocaleString() : '-'}</span>
                  </div>
                );
              })()}
            </CardContent>
          </Card>

          {/* Feedback Pie Chart */}
          <Card padding="md" className={styles.chartCard}>
            <CardHeader>
              <CardTitle as="h3">{t('analytics.chart.feedback')}</CardTitle>
            </CardHeader>
            <CardContent>
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height={220}>
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={90}
                      paddingAngle={4}
                      dataKey="value"
                    >
                      {pieData.map((_, index) => (
                        <Cell key={index} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: 'var(--card)',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        fontSize: '0.8125rem',
                      }}
                      formatter={(value) => [`${value} responses`, '']}
                    />
                    <Legend wrapperStyle={{ fontSize: '0.8125rem' }} />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className={styles.chartEmpty}>
                  <ThumbsUp size={32} />
                  <span>{t('analytics.chart.feedbackEmpty')}</span>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Error Trend Chart */}
        {apiMetrics && apiMetrics.dailyErrors.length > 0 && (
          <Card padding="md" className={styles.chartCard}>
            <CardHeader>
              <CardTitle as="h3">{t('analytics.chart.apiErrors')}</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={apiMetrics.dailyErrors}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                    tickFormatter={(v) => {
                      const d = new Date(v);
                      return `${d.getDate()}/${d.getMonth() + 1}`;
                    }}
                  />
                  <YAxis
                    tick={{ fontSize: 12, fill: 'var(--muted-foreground)' }}
                    allowDecimals={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: 'var(--card)',
                      border: '1px solid var(--border)',
                      borderRadius: 'var(--radius)',
                      fontSize: '0.8125rem',
                    }}
                    formatter={(value) => [`${value} errors`, 'Errors']}
                  />
                  <Line
                    type="monotone"
                    dataKey="errors"
                    stroke="var(--danger)"
                    strokeWidth={2}
                    name="Errors"
                    dot={{ fill: 'var(--danger)', r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Top Questions + Documents */}
        <div className={styles.listsGrid}>
          <Card padding="md">
            <CardHeader>
              <CardTitle as="h3">{t('analytics.list.questions')}</CardTitle>
            </CardHeader>
            <CardContent>
              {topQuestions.length > 0 ? (
                <div className={styles.topList}>
                  {topQuestions.map((q, i) => (
                    <div key={i} className={styles.topItem}>
                      <span className={styles.topRank}>{i + 1}</span>
                      <div className={styles.topInfo}>
                        <span className={styles.topQuestion}>{q.question}</span>
                        <span className={styles.topMeta}>
                          {q.askCount} · {new Date(q.lastAskedAt).toLocaleDateString('vi-VN')}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.emptyText}>{t('analytics.list.questions.empty')}</p>
              )}
            </CardContent>
          </Card>

          <Card padding="md">
            <CardHeader>
              <CardTitle as="h3">{t('analytics.list.documents')}</CardTitle>
            </CardHeader>
            <CardContent>
              {topDocuments.length > 0 ? (
                <div className={styles.topList}>
                  {topDocuments.map((d, i) => (
                    <div key={i} className={styles.topItem}>
                      <span className={styles.topRank}>{i + 1}</span>
                      <div className={styles.topInfo}>
                        <span className={styles.topQuestion}>{d.title}</span>
                        <span className={styles.topMeta}>
                          {d.totalCitations} {t('analytics.list.citations')}
                          {d.citationsLast7Days > 0 && ` · +${d.citationsLast7Days} ${t('analytics.list.citationsWeek')}`}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className={styles.emptyText}>{t('analytics.list.documents.empty')}</p>
              )}
            </CardContent>
          </Card>
        </div>

        <EndpointDetailsModal
          open={endpointModalOpen}
          onClose={() => setEndpointModalOpen(false)}
          metrics={apiMetrics}
          titleLabel={t('analytics.endpointDetails.title')}
          totalRequestsLabel={t('analytics.endpointDetails.totalRequests')}
          successLabel={t('analytics.endpointDetails.success')}
          errorsLabel={t('analytics.endpointDetails.errors')}
          noDataLabel={t('analytics.endpointDetails.noData')}
          colEndpoint={t('analytics.endpointDetails.colEndpoint')}
          colTotal={t('analytics.endpointDetails.colTotal')}
          colSuccess={t('analytics.endpointDetails.colSuccess')}
          colErrors={t('analytics.endpointDetails.colErrors')}
          colRate={t('analytics.endpointDetails.colRate')}
          colAvgResponse={t('analytics.endpointDetails.colAvgResponse')}
          recentErrorsLabel={t('analytics.endpointDetails.recentErrors')}
        />
      </div>
    </MainLayout>
  );
}
