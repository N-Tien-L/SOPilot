'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  User,
  Mail,
  Shield,
  Building,
  Calendar,
  Lock,
  Eye,
  EyeOff,
  AlertCircle,
  CheckCircle,
  Phone,
  Briefcase,
  FileText,
  Camera,
  Clock,
  ArrowLeft,
} from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store';
import { useLanguage } from '@/providers';
import { LoginHistoryModal } from '@/components/profile/LoginHistoryModal';
import styles from './profile.module.css';

type TabKey = 'profile' | 'edit' | 'security';

interface FullProfile {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  departmentId: string | null;
  departmentName: string | null;
  createdAt: string;
  passwordChangedAt: string | null;
  mustChangePassword: boolean;
  fullName?: string;
  phone?: string | null;
  position?: string | null;
  bio?: string | null;
  dateOfBirth?: string | null;
  employeeCode?: string | null;
  joinedDate?: string | null;
}

interface EditFormData {
  fullName: string;
  phone: string;
  position: string;
  bio: string;
  dateOfBirth: string;
}

const EMPTY_EDIT: EditFormData = {
  fullName: '',
  phone: '',
  position: '',
  bio: '',
  dateOfBirth: '',
};

interface PasswordForm {
  oldPassword: string;
  newPassword: string;
  confirmPassword: string;
}

