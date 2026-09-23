'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Eye, EyeOff, MessageSquare, CheckCircle } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { useLanguage } from '@/providers';
import styles from './reset-password.module.css';

function ResetPasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get('token');
  const { t } = useLanguage();

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [invalidToken, setInvalidToken] = useState(false);

  useEffect(() => {
    if (!token) {
      setInvalidToken(true);
    }
  }, [token]);

  const validate = (): string | null => {
    if (!password) return 'Password is required.';
    if (password.length < 8) return t('reset.password.placeholder');
    if (password !== confirmPassword) return t('validation.passwordMismatch');
    return null;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      // Call backend reset password endpoint
      // If endpoint doesn't exist, API will fail — handle gracefully
      await api.auth.resetPassword({ token: token!, newPassword: password });
      setSuccess(true);
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { data?: { message?: string; error?: { message?: string } } };
        message?: string;
      };
      setError(
        axiosError.response?.data?.message ||
        axiosError.response?.data?.error?.message ||
        axiosError.message ||
        t('reset.invalid.message')
      );
    } finally {
      setIsLoading(false);
    }
  };

  if (invalidToken) {
    return (
      <div className={styles.container}>
        <div className={styles.formContainer}>
          <div className={styles.errorCard}>
            <div className={styles.errorIcon}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
            </div>
            <h1 className={styles.errorTitle}>{t('reset.invalid.title')}</h1>
            <p className={styles.errorMessage}>
              {t('reset.invalid.message')}
            </p>
            <Link href="/forgot-password" className={styles.requestLink}>
              {t('reset.requestLink')}
            </Link>
          </div>
        </div>
        <div className={styles.background}>
          <div className={styles.gradient} />
          <div className={styles.pattern} />
        </div>
      </div>
    );
  }

  if (success) {
    return (
      <div className={styles.container}>
        <div className={styles.formContainer}>
          <div className={styles.successCard}>
            <div className={styles.successIcon}>
              <CheckCircle size={40} />
            </div>
            <h1 className={styles.successTitle}>{t('reset.success.title')}</h1>
            <p className={styles.successMessage}>
              {t('reset.success.message')}
            </p>
            <Link href="/login" className={styles.loginLink}>
              {t('reset.success.loginNow')}
            </Link>
          </div>
        </div>
        <div className={styles.background}>
          <div className={styles.gradient} />
          <div className={styles.pattern} />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.formContainer}>
        <Link href="/login" className={styles.backButton}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          <span>{t('reset.backToLogin')}</span>
        </Link>

        <div className={styles.header}>
          <div className={styles.logo}>
            <MessageSquare size={28} />
          </div>
          <h1 className={styles.title}>{t('reset.title')}</h1>
          <p className={styles.subtitle}>{t('reset.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && (
            <div className={styles.error} role="alert">
              {error}
            </div>
          )}

          <Input
            label={t('reset.password')}
            type={showPassword ? 'text' : 'password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={t('reset.password.placeholder')}
            required
            autoComplete="new-password"
            rightIcon={
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className={styles.passwordToggle}
                aria-label={showPassword ? t('reset.hidePassword') : t('reset.showPassword')}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            }
          />

          <Input
            label={t('reset.confirm')}
            type={showPassword ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            placeholder={t('reset.confirm.placeholder')}
            required
            autoComplete="new-password"
            error={confirmPassword && password !== confirmPassword ? t('validation.passwordMismatch') : undefined}
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={isLoading}
            disabled={!password || !confirmPassword || password !== confirmPassword}
          >
            {isLoading ? t('reset.submitting') : t('reset.submit')}
          </Button>
        </form>
      </div>

      <div className={styles.background}>
        <div className={styles.gradient} />
        <div className={styles.pattern} />
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
