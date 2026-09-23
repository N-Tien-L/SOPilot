'use client';

import React, { useState, useRef } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Mail,
  ArrowLeft,
  ArrowRight,
  CheckCircle,
  MessageSquare,
  Shield,
  Loader2,
  KeyRound,
} from 'lucide-react';
import { Button, Input } from '@/components/ui';
import { api } from '@/lib/api';
import { useLanguage } from '@/providers';
import styles from './forgot-password.module.css';

type Step = 'email' | 'otp' | 'reset';

interface FormError {
  message: string;
}

export default function ForgotPasswordPage() {
  const router = useRouter();
  const { t } = useLanguage();

  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [otp, setOtp] = useState('');
  const [otpDigits, setOtpDigits] = useState(['', '', '', '', '', '']);
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<FormError | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [resetToken, setResetToken] = useState<string | null>(null);
  const otpRefs = useRef<(HTMLInputElement | null)[]>([]);

  const handleSendOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      await api.auth.sendOtp(email);
      setStep('otp');
      setCountdown(60);
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setError({
        message: axiosError.response?.data?.error?.message || axiosError.message || 'Đã xảy ra lỗi',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleOtpChange = (index: number, value: string) => {
    if (value.length > 1) {
      const digits = value.replace(/\D/g, '').slice(0, 6).split('');
      const newDigits = [...otpDigits];
      digits.forEach((digit, i) => {
        if (index + i < 6) {
          newDigits[index + i] = digit;
        }
      });
      setOtpDigits(newDigits);
      setOtp(newDigits.join(''));

      const nextIndex = Math.min(index + digits.length, 5);
      otpRefs.current[nextIndex]?.focus();
      return;
    }

    if (!/^\d*$/.test(value)) return;

    const newDigits = [...otpDigits];
    newDigits[index] = value;
    setOtpDigits(newDigits);
    setOtp(newDigits.join(''));

    if (value && index < 5) {
      otpRefs.current[index + 1]?.focus();
    }
  };

  const handleOtpKeyDown = (index: number, e: React.KeyboardEvent) => {
    if (e.key === 'Backspace' && !otpDigits[index] && index > 0) {
      otpRefs.current[index - 1]?.focus();
    }
  };

  const handleOtpPaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    const newDigits = [...otpDigits];
    pasted.split('').forEach((digit, i) => {
      newDigits[i] = digit;
    });
    setOtpDigits(newDigits);
    setOtp(newDigits.join(''));
  };

  const handleVerifyOtp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length !== 6) {
      setError({ message: 'Vui lòng nhập đầy đủ 6 số OTP' });
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      const result = await api.auth.verifyOtp(email, otp);
      if (result.valid) {
        setResetToken(result.resetToken || null);
        setStep('reset');
      } else {
        setError({ message: 'Mã OTP không hợp lệ hoặc đã hết hạn' });
      }
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setError({
        message: axiosError.response?.data?.error?.message || axiosError.message || 'Mã OTP không hợp lệ',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleResendOtp = async () => {
    if (countdown > 0) return;
    setIsLoading(true);
    setError(null);

    try {
      await api.auth.sendOtp(email);
      setCountdown(60);
      setOtpDigits(['', '', '', '', '', '']);
      setOtp('');
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setError({
        message: axiosError.response?.data?.error?.message || axiosError.message || 'Đã xảy ra lỗi',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    if (newPassword !== confirmPassword) {
      setError({ message: 'Mật khẩu xác nhận không khớp' });
      return;
    }

    if (newPassword.length < 8) {
      setError({ message: 'Mật khẩu phải có ít nhất 8 ký tự' });
      return;
    }

    setError(null);
    setIsLoading(true);

    try {
      await api.auth.resetPasswordWithOtp({
        email,
        otp,
        resetToken: resetToken || undefined,
        newPassword,
        confirmPassword,
      });
      setStep('email');
      setEmail('');
      setOtp('');
      setOtpDigits(['', '', '', '', '', '']);
      setNewPassword('');
      setConfirmPassword('');
      router.push('/login?reset=success');
    } catch (err: unknown) {
      const axiosError = err as { response?: { data?: { error?: { message?: string } } }; message?: string };
      setError({
        message: axiosError.response?.data?.error?.message || axiosError.message || 'Đã xảy ra lỗi',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const renderStepIndicator = () => {
    const steps = [
      { key: 'email', label: 'Email', icon: Mail },
      { key: 'otp', label: 'Mã OTP', icon: Shield },
      { key: 'reset', label: 'Mật khẩu', icon: KeyRound },
    ];
    const currentIndex = steps.findIndex(s => s.key === step);

    return (
      <div className={styles.stepsIndicator}>
        {steps.map((s, idx) => {
          const Icon = s.icon;
          const isActive = idx === currentIndex;
          const isCompleted = idx < currentIndex;

          return (
            <React.Fragment key={s.key}>
              <div className={`${styles.step} ${isActive ? styles.active : ''} ${isCompleted ? styles.completed : ''}`}>
                <div className={styles.stepIcon}>
                  {isCompleted ? <CheckCircle size={18} /> : <Icon size={18} />}
                </div>
                <span className={styles.stepLabel}>{s.label}</span>
              </div>
              {idx < steps.length - 1 && (
                <div className={`${styles.stepLine} ${isCompleted ? styles.completed : ''}`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    );
  };

  return (
    <div className={styles.container}>
      <div className={styles.formContainer}>
        <div className={styles.formWrapper}>
          <div className={styles.header}>
            <Link href="/login" className={styles.backLink}>
              <ArrowLeft size={18} />
              <span>Quay lại đăng nhập</span>
            </Link>

            <div className={styles.logoWrapper}>
              <div className={styles.logoGlow} />
              <div className={styles.logo}>
                <MessageSquare size={28} />
              </div>
            </div>
            <h1 className={styles.title}>Đặt lại mật khẩu</h1>
            <p className={styles.subtitle}>
              {step === 'email' && 'Nhập địa chỉ email đã đăng ký để nhận mã xác thực'}
              {step === 'otp' && `Nhập mã OTP đã gửi đến ${email}`}
              {step === 'reset' && 'Nhập mật khẩu mới của bạn'}
            </p>
          </div>

          {renderStepIndicator()}

          {error && (
            <div className={styles.error}>
              <Shield size={18} />
              <span>{error.message}</span>
            </div>
          )}

          {step === 'email' && (
            <form onSubmit={handleSendOtp} className={styles.form}>
              <Input
                label="Địa chỉ email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Nhập email của bạn"
                required
                autoComplete="email"
                leftIcon={<Mail size={18} />}
                autoFocus
              />

              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                loading={isLoading}
                disabled={isLoading || !email.trim()}
              >
                {isLoading ? 'Đang gửi...' : 'Gửi mã xác thực'}
              </Button>
            </form>
          )}

          {step === 'otp' && (
            <form onSubmit={handleVerifyOtp} className={styles.form}>
              <div className={styles.otpContainer}>
                <p className={styles.otpHint}>Nhập mã 6 số</p>
                <div className={styles.otpInputs} onPaste={handleOtpPaste}>
                  {otpDigits.map((digit, idx) => (
                    <input
                      key={idx}
                      ref={(el) => { otpRefs.current[idx] = el; }}
                      type="text"
                      inputMode="numeric"
                      pattern="[0-9]"
                      maxLength={6}
                      value={digit}
                      onChange={(e) => handleOtpChange(idx, e.target.value)}
                      onKeyDown={(e) => handleOtpKeyDown(idx, e)}
                      className={styles.otpInput}
                      autoFocus={idx === 0}
                    />
                  ))}
                </div>
              </div>

              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                loading={isLoading}
                disabled={isLoading || otp.length !== 6}
              >
                Xác thực OTP
              </Button>

              <div className={styles.resendRow}>
                <span className={styles.resendText}>
                  {countdown > 0 ? (
                    <>Gửi lại mã sau <strong>{countdown}s</strong></>
                  ) : (
                    'Không nhận được mã?'
                  )}
                </span>
                <button
                  type="button"
                  onClick={handleResendOtp}
                  disabled={countdown > 0 || isLoading}
                  className={styles.resendBtn}
                >
                  Gửi lại mã
                </button>
              </div>
            </form>
          )}

          {step === 'reset' && (
            <form onSubmit={handleResetPassword} className={styles.form}>
              <div className={styles.passwordField}>
                <Input
                  label="Mật khẩu mới"
                  type={showPassword ? 'text' : 'password'}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Ít nhất 8 ký tự"
                  required
                  autoComplete="new-password"
                  rightIcon={
                    <button type="button" onClick={() => setShowPassword(!showPassword)} className={styles.togglePassword}>
                      {showPassword ? 'Ẩn' : 'Hiện'}
                    </button>
                  }
                />
              </div>

              <div className={styles.passwordField}>
                <Input
                  label="Xác nhận mật khẩu"
                  type={showConfirm ? 'text' : 'password'}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Nhập lại mật khẩu"
                  required
                  autoComplete="new-password"
                  rightIcon={
                    <button type="button" onClick={() => setShowConfirm(!showConfirm)} className={styles.togglePassword}>
                      {showConfirm ? 'Ẩn' : 'Hiện'}
                    </button>
                  }
                />
              </div>

              <Button
                type="submit"
                variant="primary"
                size="lg"
                fullWidth
                loading={isLoading}
                disabled={isLoading || !newPassword || !confirmPassword}
              >
                Đặt lại mật khẩu
              </Button>
            </form>
          )}

          <p className={styles.footer}>
            <Link href="/login" className={styles.loginLink}>
              Quay lại đăng nhập
            </Link>
          </p>
        </div>
      </div>

      <div className={styles.background}>
        <div className={styles.gradient} />
        <div className={styles.pattern} />
      </div>
    </div>
  );
}
