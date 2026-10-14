'use client';

import React, { useState, useCallback } from 'react';
import { Upload, X, FileSpreadsheet, CheckCircle2, AlertCircle } from 'lucide-react';
import { Modal, Button } from '@/components/ui';
import { api } from '@/lib/api';
import type { RosterImportResponse } from '@/types';
import styles from '../admin-users.module.css';
import { toast } from 'react-hot-toast';

interface RosterUploadModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function RosterUploadModal({ open, onClose, onSuccess }: RosterUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<RosterImportResponse | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const validateAndSetFile = (selectedFile: File) => {
    if (!selectedFile.name.endsWith('.xlsx') && !selectedFile.name.endsWith('.csv')) {
      toast.error('Chỉ hỗ trợ file .xlsx hoặc .csv');
      return;
    }
    setFile(selectedFile);
    setPhase('idle');
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setPhase('uploading');
    setProgress(0);

    try {
      const importResult = await api.roster.import(file, (pct) => {
        setProgress(pct);
      });
      setResult(importResult);
      setPhase('success');
      onSuccess();
    } catch (err: unknown) {
      console.error(err);
      toast.error('Đã xảy ra lỗi khi tải lên file danh bạ');
      setPhase('error');
    }
  };

  const resetState = () => {
    setFile(null);
    setPhase('idle');
    setProgress(0);
    setResult(null);
  };

  const handleClose = () => {
    if (phase !== 'uploading') {
      resetState();
      onClose();
    }
  };

  return (
    <Modal
      open={open}
      onClose={handleClose}
      title="Nhập danh bạ nhân sự"
      size="lg"
      closeOnOverlayClick={phase !== 'uploading'}
    >
      {(phase === 'idle' || phase === 'error') && (
        <div className={styles.uploadContainer}>
          <div
            className={`${styles.dropZone} ${dragActive ? styles.dropZoneActive : ''}`}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            {file ? (
              <div className={styles.selectedFile}>
                <FileSpreadsheet size={48} className={styles.fileIcon} />
                <p className={styles.fileName}>{file.name}</p>
                <p className={styles.fileSize}>{(file.size / 1024).toFixed(2)} KB</p>
                <button
                  className={styles.removeFileBtn}
                  onClick={(e) => {
                    e.stopPropagation();
                    setFile(null);
                  }}
                >
                  <X size={16} /> Bỏ chọn
                </button>
              </div>
            ) : (
              <>
                <Upload size={48} className={styles.uploadIcon} />
                <p className={styles.uploadText}>Kéo thả file vào đây hoặc</p>
                <label className={styles.uploadLabel}>
                  Chọn file
                  <input
                    type="file"
                    className={styles.uploadInput}
                    accept=".xlsx,.csv"
                    onChange={handleChange}
                  />
                </label>
                <p className={styles.uploadHint}>Chỉ hỗ trợ file định dạng .xlsx, .csv</p>
              </>
            )}
          </div>
          <div className={styles.modalActions}>
            <Button variant="outline" onClick={handleClose}>
              Hủy
            </Button>
            <Button
              variant="primary"
              disabled={!file || phase === 'error'}
              onClick={handleUpload}
            >
              Tiến hành nhập liệu
            </Button>
          </div>
        </div>
      )}

      {phase === 'uploading' && (
        <div className={styles.progressContainer}>
          <p className={styles.progressText}>Đang tải lên và xử lý dữ liệu...</p>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
          <p className={styles.progressValue}>{progress}%</p>
        </div>
      )}

      {phase === 'success' && result && (
        <div className={styles.importResult}>
          <div className={styles.importHeader}>
            <CheckCircle2 size={48} className={styles.successIcon} />
            <h3 className={styles.importTitle}>Nhập dữ liệu thành công</h3>
            <p className={styles.importSummary}>
              Đã nhập thành công <strong>{result.importedCount}</strong> / {result.totalRows} bản ghi
            </p>
          </div>

          {result.failedCount > 0 && (
            <div className={styles.importErrors}>
              <h4 className={styles.errorsTitle}>
                <AlertCircle size={16} />
                {result.failedCount} bản ghi lỗi
              </h4>
              <div className={styles.errorsTableWrapper}>
                <table className={styles.errorsTable}>
                  <thead>
                    <tr>
                      <th>Dòng</th>
                      <th>Mã NV</th>
                      <th>Chi tiết lỗi</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.errors.map((err, idx) => (
                      <tr key={idx}>
                        <td>{err.row}</td>
                        <td>{err.employeeCode || '-'}</td>
                        <td className={styles.errorReason}>{err.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          <div className={styles.modalActions}>
            <Button variant="primary" onClick={handleClose}>
              Đóng
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
}
