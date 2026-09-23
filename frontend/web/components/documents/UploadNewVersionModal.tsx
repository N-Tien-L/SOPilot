'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Upload,
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  CloudUpload,
  FileCheck,
  History,
} from 'lucide-react';
import { documentService } from '@/services/document.service';
import type { DocumentVersion } from '@/types/document';
import { formatFileSize } from '@/types/document';
import styles from './UploadModal.module.css';

interface UploadNewVersionModalProps {
  open: boolean;
  documentId: string;
  documentTitle: string;
  currentVersion: number;
  onClose: () => void;
  onSuccess: () => void;
}

type Step = 'SELECT' | 'UPLOAD' | 'COMPLETE' | 'ERROR';

export function UploadNewVersionModal({
  open,
  documentId,
  documentTitle,
  currentVersion,
  onClose,
  onSuccess,
}: UploadNewVersionModalProps) {
  const [step, setStep] = useState<Step>('SELECT');
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [changelog, setChangelog] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [newVersion, setNewVersion] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isClickFromInputRef = useRef(false);

  useEffect(() => {
    if (!open) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [open, onClose]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleFile = (selectedFile: File) => {
    const allowedTypes = [
      'application/pdf',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      'application/msword',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'application/vnd.ms-excel',
      'text/plain',
      'image/png',
      'image/jpeg',
      'text/markdown',
      'text/x-markdown',
    ];
    const ext = selectedFile.name.split('.').pop()?.toLowerCase();
    const allowedExtensions = ['pdf', 'doc', 'docx', 'xls', 'xlsx', 'txt', 'png', 'jpg', 'jpeg', 'md'];

    if (!allowedTypes.includes(selectedFile.type) && !allowedExtensions.includes(ext || '')) {
      setError('Loại file không được hỗ trợ. Vui lòng chọn PDF, Word, Excel, Text, Markdown, hoặc hình ảnh.');
      return;
    }

    const maxSize = 100 * 1024 * 1024;
    if (selectedFile.size > maxSize) {
      setError('Kích thước file vượt quá giới hạn 100MB.');
      return;
    }

    setFile(selectedFile);
    setError(null);
    setStep('UPLOAD');
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    if (!changelog.trim()) {
      setError('Vui lòng nhập mô tả thay đổi (changelog) cho phiên bản mới.');
      return;
    }

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const result = await documentService.uploadNewVersion(
        documentId,
        file,
        changelog.trim(),
        (percent) => setUploadProgress(percent)
      );

      const versionNum: number =
        (result as DocumentVersion | undefined)?.versionNumber ??
        (result as DocumentVersion | undefined)?.version ??
        currentVersion + 1;
      setNewVersion(typeof versionNum === 'number' ? versionNum : currentVersion + 1);
      setUploading(false);
      setStep('COMPLETE');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Tải lên phiên bản mới thất bại. Vui lòng thử lại.';
      setError(message);
      setUploading(false);
    }
  };

  const handleBack = () => {
    if (uploading) return;
    setFile(null);
    setError(null);
    setStep('SELECT');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  const handleFinish = () => {
    onSuccess();
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split('.').pop()?.toLowerCase();
    switch (ext) {
      case 'pdf': return '📄';
      case 'doc':
      case 'docx': return '📝';
      case 'xls':
      case 'xlsx': return '📊';
      case 'txt': return '📃';
      case 'md': return '📋';
      case 'png':
      case 'jpg':
      case 'jpeg': return '🖼️';
      default: return '📁';
    }
  };

  if (!open) return null;

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.headerTitle}>
            <History className="w-4 h-4" style={{ display: 'inline', marginRight: 6, verticalAlign: 'middle' }} />
            Tải lên phiên bản mới
          </h2>
          <button onClick={onClose} className={styles.closeBtn} disabled={uploading}>
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className={styles.content}>
          {step === 'SELECT' && (
            <>
              <div className={styles.successBanner}>
                <div className={styles.successBannerLeft}>
                  <div className={styles.successIcon}>
                    <History className="w-4 h-4" />
                  </div>
                  <span className={styles.successText}>
                    Đang tải lên phiên bản mới cho: <strong>{documentTitle}</strong>
                  </span>
                </div>
                <span className={styles.successFilename}>
                  Hiện tại: v{currentVersion}
                </span>
              </div>

              <div
                className={`${styles.dropzone} ${dragActive ? styles.active : ''}`}
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => {
                  if (!isClickFromInputRef.current) {
                    fileInputRef.current?.click();
                  }
                }}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  className={styles.dropzoneInput}
                  onChange={handleFileChange}
                  onClick={() => {
                    isClickFromInputRef.current = true;
                    setTimeout(() => {
                      isClickFromInputRef.current = false;
                    }, 100);
                  }}
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.md"
                />
                <div className={styles.dropzoneIcon}>
                  <CloudUpload className="w-8 h-8" />
                </div>
                <p className={styles.dropzoneText}>
                  Kéo thả file vào đây hoặc{' '}
                  <span className={styles.dropzoneTextBold}>chọn file</span>
                </p>
                <p className={styles.dropzoneHint}>
                  PDF, Word, Excel, Text, Markdown, hình ảnh (tối đa 100MB)
                </p>
              </div>

              {error && (
                <div className={styles.error} style={{ marginTop: '1rem' }}>
                  <AlertCircle className={`${styles.errorIcon} w-5 h-5`} />
                  <span>{error}</span>
                </div>
              )}
            </>
          )}

          {step === 'UPLOAD' && file && (
            <>
              <div className={styles.uploadPreview}>
                <div className={styles.fileIcon}>{getFileIcon(file.name)}</div>
                <p className={styles.fileName}>{file.name}</p>
                <p className={styles.fileSize}>{formatFileSize(file.size)}</p>

                <div className={styles.field} style={{ marginTop: '1rem', width: '100%' }}>
                  <label className={styles.fieldLabel}>
                    Mô tả thay đổi <span className={styles.required}>*</span>
                  </label>
                  <textarea
                    value={changelog}
                    onChange={(e) => setChangelog(e.target.value)}
                    className={`${styles.fieldInput} ${styles.fieldTextarea}`}
                    placeholder="Mô tả những thay đổi trong phiên bản này (bắt buộc)"
                    rows={3}
                    disabled={uploading}
                  />
                </div>

                <div className={styles.progressContainer} style={{ width: '100%' }}>
                  <div className={styles.uploadProgressBar}>
                    <div
                      className={styles.progressFill}
                      style={{ width: uploading ? `${uploadProgress}%` : '0%' }}
                    />
                  </div>
                  <p className={styles.progressText}>
                    {uploading ? `Đang tải lên... ${uploadProgress}%` : 'Sẵn sàng tải lên'}
                  </p>
                </div>

                {error && (
                  <div className={styles.error} style={{ marginTop: '0.5rem' }}>
                    <AlertCircle className={`${styles.errorIcon} w-5 h-5`} />
                    <span>{error}</span>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 'COMPLETE' && (
            <div className={styles.successScreen}>
              <div className={styles.successScreenIcon}>
                <FileCheck className="w-10 h-10" />
              </div>
              <h3 className={styles.successScreenTitle}>
                Phiên bản mới đã được tạo thành công!
              </h3>
              <p className={styles.successScreenText}>
                Phiên bản v{newVersion ?? currentVersion + 1} của &ldquo;{documentTitle}&rdquo; đã được tải lên.
              </p>

              <div className={styles.docSummaryCard}>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>📄 Tên file</span>
                  <span>{file?.name}</span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>🏷️ Loại</span>
                  <span>
                    {getFileIcon(file?.name || '')} {file?.name.split('.').pop()?.toUpperCase()} —{' '}
                    {formatFileSize(file?.size || 0)}
                  </span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>📌 Phiên bản</span>
                  <span>
                    v{currentVersion} → <strong>v{newVersion ?? currentVersion + 1}</strong>
                  </span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>📝 Mô tả</span>
                  <span>{changelog}</span>
                </div>
              </div>

              <div className={styles.successActions}>
                <button onClick={handleFinish} className={styles.primaryBtn}>
                  <CheckCircle className="w-4 h-4" />
                  Hoàn tất
                </button>
              </div>
            </div>
          )}
        </div>

        {step === 'UPLOAD' && (
          <div className={styles.actions}>
            <button
              onClick={handleBack}
              className={styles.backBtn}
              disabled={uploading}
            >
              Quay lại
            </button>
            <button
              onClick={handleUpload}
              disabled={uploading || !changelog.trim()}
              className={styles.primaryBtn}
            >
              {uploading ? (
                <>
                  <Loader2 className={`${styles.spinner} w-4 h-4`} />
                  Đang tải lên...
                </>
              ) : (
                <>
                  <Upload className="w-4 h-4" />
                  Tải lên phiên bản mới
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
