'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, MessageSquare, Sparkles, Shield, Zap } from 'lucide-react';
import { Button, Input, Checkbox } from '@/components/ui';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store';
import { useLanguage } from '@/providers';
import styles from './login.module.css';

interface LoginError {
  code: string;
  message: string;
}

export default function LoginPage() {
  const router = useRouter();
  const { setUser, setTokens } = useAuthStore();
  const { t } = useLanguage();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<LoginError | null>(null);

  const ERROR_MESSAGES: Record<string, string> = {
    UNAUTHORIZED: t('login.error.unauthorized'),
    ACCOUNT_DEACTIVATED: t('login.error.deactivated'),
    ACCOUNT_REVOKED: t('login.error.revoked'),
    RATE_LIMIT_EXCEEDED: t('login.error.rateLimit'),
    VALIDATION_ERROR: t('login.error.validation'),
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const response = await api.auth.login({ username, password });

      setUser(response.user);
      setTokens(response.accessToken, response.refreshToken);

      if (typeof window !== 'undefined') {
        localStorage.setItem('userId', response.user.id);
        localStorage.setItem('userRole', response.user.role);
        if (rememberMe) {
          localStorage.setItem('rememberUsername', username);
        } else {
          localStorage.removeItem('rememberUsername');
        }
      }

      router.push('/');
    } catch (err: unknown) {
      const axiosError = err as {
        response?: {
          data?: {
            success?: boolean;
            error?: string | { code?: string; message?: string };
            message?: string;
          };
        };
        message?: string;
      };
      const errorData = axiosError.response?.data?.error;
      const errorMessage = axiosError.response?.data?.message;
      let errorCode: string;
      let message: string;

      if (typeof errorData === 'string') {
        errorCode = errorData;
        message = errorMessage || ERROR_MESSAGES[errorCode] || axiosError.message || t('login.error.unknown');
      } else if (typeof errorData === 'object' && errorData !== null) {
        errorCode = (errorData as { code?: string }).code || 'UNKNOWN';
        message = (errorData as { message?: string }).message || ERROR_MESSAGES[errorCode] || errorMessage || axiosError.message || t('login.error.unknown');
      } else {
        errorCode = 'UNKNOWN';
        message = errorMessage || axiosError.message || t('login.error.unknown');
      }

      setError({
        code: errorCode,
        message: message,
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.formContainer}>
        <div className={styles.formWrapper}>
          <div className={styles.header}>
            <div className={styles.logoWrapper}>
              <div className={styles.logoGlow} />
              <div className={styles.logo}>
                <MessageSquare size={28} />
              </div>
            </div>
            <h1 className={styles.title}>{t('login.title')}</h1>
            <p className={styles.subtitle}>{t('login.subtitle')}</p>
          </div>

          <form onSubmit={handleSubmit} className={styles.form}>
            {error && (
              <div className={styles.error} role="alert">
                <div className={styles.errorIcon}>
                  <Shield size={18} />
                </div>
                <span>{error.message}</span>
              </div>
            )}

            <div className={styles.inputGroup}>
              <Input
                label={t('login.username')}
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder={t('login.username.placeholder')}
                required
                autoComplete="username"
                leftIcon={<span className={styles.inputIcon}>@</span>}
                autoFocus
              />
            </div>

            <div className={styles.inputGroup}>
              <Input
                label={t('login.password')}
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('login.password.placeholder')}
                required
                autoComplete="current-password"
                rightIcon={
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className={styles.passwordToggle}
                    aria-label={showPassword ? t('login.hidePassword') : t('login.showPassword')}
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />
            </div>

            <div className={styles.rememberRow}>
              <Checkbox
                id="remember"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                label={t('login.rememberMe')}
              />
              <Link href="/forgot-password" className={styles.forgotLink}>
                {t('login.forgotPassword')}
              </Link>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              loading={isLoading}
              disabled={isLoading || !username.trim() || !password}
            >
              {isLoading ? t('login.submitting') : t('login.submit')}
            </Button>
          </form>

          <p className={styles.footer}>
            {t('login.footer')}{' '}
            <span className={styles.adminContact}>{t('login.footer.admin')}</span>{' '}
            {t('login.footer.account')}
          </p>
        </div>
      </div>

      <div className={styles.visualSide}>
        <div className={styles.visualContent}>
          <div className={styles.visualBadge}>
            <Sparkles size={16} />
            <span>AI-Powered</span>
          </div>
          <h2 className={styles.visualTitle}>Chào mừng đến với Poliwise</h2>
          <p className={styles.visualText}>
            Nền tảng quản lý tri thức thông minh với AI, giúp bạn tìm kiếm và quản lý tài liệu hiệu quả.
          </p>

          <div className={styles.features}>
            <div className={styles.feature}>
              <div className={styles.featureIcon}>
                <Zap size={20} />
              </div>
              <div>
                <h4>Tìm kiếm thông minh</h4>
                <p>Trả lời câu hỏi bằng AI từ tài liệu của bạn</p>
              </div>
            </div>
            <div className={styles.feature}>
              <div className={styles.featureIcon}>
                <Shield size={20} />
              </div>
              <div>
                <h4>Bảo mật cao</h4>
                <p>Quản lý quyền truy cập theo vai trò</p>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.floatingOrbs}>
          <div className={styles.orb1} />
          <div className={styles.orb2} />
          <div className={styles.orb3} />
        </div>
      </div>

      <div className={styles.background}>
        <div className={styles.gradient} />
        <div className={styles.pattern} />
      </div>
    </div>
  );
}
