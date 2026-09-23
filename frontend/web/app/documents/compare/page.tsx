'use client';

import React, { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Search,
  GitCompare,
  Plus,
  Minus,
  FileText,
} from 'lucide-react';
import {
  Button,
  Input,
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  Badge,
  EmptyState,
} from '@/components/ui';
import { api } from '@/lib/api';
import type { Document } from '@/types';
import styles from './compare.module.css';

export default function ComparePoliciesPage() {
  const router = useRouter();
  const [search1, setSearch1] = useState('');
  const [search2, setSearch2] = useState('');
  const [doc1, setDoc1] = useState<Document | null>(null);
  const [doc2, setDoc2] = useState<Document | null>(null);
  const [results, setResults] = useState<{
    document1Id: string;
    document2Id: string;
    document1Title: string;
    document2Title: string;
    addedSections: { sectionTitle: string; oldContent: string | null; newContent: string | null; changeType: string }[];
    removedSections: { sectionTitle: string; oldContent: string | null; newContent: string | null; changeType: string }[];
    modifiedSections: { sectionTitle: string; oldContent: string | null; newContent: string | null; changeType: string }[];
    totalChanges: number;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCompare = async () => {
    if (!doc1 || !doc2) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.documents.comparePolicies(doc1.id, doc2.id);
      setResults(data);
    } catch {
      setError('Không thể so sánh hai tài liệu. Đảm bảo cả hai đã được xử lý.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.container}>
      <Button variant="ghost" icon={<ArrowLeft size={16} />} onClick={() => router.back()}>
        Quay lại
      </Button>

      <div className={styles.header}>
        <div className={styles.icon}>
          <GitCompare size={24} />
        </div>
        <div>
          <h1>So sánh chính sách</h1>
          <p>Chọn hai tài liệu để so sánh nội dung và xem các thay đổi.</p>
        </div>
      </div>

      <div className={styles.selection}>
        <Card padding="md">
          <CardHeader>
            <CardTitle as="h2">Tài liệu 1</CardTitle>
          </CardHeader>
          <CardContent>
            {doc1 ? (
              <div className={styles.selectedDoc}>
                <FileText size={18} />
                <span>{doc1.title}</span>
                <Button variant="ghost" size="sm" onClick={() => setDoc1(null)}>Đổi</Button>
              </div>
            ) : (
              <Input
                placeholder="Tìm kiếm tài liệu..."
                value={search1}
                onChange={(e) => setSearch1(e.target.value)}
                leftIcon={<Search size={16} />}
              />
            )}
          </CardContent>
        </Card>

        <div className={styles.vs}>VS</div>

        <Card padding="md">
          <CardHeader>
            <CardTitle as="h2">Tài liệu 2</CardTitle>
          </CardHeader>
          <CardContent>
            {doc2 ? (
              <div className={styles.selectedDoc}>
                <FileText size={18} />
                <span>{doc2.title}</span>
                <Button variant="ghost" size="sm" onClick={() => setDoc2(null)}>Đổi</Button>
              </div>
            ) : (
              <Input
                placeholder="Tìm kiếm tài liệu..."
                value={search2}
                onChange={(e) => setSearch2(e.target.value)}
                leftIcon={<Search size={16} />}
              />
            )}
          </CardContent>
        </Card>

        <Button
          variant="primary"
          icon={<GitCompare size={16} />}
          onClick={handleCompare}
          disabled={!doc1 || !doc2 || loading}
          loading={loading}
        >
          So sánh
        </Button>
      </div>

      {error && (
        <div className={styles.error}>{error}</div>
      )}

      {results && (
        <div className={styles.results}>
          {/* Headers */}
          <div className={styles.resultHeader}>
            <div className={styles.docLabel}>{results.document1Title}</div>
            <div className={styles.docLabel}>{results.document2Title}</div>
          </div>

          {/* Stats */}
          <div className={styles.stats}>
            {results.addedSections.length > 0 && (
              <Badge variant="success">{results.addedSections.length} mục mới</Badge>
            )}
            {results.removedSections.length > 0 && (
              <Badge variant="destructive">{results.removedSections.length} mục bị xóa</Badge>
            )}
            {results.modifiedSections.length > 0 && (
              <Badge variant="warning">{results.modifiedSections.length} mục thay đổi</Badge>
            )}
          </div>

          {results.addedSections.length > 0 && (
            <Card padding="md">
              <CardHeader>
                <CardTitle as="h3">
                  <Plus size={16} /> Mục mới (trong tài liệu 2)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className={styles.changeList}>
                  {results.addedSections.map((item, i) => (
                    <li key={i} className={styles.added}>{item.newContent}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {results.removedSections.length > 0 && (
            <Card padding="md">
              <CardHeader>
                <CardTitle as="h3">
                  <Minus size={16} /> Mục bị xóa (không có trong tài liệu 2)
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className={styles.changeList}>
                  {results.removedSections.map((item, i) => (
                    <li key={i} className={styles.removed}>{item.oldContent}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {results.modifiedSections.length > 0 && (
            <Card padding="md">
              <CardHeader>
                <CardTitle as="h3">
                  <GitCompare size={16} /> Mục thay đổi
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className={styles.modifiedList}>
                  {results.modifiedSections.map((item, i) => (
                    <div key={i} className={styles.modifiedItem}>
                      <Minus size={14} className={styles.removedIcon} />
                      <span className={styles.oldText}>{item.oldContent}</span>
                      <Plus size={14} className={styles.addedIcon} />
                      <span className={styles.newText}>{item.newContent}</span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {results.totalChanges === 0 && (
            <EmptyState
              icon={<GitCompare size={32} />}
              title="Không có thay đổi"
              description="Hai tài liệu này có nội dung giống nhau."
            />
          )}
        </div>
      )}
    </div>
  );
}
