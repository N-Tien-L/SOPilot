'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Upload,
  X,
  Loader2,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  ChevronLeft,
  CloudUpload,
  FileCheck,
  FileSearch,
  FileText,
} from 'lucide-react';
import {
  documentService,
} from '@/services/document.service';
import { api } from '@/lib/api';
import { computeFileChecksum } from '@/lib/crypto';
import type {
  DocumentUploadResponse,
  Category,
  DuplicateCheckResponse,
  ConfirmResultResponse,
} from '@/types/document';
import { formatFileSize, formatDate } from '@/types/document';
import styles from './UploadModal.module.css';

interface UploadModalProps {
  onClose: () => void;
  onSuccess: () => void;
  categories: Category[];
  initialDocument?: DocumentUploadResponse | any;
}

const STEPS = {
  SELECT: 1,
  UPLOAD: 2,
  METADATA: 3,
  DUPLICATE_WARNING: 4,
  NEAR_DUPLICATE: 5,
  COMPLETE: 6,
} as const;

type UploadStep = typeof STEPS[keyof typeof STEPS];

const HIDE_PROGRESS_STEPS: UploadStep[] = [
  STEPS.COMPLETE,
  STEPS.DUPLICATE_WARNING,
  STEPS.NEAR_DUPLICATE,
];

const STEP_LABELS = [
  'Chọn file',
  'Đang tải',
  'Xác nhận',
  'Cảnh báo trùng lặp',
  'Tài liệu tương tự',
  'Hoàn thành',
];

