'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Globe,
  Moon,
  Sun,
  Clock,
  Check,
} from 'lucide-react';
import { Button, Switch, Select } from '@/components/ui';
import { useLanguage } from '@/providers';
import { usePreferencesStore } from '@/store';
import styles from './settings.module.css';

const TIMEZONE_OPTIONS = [
  { value: 'Asia/Ho_Chi_Minh', label: 'Asia/Ho_Chi_Minh (UTC+7)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'UTC', label: 'UTC (UTC+0)' },
];

export default function SettingsPage() {
  const router = useRouter();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const { t, language, setLanguage } = useLanguage();
  const { theme, setTheme } = usePreferencesStore();
  const [localTimezone, setLocalTimezone] = useState('Asia/Ho_Chi_Minh');

  useEffect(() => {
    const tz = localStorage.getItem('timezone');
    if (tz) setLocalTimezone(tz);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    localStorage.setItem('timezone', localTimezone);
    await new Promise((r) => setTimeout(r, 800));
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  return (
    <div className={styles.pageWrapper}>
      <div className={styles.pageHeader}>
        <div className={styles.headerContent}>
          <div className={styles.headerIcon}>
            <Globe size={28} />
          </div>
          <div>
            <h1 className={styles.pageTitle}>{t('settings.title')}</h1>
            <p className={styles.pageSubtitle}>{t('settings.subtitle')}</p>
          </div>
        </div>
      </div>

      <div className={styles.pageBody}>
        {saved && (
          <div className={styles.savedBanner}>
            <Check size={18} />
            <span>{t('settings.saved')}</span>
          </div>
        )}

        <div className={styles.cardsGrid}>
          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon} data-color="purple">
                <Globe size={20} />
              </div>
              <div>
                <h2 className={styles.cardTitle}>Ngôn ngữ</h2>
                <p className={styles.cardDesc}>Chọn ngôn ngữ hiển thị cho giao diện</p>
              </div>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.settingRow}>
                <div className={styles.settingInfo}>
                  <h3>{t('settings.language')}</h3>
                  <p>{t('settings.language.desc')}</p>
                </div>
                <Select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value as 'vi' | 'en')}
                  options={[
                    { value: 'vi', label: t('settings.lang.vi') },
                    { value: 'en', label: t('settings.lang.en') },
                  ]}
                  selectSize="md"
                  className={styles.settingSelect}
                />
              </div>
            </div>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon} data-color="blue">
                <Clock size={20} />
              </div>
              <div>
                <h2 className={styles.cardTitle}>Múi giờ</h2>
                <p className={styles.cardDesc}>Thiết lập múi giờ cho hệ thống</p>
              </div>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.settingRow}>
                <div className={styles.settingInfo}>
                  <h3>{t('settings.timezone')}</h3>
                  <p>{t('settings.timezone.desc')}</p>
                </div>
                <Select
                  value={localTimezone}
                  onChange={(e) => setLocalTimezone(e.target.value)}
                  options={TIMEZONE_OPTIONS}
                  selectSize="md"
                  className={styles.settingSelect}
                />
              </div>
            </div>
          </div>

          <div className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.cardIcon} data-color={theme === 'dark' ? 'yellow' : 'gray'}>
                {theme === 'dark' ? <Moon size={20} /> : <Sun size={20} />}
              </div>
              <div>
                <h2 className={styles.cardTitle}>Giao diện</h2>
                <p className={styles.cardDesc}>Tùy chỉnh giao diện hiển thị</p>
              </div>
            </div>
            <div className={styles.cardContent}>
              <div className={styles.settingRow}>
                <div className={styles.settingInfo}>
                  <h3>{t('settings.darkMode')}</h3>
                  <p>{t('settings.darkMode.desc')}</p>
                </div>
                <div className={styles.themeToggle}>
                  <button
                    className={`${styles.themeOption} ${theme === 'light' ? styles.active : ''}`}
                    onClick={() => setTheme('light')}
                  >
                    <Sun size={18} />
                    <span>Sáng</span>
                  </button>
                  <button
                    className={`${styles.themeOption} ${theme === 'dark' ? styles.active : ''}`}
                    onClick={() => setTheme('dark')}
                  >
                    <Moon size={18} />
                    <span>Tối</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className={styles.actions}>
          <Button
            variant="primary"
            size="lg"
            loading={saving}
            onClick={handleSave}
          >
            {saving ? t('settings.saving') : t('settings.save')}
          </Button>
        </div>
      </div>
    </div>
  );
}
