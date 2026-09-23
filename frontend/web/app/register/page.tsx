'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, MessageSquare, UserPlus } from 'lucide-react';
import { Button, Input, Select } from '@/components/ui';
import { api } from '@/lib/api';
import { UserRole } from '@/types';
import { useLanguage } from '@/providers';
import styles from './register.module.css';

export default function RegisterPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: UserRole.USER,
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const roleOptions = [
    { value: UserRole.USER, label: t('role.user') },
    { value: UserRole.MANAGER, label: t('role.manager') },
    { value: UserRole.ADMIN, label: t('role.admin') },
  ];

  const handleChange = (field: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    if (error) setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Inline validation
    if (!formData.username.trim()) {
      setError('Username is required.');
      return;
    }
    if (formData.username.trim().length < 3) {
      setError('Username must be at least 3 characters.');
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(formData.username.trim())) {
      setError('Username can only contain letters, numbers, and underscores.');
      return;
    }
    if (!formData.email.trim()) {
      setError('Email is required.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email.trim())) {
      setError('Email is invalid.');
      return;
    }
    if (!formData.password) {
      setError('Password is required.');
      return;
    }
    if (formData.password.length < 8) {
      setError(t('validation.passwordMinLength'));
      return;
    }
    if (formData.password !== formData.confirmPassword) {
      setError(t('validation.passwordMismatch'));
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await api.auth.register({
        username: formData.username.trim(),
        email: formData.email.trim(),
        password: formData.password,
        role: formData.role,
      });
      setSuccess(t('register.success').replace('{username}', formData.username));
      setFormData({ username: '', email: '', password: '', confirmPassword: '', role: UserRole.USER });
    } catch (err: unknown) {
      const axiosError = err as {
        response?: { data?: { error?: { message?: string } } };
        message?: string;
      };
      setError(
        axiosError.response?.data?.error?.message ||
        axiosError.message ||
        'An error occurred while creating the account.'
      );
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.formContainer}>
        <button
          type="button"
          onClick={() => router.back()}
          className={styles.backButton}
        >
          <ArrowLeft size={18} />
          <span>{t('register.back')}</span>
        </button>

        <div className={styles.header}>
          <div className={styles.logo}>
            <MessageSquare size={28} />
          </div>
          <h1 className={styles.title}>{t('register.title')}</h1>
          <p className={styles.subtitle}>{t('register.subtitle')}</p>
        </div>

        <form onSubmit={handleSubmit} className={styles.form}>
          {error && (
            <div className={styles.error} role="alert">
              {error}
            </div>
          )}

          {success && (
            <div className={styles.success} role="status">
              <UserPlus size={18} />
              <span>{success}</span>
            </div>
          )}

          <Input
            label={t('register.username')}
            type="text"
            value={formData.username}
            onChange={handleChange('username')}
            placeholder={t('register.username.placeholder')}
            required
            autoComplete="username"
            helperText={t('register.username.helper')}
          />

          <Input
            label={t('register.email')}
            type="email"
            value={formData.email}
            onChange={handleChange('email')}
            placeholder={t('register.email.placeholder')}
            required
            autoComplete="email"
          />

          <Select
            label={t('register.role')}
            value={formData.role}
            onChange={handleChange('role')}
            options={roleOptions}
            required
            helperText={t('register.role.helper')}
          />

          <Input
            label={t('register.password')}
            type="password"
            value={formData.password}
            onChange={handleChange('password')}
            placeholder={t('register.password.placeholder')}
            required
            autoComplete="new-password"
          />

          <Input
            label={t('register.confirm')}
            type="password"
            value={formData.confirmPassword}
            onChange={handleChange('confirmPassword')}
            placeholder={t('register.confirm.placeholder')}
            required
            autoComplete="new-password"
            error={formData.confirmPassword && formData.password !== formData.confirmPassword ? t('validation.passwordMismatch') : undefined}
          />

          <Button
            type="submit"
            variant="primary"
            size="lg"
            fullWidth
            loading={isLoading}
            icon={<UserPlus size={18} />}
          >
            {isLoading ? t('register.submitting') : t('register.submit')}
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