export default function ProfilePage() {
  const router = useRouter();
  const { user, isAuthenticated, _hasHydrated } = useAuthStore();
  const { t } = useLanguage();
  const [profile, setProfile] = useState<FullProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabKey>('profile');

  const [editForm, setEditForm] = useState<EditFormData>(EMPTY_EDIT);
  const [editErrors, setEditErrors] = useState<Partial<Record<keyof EditFormData, string>>>({});
  const [isSaving, setIsSaving] = useState(false);
  const [editSuccess, setEditSuccess] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [passwordForm, setPasswordForm] = useState<PasswordForm>({
    oldPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [showPasswords, setShowPasswords] = useState({ old: false, new: false, confirm: false });
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);
  const [showLoginHistory, setShowLoginHistory] = useState(false);

  useEffect(() => {
    if (!_hasHydrated) return;
    if (!isAuthenticated) {
      router.push('/login');
      return;
    }
    loadProfile();
  }, [_hasHydrated, isAuthenticated]);

  const loadProfile = useCallback(async () => {
    try {
      setIsLoading(true);
      const data = await api.profile.getFull();
      setProfile(data as FullProfile);
      setEditForm({
        fullName: (data as FullProfile).fullName || '',
        phone: (data as FullProfile).phone || '',
        position: (data as FullProfile).position || '',
        bio: (data as FullProfile).bio || '',
        dateOfBirth: (data as FullProfile).dateOfBirth || '',
      });
    } catch (err) {
      console.error('Failed to load profile:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const validateEditForm = (): boolean => {
    const errors: Partial<Record<keyof EditFormData, string>> = {};
    if (!editForm.fullName.trim()) {
      errors.fullName = t('validation.fullNameRequired');
    } else if (editForm.fullName.trim().length > 200) {
      errors.fullName = t('validation.fullNameMaxLength');
    }
    if (editForm.phone && !/^\+?[0-9]{7,15}$/.test(editForm.phone.replace(/\s/g, ''))) {
      errors.phone = t('validation.phoneInvalid');
    }
    if (editForm.bio && editForm.bio.length > 1000) {
      errors.bio = t('validation.bioMaxLength');
    }
    if (editForm.position && editForm.position.length > 200) {
      errors.position = t('validation.positionMaxLength');
    }
    setEditErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEditError(null);
    setEditSuccess(false);
    if (!validateEditForm()) return;

    try {
      setIsSaving(true);
      await api.profile.update({
        fullName: editForm.fullName.trim() || undefined,
        phone: editForm.phone.trim() || undefined,
        position: editForm.position.trim() || undefined,
        bio: editForm.bio.trim() || undefined,
        dateOfBirth: editForm.dateOfBirth || undefined,
      });
      setEditSuccess(true);
      await loadProfile();
      setTimeout(() => setEditSuccess(false), 4000);
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        (err as Error)?.message ||
        t('validation.saveError');
      setEditError(msg);
    } finally {
      setIsSaving(false);
    }
  };

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(false);

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError(t('validation.passwordNewMismatch'));
      return;
    }
    if (passwordForm.newPassword.length < 8) {
      setPasswordError(t('validation.passwordMinLength'));
      return;
    }

    try {
      setIsChangingPassword(true);
      const result = await api.auth.changePassword({
        oldPassword: passwordForm.oldPassword,
        newPassword: passwordForm.newPassword,
        confirmPassword: passwordForm.confirmPassword,
      });
      if (result.success) {
        setPasswordSuccess(true);
        setPasswordForm({ oldPassword: '', newPassword: '', confirmPassword: '' });
      } else {
        setPasswordError(result.message);
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { message?: string } }; message?: string };
      setPasswordError(
        axiosError.response?.data?.message || axiosError.message || t('validation.passwordChangeError')
      );
    } finally {
      setIsChangingPassword(false);
    }
  };

  const getPasswordStrength = (password: string) => {
    let strength = 0;
    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[a-z]/.test(password)) strength++;
    if (/[A-Z]/.test(password)) strength++;
    if (/[0-9]/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;
    if (strength <= 2) return { label: t('profile.security.strength.weak'), color: '#ef4444', strength };
    if (strength <= 4) return { label: t('profile.security.strength.medium'), color: '#f59e0b', strength };
    return { label: t('profile.security.strength.strong'), color: '#22c55e', strength };
  };

  const getRoleLabel = (role: string) => {
    const labels: Record<string, string> = {
      ADMIN: t('role.admin'),
      MANAGER: t('role.manager'),
      USER: t('role.user'),
    };
    return labels[role] || role;
  };

  const formatDate = (dateStr: string | null | undefined) => {
    if (!dateStr) return t('profile.notSet');
    return new Date(dateStr).toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateStr: string | null) => {
    if (!dateStr) return t('profile.notSet');
    return new Date(dateStr).toLocaleDateString('vi-VN', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (isLoading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.spinner} />
        <p>{t('profile.loading')}</p>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <button
          onClick={() => router.push('/')}
          className={styles.backButton}
        >
          <ArrowLeft size={16} />
          {'Quay lại'}
        </button>
        <h1 className={styles.pageTitle}>{t('profile.title')}</h1>
        <p className={styles.pageSubtitle}>{t('profile.subtitle')}</p>
      </div>

      <div className={styles.tabs}>
        {(['profile', 'edit', 'security'] as TabKey[]).map((tab) => (
          <button
            key={tab}
            className={`${styles.tab} ${activeTab === tab ? styles.activeTab : ''}`}
            onClick={() => setActiveTab(tab)}
          >
            {tab === 'profile' && <User size={18} />}
            {tab === 'edit' && <FileText size={18} />}
            {tab === 'security' && <Lock size={18} />}
            {tab === 'profile' && t('profile.tabs.info')}
            {tab === 'edit' && t('profile.tabs.edit')}
            {tab === 'security' && t('profile.tabs.security')}
          </button>
        ))}
      </div>

      <div className={styles.content}>
        {/* ── Tab: Profile Info ── */}
        {activeTab === 'profile' && profile && (
          <div className={styles.profileCard}>
            <div className={styles.avatarSection}>
              <div className={styles.avatar}>
                {profile.fullName ? profile.fullName.charAt(0).toUpperCase() : profile.username.charAt(0).toUpperCase()}
              </div>
              <div className={styles.avatarInfo}>
                <h2 className={styles.username}>{profile.fullName || profile.username}</h2>
                <span className={`${styles.roleBadge} ${styles[profile.role.toLowerCase()]}`}>
                  {getRoleLabel(profile.role)}
                </span>
              </div>
            </div>

            <div className={styles.infoGrid}>
              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><User size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.username')}</span>
                  <span className={styles.infoValue}>{profile.username}</span>
                </div>
              </div>

              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><Mail size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.email')}</span>
                  <span className={styles.infoValue}>{profile.email}</span>
                </div>
              </div>

              {profile.fullName && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><User size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.fullName')}</span>
                    <span className={styles.infoValue}>{profile.fullName}</span>
                  </div>
                </div>
              )}

              {profile.employeeCode && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><Shield size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.employeeCode')}</span>
                    <span className={styles.infoValue}>{profile.employeeCode}</span>
                  </div>
                </div>
              )}

              {profile.position && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><Briefcase size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.position')}</span>
                    <span className={styles.infoValue}>{profile.position}</span>
                  </div>
                </div>
              )}

              {profile.phone && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><Phone size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.phone')}</span>
                    <span className={styles.infoValue}>{profile.phone}</span>
                  </div>
                </div>
              )}

              {profile.bio && (
                <div className={`${styles.infoItem} ${styles.infoItemWide}`}>
                  <div className={styles.infoIcon}><FileText size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.bio')}</span>
                    <span className={styles.infoValue}>{profile.bio}</span>
                  </div>
                </div>
              )}

              {profile.dateOfBirth && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><Calendar size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.dateOfBirth')}</span>
                    <span className={styles.infoValue}>{formatDate(profile.dateOfBirth)}</span>
                  </div>
                </div>
              )}

              {profile.joinedDate && (
                <div className={styles.infoItem}>
                  <div className={styles.infoIcon}><Calendar size={18} /></div>
                  <div className={styles.infoContent}>
                    <span className={styles.infoLabel}>{t('profile.joinedDate')}</span>
                    <span className={styles.infoValue}>{formatDate(profile.joinedDate)}</span>
                  </div>
                </div>
              )}

              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><Shield size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.role')}</span>
                  <span className={styles.infoValue}>{getRoleLabel(profile.role)}</span>
                </div>
              </div>

              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><Building size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.department')}</span>
                  <span className={styles.infoValue}>{profile.departmentName || t('profile.department.none')}</span>
                </div>
              </div>

              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><Calendar size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.createdAt')}</span>
                  <span className={styles.infoValue}>{formatDateTime(profile.createdAt)}</span>
                </div>
              </div>

              <div className={styles.infoItem}>
                <div className={styles.infoIcon}><Lock size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.passwordChanged')}</span>
                  <span className={styles.infoValue}>{formatDateTime(profile.passwordChangedAt)}</span>
                </div>
              </div>

              <div className={`${styles.infoItem} ${styles.infoItemSmall}`}>
                <div className={styles.infoIcon}><Clock size={18} /></div>
                <div className={styles.infoContent}>
                  <span className={styles.infoLabel}>{t('profile.loginHistory')}</span>
                  <button
                    className={styles.textButton}
                    onClick={() => setShowLoginHistory(true)}
                  >
                    {t('profile.viewDetail')}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Tab: Edit Profile ── */}
        {activeTab === 'edit' && (
          <div className={styles.editCard}>
            <div className={styles.editHeader}>
              <h2 className={styles.sectionTitle}>{t('profile.edit.title')}</h2>
              <p className={styles.sectionDescription}>
                {t('profile.edit.description')}
              </p>
            </div>

            {editSuccess && (
              <div className={styles.successMessage}>
                <CheckCircle size={18} />
                <span>{t('profile.edit.success')}</span>
              </div>
            )}
            {editError && (
              <div className={styles.errorMessage}>
                <AlertCircle size={18} />
                <span>{editError}</span>
              </div>
            )}

            <form onSubmit={handleEditSubmit} className={styles.editForm}>
              <div className={styles.formSection}>
                <h3 className={styles.formSectionTitle}>{t('profile.edit.basicInfo')}</h3>
                <div className={styles.formGrid}>
                  <div className={styles.formGroup}>
                    <Input
                      label={t('profile.fullName')}
                      value={editForm.fullName}
                      onChange={(e) => setEditForm({ ...editForm, fullName: e.target.value })}
                      placeholder={t('register.fullName.placeholder')}
                      error={editErrors.fullName}
                      required
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <Input
                      label={t('profile.phone')}
                      type="tel"
                      value={editForm.phone}
                      onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })}
                      placeholder="0912345678"
                      error={editErrors.phone}
                      helperText="7-15 digits, can start with +"
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <Input
                      label={t('profile.position')}
                      value={editForm.position}
                      onChange={(e) => setEditForm({ ...editForm, position: e.target.value })}
                      placeholder="Software Engineer"
                      error={editErrors.position}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <Input
                      label={t('profile.dateOfBirth')}
                      type="date"
                      value={editForm.dateOfBirth}
                      onChange={(e) => setEditForm({ ...editForm, dateOfBirth: e.target.value })}
                      error={editErrors.dateOfBirth}
                    />
                  </div>
                </div>
              </div>

              <div className={styles.formSection}>
                <h3 className={styles.formSectionTitle}>{t('profile.edit.bioSection')}</h3>
                <div className={styles.formGroupFull}>
                  <label className={styles.textareaLabel}>
                    {t('profile.edit.bioLabel')}
                    <span className={styles.charCount}>
                      {editForm.bio.length} / 1000
                    </span>
                  </label>
                  <textarea
                    className={`${styles.textarea} ${editErrors.bio ? styles.textareaError : ''}`}
                    value={editForm.bio}
                    onChange={(e) => setEditForm({ ...editForm, bio: e.target.value })}
                    placeholder={t('profile.edit.bioPlaceholder')}
                    rows={4}
                    maxLength={1000}
                  />
                  {editErrors.bio && (
                    <span className={styles.fieldError}>{editErrors.bio}</span>
                  )}
                </div>
              </div>

              <div className={styles.formActions}>
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    if (profile) {
                      setEditForm({
                        fullName: profile.fullName || '',
                        phone: profile.phone || '',
                        position: profile.position || '',
                        bio: profile.bio || '',
                        dateOfBirth: profile.dateOfBirth || '',
                      });
                    }
                    setEditErrors({});
                    setEditError(null);
                    setEditSuccess(false);
                  }}
                >
                  {t('profile.edit.reset')}
                </Button>
                <Button
                  type="submit"
                  variant="primary"
                  icon={<CheckCircle size={16} />}
                  loading={isSaving}
                  disabled={isSaving}
                >
                  {t('profile.edit.save')}
                </Button>
              </div>
            </form>
          </div>
        )}

        {/* ── Tab: Security ── */}
        {activeTab === 'security' && (
          <div className={styles.securityCard}>
            <h2 className={styles.sectionTitle}>{t('profile.security.changePassword')}</h2>
            <p className={styles.sectionDescription}>
              {t('profile.security.description')}
            </p>

            {passwordSuccess && (
              <div className={styles.successMessage}>
                <CheckCircle size={18} />
                <span>{t('profile.security.success')}</span>
              </div>
            )}
            {passwordError && (
              <div className={styles.errorMessage}>
                <AlertCircle size={18} />
                <span>{passwordError}</span>
              </div>
            )}

            <form onSubmit={handlePasswordChange} className={styles.passwordForm}>
              <Input
                label={t('profile.security.currentPassword')}
                type={showPasswords.old ? 'text' : 'password'}
                value={passwordForm.oldPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, oldPassword: e.target.value })}
                placeholder={t('profile.security.currentPassword.placeholder')}
                required
                autoComplete="current-password"
                rightIcon={
                  <button type="button" onClick={() => setShowPasswords({ ...showPasswords, old: !showPasswords.old })} className={styles.passwordToggle}>
                    {showPasswords.old ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />

              <div className={styles.passwordStrength}>
                {passwordForm.newPassword && (
                  <div className={styles.strengthIndicator}>
                    <div
                      className={styles.strengthBar}
                      style={{
                        width: `${Math.min(100, (getPasswordStrength(passwordForm.newPassword).strength || 0) * 20)}%`,
                        backgroundColor: getPasswordStrength(passwordForm.newPassword).color,
                      }}
                    />
                    <span className={styles.strengthLabel} style={{ color: getPasswordStrength(passwordForm.newPassword).color }}>
                      {getPasswordStrength(passwordForm.newPassword).label}
                    </span>
                  </div>
                )}
              </div>

              <Input
                label={t('profile.security.newPassword')}
                type={showPasswords.new ? 'text' : 'password'}
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, newPassword: e.target.value })}
                placeholder={t('profile.security.newPassword.placeholder')}
                required
                autoComplete="new-password"
                rightIcon={
                  <button type="button" onClick={() => setShowPasswords({ ...showPasswords, new: !showPasswords.new })} className={styles.passwordToggle}>
                    {showPasswords.new ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />

              <Input
                label={t('profile.security.confirmPassword')}
                type={showPasswords.confirm ? 'text' : 'password'}
                value={passwordForm.confirmPassword}
                onChange={(e) => setPasswordForm({ ...passwordForm, confirmPassword: e.target.value })}
                placeholder={t('profile.security.confirmPassword.placeholder')}
                required
                autoComplete="new-password"
                error={
                  passwordForm.confirmPassword && passwordForm.newPassword !== passwordForm.confirmPassword
                    ? t('validation.passwordMismatch')
                    : undefined
                }
                rightIcon={
                  <button type="button" onClick={() => setShowPasswords({ ...showPasswords, confirm: !showPasswords.confirm })} className={styles.passwordToggle}>
                    {showPasswords.confirm ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                }
              />

              <div className={styles.passwordRequirements}>
                <p>{t('profile.security.requirements')}</p>
                <ul>
                  <li className={passwordForm.newPassword.length >= 8 ? styles.met : ''}>{t('profile.security.req.length')}</li>
                  <li className={/[A-Z]/.test(passwordForm.newPassword) ? styles.met : ''}>{t('profile.security.req.uppercase')}</li>
                  <li className={/[a-z]/.test(passwordForm.newPassword) ? styles.met : ''}>{t('profile.security.req.lowercase')}</li>
                  <li className={/[0-9]/.test(passwordForm.newPassword) ? styles.met : ''}>{t('profile.security.req.number')}</li>
                  <li className={/[^a-zA-Z0-9]/.test(passwordForm.newPassword) ? styles.met : ''}>{t('profile.security.req.special')}</li>
                </ul>
              </div>

              <Button
                type="submit"
                variant="primary"
                loading={isChangingPassword}
                disabled={
                  isChangingPassword ||
                  !passwordForm.oldPassword ||
                  !passwordForm.newPassword ||
                  !passwordForm.confirmPassword ||
                  passwordForm.newPassword !== passwordForm.confirmPassword
                }
              >
                {t('profile.security.submit')}
              </Button>
            </form>
          </div>
        )}
      </div>

      <LoginHistoryModal
        open={showLoginHistory}
        onClose={() => setShowLoginHistory(false)}
        userId={profile?.id ?? ''}
      />
    </div>
  );
}
