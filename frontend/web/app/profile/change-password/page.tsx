'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Eye, EyeOff, ArrowLeft, KeyRound, CheckCircle } from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { api } from '@/lib/api';
import styles from './change-password.module.css';

export default function ChangePasswordPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    if (error) setError(null);
  };

  const passwordStrength = (pwd: string): { level: number; label: string; color: string } => {
    if (!pwd) return { level: 0, label: '', color: '' };
    let score = 0;
    if (pwd.length >= 8) score++;
    if (pwd.length >= 12) score++;
    if (/[A-Z]/.test(pwd)) score++;
    if (/[a-z]/.test(pwd)) score++;
    if (/[0-9]/.test(pwd)) score++;
    if (/[^A-Za-z0-9]/.test(pwd)) score++;

    if (score <= 2) return { level: 1, label: 'Yếu', color: '#dc2626' };
    if (score <= 4) return { level: 2, label: 'Trung bình', color: '#d97706' };
    return { level: 3, label: 'Mạnh', color: '#16a34a' };
  };

  const strength = passwordStrength(formData.newPassword);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!formData.currentPassword) {
      setError('Vui lòng nhập mật khẩu hiện tại.');
      return;
    }
    if (!formData.newPassword) {
      setError('Vui lòng nhập mật khẩu mới.');
      return;
    }
    if (formData.newPassword.length < 8) {
      setError('Mật khẩu mới phải có ít nhất 8 ký tự.');
      return;
    }
    if (formData.newPassword === formData.currentPassword) {
      setError('Mật khẩu mới không được trùng với mật khẩu hiện tại.');
      return;
    }
    if (formData.newPassword !== formData.confirmPassword) {
      setError('Mật khẩu xác nhận không khớp.');
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await api.auth.changePassword({
        oldPassword: formData.currentPassword,
        newPassword: formData.newPassword,
        confirmPassword: formData.confirmPassword,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const axiosError = err as { message?: string };
      setError(axiosError.message || 'Đã xảy ra lỗi khi đổi mật khẩu.');
    } finally {
      setIsLoading(false);
    }
  };

  if (success) {
    return (
      <div className={styles.container}>
        <div className={styles.successCard}>
          <div className={styles.successIcon}>
            <CheckCircle size={40} />
          </div>
          <h1 className={styles.successTitle}>Đổi mật khẩu thành công</h1>
          <p className={styles.successMessage}>
            Mật khẩu của bạn đã được thay đổi. Nếu bạn đã đăng xuất khỏi các thiết bị khác, hãy đăng nhập lại với mật khẩu mới.
          </p>
          <div className={styles.successActions}>
            <Button variant="primary" onClick={() => router.push('/')}>
              Quay lại trang chủ
            </Button>
            <Button variant="secondary" onClick={() => router.push('/profile')}>
              Trang cá nhân
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.formContainer}>
        <Link href="/profile" className={styles.backButton}>
          <ArrowLeft size={18} />
          <span>Quay lại trang cá nhân</span>
        </Link>

        <div className={styles.header}>
          <div className={styles.iconWrapper}>
            <KeyRound size={24} />
          </div>
          <h1 className={styles.title}>Đổi mật khẩu</h1>
          <p className={styles.subtitle}>
            Sử dụng mật khẩu mạnh để bảo vệ tài khoản của bạn.
          </p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && (
            <div className={styles.error} role="alert">
              {error}
            </div>
          )}

          <Input
            label="Mật khẩu hiện tại"
            type={showCurrent ? 'text' : 'password'}
            value={formData.currentPassword}
            onChange={handleChange('currentPassword')}
            placeholder="Nhập mật khẩu hiện tại"
            required
            autoComplete="current-password"
            rightIcon={
              <button
                type="button"
                onClick={() => setShowCurrent(!showCurrent)}
                className={styles.passwordToggle}
                aria-label={showCurrent ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showCurrent ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            }
          />

          <Input
            label="Mật khẩu mới"
            type={showNew ? 'text' : 'password'}
            value={formData.newPassword}
            onChange={handleChange('newPassword')}
            placeholder="Ít nhất 8 ký tự"
            required
            autoComplete="new-password"
            rightIcon={
              <button
                type="button"
                onClick={() => setShowNew(!showNew)}
                className={styles.passwordToggle}
                aria-label={showNew ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
              >
                {showNew ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            }
          />

          {formData.newPassword && (
            <div className={styles.strengthWrapper}>
              <div className={styles.strengthBars}>
                {[1, 2, 3].map((level) => (
                  <div
                    key={level}
                    className={styles.strengthBar}
                    style={{
                      background: level <= strength.level ? strength.color : 'var(--border)',
                    }}
                  />
                ))}
              </div>
              <span className={styles.strengthLabel} style={{ color: strength.color }}>
                {strength.label}
              </span>
            </div>
          )}

          <Input
            label="Xác nhận mật khẩu mới"
            type="password"
            value={formData.confirmPassword}
            onChange={handleChange('confirmPassword')}
            placeholder="Nhập lại mật khẩu mới"
            required
            autoComplete="new-password"
            error={
              formData.confirmPassword && formData.newPassword !== formData.confirmPassword
                ? 'Mật khẩu không khớp'
                : undefined
            }
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={isLoading}
            disabled={
              !formData.currentPassword ||
              !formData.newPassword ||
              !formData.confirmPassword ||
              formData.newPassword !== formData.confirmPassword
            }
          >
            {isLoading ? 'Đang xử lý...' : 'Đổi mật khẩu'}
          </Button>
        </form>
      </div>
    </div>
  );
}
