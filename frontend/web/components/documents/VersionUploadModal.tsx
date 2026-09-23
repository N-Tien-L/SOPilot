'use client';

import React, { useState } from 'react';
import { Upload, X } from 'lucide-react';
import { documentService } from '@/services/document.service';
import styles from './UploadModal.module.css';

interface VersionUploadModalProps {
  documentId: string;
  currentVersion: number;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export function VersionUploadModal({ documentId, currentVersion, isOpen, onClose, onSuccess }: VersionUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError('');
    try {
      await documentService.uploadNewVersion(documentId, file, `Phiên bản ${currentVersion + 1}`, () => {});
      onSuccess();
    } catch (e: any) {
      setError(e.message || 'Upload thất bại');
      setUploading(false);
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h2>Tải lên phiên bản mới</h2>
          <button onClick={onClose} className={styles.closeBtn}><X /></button>
        </div>
        <div className={styles.content}>
          <p>Chọn file mới:</p>
          <input type="file" onChange={e => setFile(e.target.files?.[0] || null)} />
          {file && <p>Đã chọn: {file.name}</p>}
          {error && <p style={{color: 'red'}}>{error}</p>}
        </div>
        <div className={styles.actions}>
          <button onClick={onClose} className={styles.backBtn}>Hủy</button>
          <button onClick={handleUpload} disabled={!file || uploading} className={styles.primaryBtn}>
            {uploading ? 'Đang tải...' : 'Tải lên'}
          </button>
        </div>
      </div>
    </div>
  );
}