export function UploadModal({ onClose, onSuccess, categories, initialDocument }: UploadModalProps) {
  const [step, setStep] = useState<UploadStep>(initialDocument ? STEPS.METADATA : STEPS.SELECT);
  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadedDocument, setUploadedDocument] = useState<DocumentUploadResponse | null>(initialDocument || null);
  const [error, setError] = useState<string | null>(null);

  // New states for deduplication
  const [checksum, setChecksum] = useState<string | null>(null);
  const [duplicateCheck, setDuplicateCheck] = useState<DuplicateCheckResponse | null>(null);
  const [showDuplicateWarning, setShowDuplicateWarning] = useState(false);
  const [nearDuplicateInfo, setNearDuplicateInfo] = useState<ConfirmResultResponse | null>(null);
  const [processingStatus, setProcessingStatus] = useState<string | null>(null);
  const [selectedAction, setSelectedAction] = useState<'CREATE_NEW' | 'CREATE_VERSION' | null>(null);
  const [processing, setProcessing] = useState(false);

  const [formData, setFormData] = useState({
    title: initialDocument?.title || initialDocument?.suggestedTitle || initialDocument?.originalFilename?.replace(/\.[^/.]+$/, '') || '',
    description: initialDocument?.description || initialDocument?.suggestedDescription || '',
    categorySlug: initialDocument?.categorySlug || initialDocument?.suggestedCategorySlug || '',
    tags: initialDocument?.tags || initialDocument?.suggestedTags || [] as string[],
    language: initialDocument?.language || initialDocument?.suggestedLanguage || 'vi',
    isPolicy: initialDocument?.isPolicy || initialDocument?.suggestedIsPolicy || false,
  });
  const [tagInput, setTagInput] = useState('');
  const [confirming, setConfirming] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const isClickFromInputRef = useRef(false);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', handleEsc);
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', handleEsc);
      document.body.style.overflow = '';
    };
  }, [onClose]);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    // Stop propagation to prevent the dropzone's onClick from triggering again
    e.stopPropagation();
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleFile = async (selectedFile: File) => {
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
    setShowDuplicateWarning(false);
    setDuplicateCheck(null);

    // Compute checksum client-side
    let computedChecksum: string | null = null;
    try {
      computedChecksum = await computeFileChecksum(selectedFile);
      setChecksum(computedChecksum);

      // Pre-check duplicate BEFORE allowing upload (Layer 1 only via frontend)
      if (computedChecksum) {
        try {
          const dup = await documentService.checkDuplicate(computedChecksum);
          setDuplicateCheck(dup);
          if (dup.isDuplicate && dup.action === 'BLOCK') {
            setShowDuplicateWarning(true);
            setStep(STEPS.DUPLICATE_WARNING); // block upload - stay at SELECT
            return;
          }
        } catch (err) {
          console.warn('Check duplicate failed:', err);
          // fall through — allow upload if check fails
        }
      }
    } catch (err) {
      console.warn('Failed to compute file checksum:', err);
    }

    setStep(STEPS.UPLOAD); // only reached if no duplicate found
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      const response = await documentService.uploadDocument(file, (percent) => {
        setUploadProgress(percent);
      });

      setUploadedDocument(response);
      setFormData({
        ...formData,
        title: response.suggestedTitle || file.name.replace(/\.[^/.]+$/, ''),
        description: response.suggestedDescription || '',
        categorySlug: response.suggestedCategorySlug || '',
        tags: response.suggestedTags || [],
        language: response.suggestedLanguage || 'vi',
        isPolicy: response.suggestedIsPolicy || false,
      });

      setStep(STEPS.METADATA);
    } catch (err: any) {
      setError(err.message || 'Tải lên thất bại. Vui lòng thử lại.');
    } finally {
      setUploading(false);
    }
  };

  const handleConfirm = async () => {
    if (!uploadedDocument) return;

    setConfirming(true);
    setError(null);
    setProcessingStatus('Đang xác nhận và xử lý tài liệu...');

    try {
      const result = await documentService.confirmMetadataSync(uploadedDocument.id, {
        title: formData.title,
        description: formData.description,
        categorySlug: formData.categorySlug,
        tags: formData.tags,
        language: formData.language,
        isPolicy: formData.isPolicy,
        fileChecksum: checksum || undefined,
      });

      if (result.status === 'DUPLICATE') {
        setShowDuplicateWarning(true);
        setDuplicateCheck({
          isDuplicate: true,
          action: 'BLOCK',
          existingDocument: result.nearDuplicateOf,
          similarity: result.similarity,
          detectionMethod: 'ingestion_pipeline',
        });
        setStep(STEPS.DUPLICATE_WARNING);
        setProcessingStatus(null);
        return;
      }

      if (result.status === 'NEAR_DUPLICATE') {
        setNearDuplicateInfo(result);
        setSelectedAction(null);
        setStep(STEPS.NEAR_DUPLICATE);
        setProcessingStatus(null);
        return;
      }

      // result.status === 'READY'
      setProcessingStatus(null);
      setStep(STEPS.COMPLETE);
      // Note: Do NOT call onSuccess() here - let user see the success screen first
    } catch (err: unknown) {
      const anyErr = err as { status?: number; response?: { data?: { code?: string; message?: string } }; message?: string };
      if (anyErr.status === 409 || anyErr.response?.data?.code === 'DUPLICATE') {
        const errorData = (err as any)?.response?.data;
        setShowDuplicateWarning(true);
        setDuplicateCheck({
          isDuplicate: true,
          action: 'BLOCK',
          existingDocument: errorData?.existingDocument || null,
          similarity: null,
          detectionMethod: errorData?.detectionMethod || 'unknown',
        });
        setStep(STEPS.DUPLICATE_WARNING);
      } else {
        setError(anyErr.message || 'Có lỗi xảy ra khi xác nhận metadata.');
      }
      setProcessingStatus(null);
    } finally {
      setConfirming(false);
    }
  };

  const handleNearDuplicateAction = async () => {
    if (!selectedAction || !nearDuplicateInfo) return;
    setProcessing(true);

    try {
      if (selectedAction === 'CREATE_VERSION' && nearDuplicateInfo.nearDuplicateOf) {
        // Call uploadNewVersion on the existing document
        await documentService.uploadNewVersion(
          nearDuplicateInfo.nearDuplicateOf.documentId,
          file!,
          `Auto-uploaded version via upload flow (${new Date().toISOString()})`
        );

        // Clean up the orphan STAGING document created during handleUpload
        if (uploadedDocument?.id && uploadedDocument.id !== nearDuplicateInfo.nearDuplicateOf.documentId) {
          try {
            await documentService.deleteDocument(uploadedDocument.id);
          } catch (cleanupErr) {
            console.warn('Failed to clean up staging document:', cleanupErr);
          }
        }

        setProcessing(false);
        setStep(STEPS.COMPLETE);
        // Note: Do NOT call onSuccess() here - let user see the success screen first
      } else {
        // CREATE_NEW: just show success (already ingested)
        setProcessing(false);
        setStep(STEPS.COMPLETE);
        // Note: Do NOT call onSuccess() here - let user see the success screen first
      }
    } catch (err: any) {
      setError(err.message || 'Có lỗi xảy ra khi xử lý tài liệu.');
      setProcessing(false);
    }
  };

  const handleAddTag = () => {
    if (tagInput.trim() && !formData.tags.includes(tagInput.trim())) {
      setFormData({
        ...formData,
        tags: [...formData.tags, tagInput.trim()],
      });
      setTagInput('');
    }
  };

  const handleRemoveTag = (tag: string) => {
    setFormData({
      ...formData,
      tags: formData.tags.filter((t: string) => t !== tag),
    });
  };

  const handleCancelNearDuplicate = async () => {
    // Delete the staging document before closing
    if (uploadedDocument?.id) {
      try {
        await documentService.deleteDocument(uploadedDocument.id);
      } catch (err) {
        console.warn('Failed to delete staging document:', err);
      }
    }
    onClose();
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

  const renderProgressSteps = () => {
    // Only show relevant steps based on current state
    const totalSteps = step >= STEPS.NEAR_DUPLICATE ? 6 : (step >= STEPS.DUPLICATE_WARNING ? 5 : 4);
    const currentLabelIndex = Math.min(step - 1, STEP_LABELS.length - 1);

    return (
      <div className={styles.progressBar}>
        <div className={styles.stepsContainer}>
          {STEP_LABELS.slice(0, totalSteps).map((label, idx) => {
            const stepNum = idx + 1;
            const isCompleted = step > stepNum;
            const isActive = step === stepNum;

            return (
              <React.Fragment key={stepNum}>
                <div className={styles.step}>
                  <div
                    className={`${styles.stepDot} ${
                      isCompleted ? styles.completed :
                      isActive ? styles.active :
                      styles.pending
                    }`}
                  >
                    {isCompleted ? <CheckCircle className="w-4 h-4" /> : stepNum}
                  </div>
                  <span
                    className={`${styles.stepLabel} ${
                      isCompleted ? styles.completed :
                      isActive ? styles.active :
                      styles.pending
                    }`}
                  >
                    {label}
                  </span>
                </div>
                {stepNum < totalSteps && (
                  <div className={`${styles.stepConnector} ${isCompleted ? styles.completed : ''}`}>
                    {isCompleted && <div className={styles.stepConnectorFill} style={{ width: '100%' }} />}
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.headerTitle}>Tải lên tài liệu</h2>
          <button onClick={onClose} className={styles.closeBtn}>
            <X className="w-5 h-5" />
          </button>
        </div>

        {!HIDE_PROGRESS_STEPS.includes(step) && renderProgressSteps()}

        <div className={styles.content}>
          {/* Step 1: Select File */}
          {step === STEPS.SELECT && (
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
                  // Reset after a tick so next dropzone click doesn't get false positive
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
          )}

          {/* Step 2: Upload */}
          {step === STEPS.UPLOAD && file && (
            <div className={styles.uploadPreview}>
              <div className={styles.fileIcon}>
                {getFileIcon(file.name)}
              </div>
              <p className={styles.fileName}>{file.name}</p>
              <p className={styles.fileSize}>{formatFileSize(file.size)}</p>

              <div className={styles.progressContainer}>
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

              <button
                onClick={handleUpload}
                disabled={uploading}
                className={styles.uploadBtn}
              >
                {uploading ? (
                  <>
                    <Loader2 className={`${styles.spinner} w-5 h-5`} />
                    Đang tải lên...
                  </>
                ) : (
                  <>
                    <Upload className="w-5 h-5" />
                    Bắt đầu tải lên
                  </>
                )}
              </button>
            </div>
          )}

          {/* Step 3: Metadata Form */}
          {step === STEPS.METADATA && uploadedDocument && (
            <div className={styles.form}>
              {error && (
                <div className={styles.error}>
                  <AlertCircle className={`${styles.errorIcon} w-5 h-5`} />
                  <span>{error}</span>
                </div>
              )}

              {/* Duplicate Warning Panel */}
              {showDuplicateWarning && duplicateCheck?.existingDocument && (
                <div className={styles.duplicateWarningPanel}>
                  <div className={styles.warningHeader}>
                    <AlertTriangle className="w-5 h-5" />
                    <span>Phát hiện tài liệu trùng lặp</span>
                  </div>
                  <p className={styles.warningMessage}>
                    File bạn đang tải lên giống hệt tài liệu đã có trong hệ thống.
                    Hệ thống sẽ không tạo tài liệu mới.
                  </p>
                  <div className={styles.existingDocCard}>
                    <div className={styles.docCardRow}>
                      <span className={styles.docCardLabel}>Tên file</span>
                      <span>{duplicateCheck.existingDocument.originalFilename}</span>
                    </div>
                    <div className={styles.docCardRow}>
                      <span className={styles.docCardLabel}>Kích thước</span>
                      <span>{formatFileSize(duplicateCheck.existingDocument.fileSizeBytes)}</span>
                    </div>
                    <div className={styles.docCardRow}>
                      <span className={styles.docCardLabel}>Ngày tạo</span>
                      <span>{formatDate(duplicateCheck.existingDocument.createdAt)}</span>
                    </div>
                    {duplicateCheck.existingDocument.title && (
                      <div className={styles.docCardRow}>
                        <span className={styles.docCardLabel}>Tiêu đề</span>
                        <span>{duplicateCheck.existingDocument.title}</span>
                      </div>
                    )}
                  </div>
                  <div className={styles.warningActions}>
                    <button onClick={onClose} className={styles.cancelBtn}>
                      Hủy bỏ
                    </button>
                    <button
                      onClick={() => {
                        setShowDuplicateWarning(false);
                        setDuplicateCheck(null);
                        setChecksum(null);
                        setFile(null);
                        setUploadedDocument(null);
                        if (fileInputRef.current) fileInputRef.current.value = ''; // clear file input
                        setStep(STEPS.SELECT);
                      }}
                      className={styles.secondaryBtn}
                    >
                      Chọn file khác
                    </button>
                  </div>
                </div>
              )}

              {!showDuplicateWarning && (
                <>
                  <div className={styles.successBanner}>
                    <div className={styles.successBannerLeft}>
                      <div className={styles.successIcon}>
                        <CheckCircle className="w-4 h-4" />
                      </div>
                      <span className={styles.successText}>Tải lên thành công!</span>
                    </div>
                    <span className={styles.successFilename}>
                      {getFileIcon(file?.name || '')} {file?.name}
                    </span>
                  </div>

                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>
                      Tiêu đề <span className={styles.required}>*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.title}
                      onChange={(e) => setFormData({ ...formData, title: e.target.value })}
                      className={styles.fieldInput}
                      placeholder="Nhập tiêu đề tài liệu"
                    />
                  </div>

                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Mô tả</label>
                    <textarea
                      value={formData.description}
                      onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                      className={`${styles.fieldInput} ${styles.fieldTextarea}`}
                      placeholder="Nhập mô tả tài liệu"
                      rows={3}
                    />
                  </div>

                  <div className={styles.fieldRow}>
                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Danh mục</label>
                      <select
                        value={formData.categorySlug}
                        onChange={(e) => setFormData({ ...formData, categorySlug: e.target.value })}
                        className={`${styles.fieldInput} ${styles.fieldSelect}`}
                      >
                        <option value="">Chọn danh mục</option>
                        {categories.map((cat) => (
                          <option key={cat.id} value={cat.slug}>
                            {cat.name}
                          </option>
                        ))}
                      </select>
                    </div>

                    <div className={styles.field}>
                      <label className={styles.fieldLabel}>Ngôn ngữ</label>
                      <select
                        value={formData.language}
                        onChange={(e) => setFormData({ ...formData, language: e.target.value })}
                        className={`${styles.fieldInput} ${styles.fieldSelect}`}
                      >
                        <option value="vi">Tiếng Việt</option>
                        <option value="en">Tiếng Anh</option>
                      </select>
                    </div>
                  </div>

                  <div className={styles.field}>
                    <label className={styles.fieldLabel}>Tags</label>
                    <div className={styles.tagsContainer}>
                      {formData.tags.map((tag: string) => (
                        <span key={tag} className={styles.tag}>
                          {tag}
                          <button
                            type="button"
                            onClick={() => handleRemoveTag(tag)}
                            className={styles.tagRemove}
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </span>
                      ))}
                      <input
                        type="text"
                        value={tagInput}
                        onChange={(e) => setTagInput(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddTag();
                          }
                        }}
                        className={styles.tagInput}
                        placeholder={formData.tags.length === 0 ? 'Nhập tag và nhấn Enter' : ''}
                      />
                    </div>
                  </div>

                  <div className={`${styles.field} ${styles.checkboxField}`}>
                    <input
                      type="checkbox"
                      id="isPolicy"
                      checked={formData.isPolicy}
                      onChange={(e) => setFormData({ ...formData, isPolicy: e.target.checked })}
                      className={styles.checkbox}
                    />
                    <label htmlFor="isPolicy" className={styles.checkboxLabel}>
                      Đây là tài liệu chính sách
                    </label>
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 4: Duplicate Warning (Full Screen) */}
          {step === STEPS.DUPLICATE_WARNING && (
            <div className={styles.duplicateWarningPanel}>
              <div className={styles.warningHeader}>
                <AlertTriangle className="w-5 h-5" />
                <span>Tài liệu trùng lặp</span>
              </div>
              <p className={styles.warningMessage}>
                Tài liệu bạn đang tải lên gần như trùng lặp với tài liệu đã có trong hệ thống
                {duplicateCheck?.existingDocument?.originalFilename && (
                  <> (<strong>{duplicateCheck.existingDocument.originalFilename}</strong>)</>
                )}.
                Hệ thống sẽ không tạo tài liệu mới.
              </p>
              {duplicateCheck?.existingDocument ? (
                <div className={styles.existingDocCard}>
                  <div className={styles.docCardRow}>
                    <span className={styles.docCardLabel}>Tên file</span>
                    <span>{duplicateCheck.existingDocument.originalFilename}</span>
                  </div>
                  <div className={styles.docCardRow}>
                    <span className={styles.docCardLabel}>Kích thước</span>
                    <span>{formatFileSize(duplicateCheck.existingDocument.fileSizeBytes)}</span>
                  </div>
                  <div className={styles.docCardRow}>
                    <span className={styles.docCardLabel}>Ngày tạo</span>
                    <span>{formatDate(duplicateCheck.existingDocument.createdAt)}</span>
                  </div>
                  {duplicateCheck.existingDocument.title && (
                    <div className={styles.docCardRow}>
                      <span className={styles.docCardLabel}>Tiêu đề</span>
                      <span>{duplicateCheck.existingDocument.title}</span>
                    </div>
                  )}
                </div>
              ) : (
                <div className={styles.warningFallback}>
                  <p>Không tìm thấy thông tin tài liệu trùng lặp.</p>
                </div>
              )}
              <div className={styles.warningActions}>
                <button onClick={onClose} className={styles.cancelBtn}>
                  Đóng
                </button>
                <button
                  onClick={() => {
                    setShowDuplicateWarning(false);
                    setDuplicateCheck(null);
                    setChecksum(null);
                    setFile(null);
                    setUploadedDocument(null);
                    if (fileInputRef.current) fileInputRef.current.value = '';
                    setStep(STEPS.SELECT);
                  }}
                  className={styles.secondaryBtn}
                >
                  Chọn file khác
                </button>
              </div>
            </div>
          )}

          {/* Step 5: Near Duplicate Action Selector */}
          {step === STEPS.NEAR_DUPLICATE && nearDuplicateInfo && (
            <div className={styles.nearDuplicatePanel}>
              <div className={styles.nearDuplicateHeader}>
                <FileSearch className="w-6 h-6" />
                <div>
                  <h3>Tài liệu tương tự được phát hiện</h3>
                  <p>
                    File của bạn có <strong>{Math.round((nearDuplicateInfo.similarity || 0) * 100)}%</strong> tương đồng
                    với tài liệu đã có trong hệ thống.
                  </p>
                </div>
              </div>

              <div className={styles.comparisonCards}>
                <div className={styles.comparisonCard}>
                  <span className={styles.comparisonCardLabel}>Tài liệu hiện có</span>
                  <div className={styles.comparisonCardContent}>
                    <div>{getFileIcon(nearDuplicateInfo.nearDuplicateOf?.originalFilename || '')} {nearDuplicateInfo.nearDuplicateOf?.originalFilename}</div>
                    <div className={styles.comparisonCardMeta}>
                      v{nearDuplicateInfo.nearDuplicateOf?.status} •{' '}
                      {formatFileSize(nearDuplicateInfo.nearDuplicateOf?.fileSizeBytes || 0)}
                    </div>
                  </div>
                </div>

                <div className={styles.comparisonCard}>
                  <span className={styles.comparisonCardLabel}>File của bạn</span>
                  <div className={styles.comparisonCardContent}>
                    <div>{getFileIcon(file?.name || '')} {file?.name}</div>
                    <div className={styles.comparisonCardMeta}>
                      {formatFileSize(file?.size || 0)}
                    </div>
                  </div>
                </div>
              </div>

              <div className={styles.actionSelector}>
                <p className={styles.actionSelectorTitle}>Bạn muốn xử lý thế nào?</p>

                <label className={`${styles.radioOption} ${selectedAction === 'CREATE_NEW' ? styles.selected : ''}`}>
                  <input
                    type="radio"
                    name="uploadAction"
                    value="CREATE_NEW"
                    checked={selectedAction === 'CREATE_NEW'}
                    onChange={() => setSelectedAction('CREATE_NEW')}
                  />
                  <div>
                    <strong>Tạo tài liệu mới (độc lập)</strong>
                    <p>Tải file này như một tài liệu hoàn toàn mới, không liên kết với tài liệu hiện có.</p>
                  </div>
                </label>

                <label className={`${styles.radioOption} ${selectedAction === 'CREATE_VERSION' ? styles.selected : ''}`}>
                  <input
                    type="radio"
                    name="uploadAction"
                    value="CREATE_VERSION"
                    checked={selectedAction === 'CREATE_VERSION'}
                    onChange={() => setSelectedAction('CREATE_VERSION')}
                  />
                  <div>
                    <strong>Upload như phiên bản mới</strong>
                    <p>Tài liệu mới sẽ trở thành phiên bản tiếp theo của tài liệu hiện có.</p>
                  </div>
                </label>
              </div>

              <div className={styles.nearDuplicateActions}>
                <button onClick={handleCancelNearDuplicate} className={styles.cancelBtn}>
                  Hủy bỏ
                </button>
                <button
                  onClick={handleNearDuplicateAction}
                  disabled={!selectedAction || processing}
                  className={styles.primaryBtn}
                >
                  {processing ? (
                    <>
                      <Loader2 className={`${styles.spinner} w-4 h-4`} />
                      Đang xử lý...
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-4 h-4" />
                      Xác nhận
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Step 6: Complete */}
          {step === STEPS.COMPLETE && (
            <div className={styles.successScreen}>
              <div className={styles.successScreenIcon}>
                <FileCheck className="w-10 h-10" />
              </div>
              <h3 className={styles.successScreenTitle}>Tài liệu đã được lưu thành công!</h3>
              <p className={styles.successScreenText}>
                Tài liệu "{formData.title}" đã được xử lý và sẵn sàng sử dụng.
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
                  <span className={styles.summaryLabel}>📁 Danh mục</span>
                  <span>{formData.categorySlug || '—'}</span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>🏷️ Tags</span>
                  <span>{formData.tags.join(', ') || '—'}</span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>🌍 Ngôn ngữ</span>
                  <span>{formData.language === 'vi' ? 'Tiếng Việt' : 'Tiếng Anh'}</span>
                </div>
                <div className={styles.summaryRow}>
                  <span className={styles.summaryLabel}>📌 Trạng thái</span>
                  <span className={styles.statusReady}>✓ Sẵn sàng sử dụng</span>
                </div>
              </div>

              <div className={styles.successActions}>
                <button
                  onClick={() => {
                    if (uploadedDocument?.id) {
                      window.location.href = `/documents/${uploadedDocument.id}`;
                    } else {
                      handleFinish();
                    }
                  }}
                  className={styles.primaryBtn}
                >
                  <FileText className="w-4 h-4" />
                  Mở tài liệu
                </button>
                <button onClick={handleFinish} className={styles.secondaryBtn}>
                  Tải thêm tài liệu khác
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons */}
        {step === STEPS.METADATA && !showDuplicateWarning && (
          <div className={styles.actions}>
            {!initialDocument && (
              <button
                onClick={() => setStep(STEPS.UPLOAD)}
                className={styles.backBtn}
              >
                <ChevronLeft className="w-4 h-4" />
                Quay lại
              </button>
            )}
            <button
              onClick={handleConfirm}
              disabled={confirming || !formData.title.trim()}
              className={styles.primaryBtn}
            >
              {confirming ? (
                <>
                  <Loader2 className={`${styles.spinner} w-4 h-4`} />
                  {processingStatus || 'Đang xác nhận...'}
                </>
              ) : (
                <>
                  <CheckCircle className="w-4 h-4" />
                  Xác nhận và lưu
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
