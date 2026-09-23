'use client';

import React, { useState, useEffect } from 'react';
import { X, Loader2, Edit } from 'lucide-react';
import { Button, Input, Select, Modal } from '@/components/ui';
import { api } from '@/lib/api';
import type { AccessRule, CreateAccessRuleRequest } from '@/types/document';

interface DepartmentOption {
  id: string;
  name: string;
}

interface UserOption {
  id: string;
  username: string;
  email: string;
  fullName?: string;
}

interface AccessRuleModalProps {
  documentId: string;
  departments?: DepartmentOption[];
  users?: UserOption[];
  onSuccess: () => void;
  editingRule?: AccessRule | null;
  onRuleDeleted?: () => void;
}

export function AccessRuleModal({
  documentId: propDocId,
  departments = [],
  users = [],
  onSuccess,
  editingRule,
  onRuleDeleted,
}: AccessRuleModalProps) {
  const [open, setOpen] = useState(false);
  const [targetType, setTargetType] = useState<'ROLE' | 'DEPARTMENT' | 'USER'>('ROLE');
  const [targetValue, setTargetValue] = useState('');
  const [permission, setPermission] = useState<'VIEW' | 'DENY'>('VIEW');
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [localDepts, setLocalDepts] = useState<DepartmentOption[]>(departments);
  const [localUsers, setLocalUsers] = useState<UserOption[]>(users);

  const isEditing = !!editingRule;

  useEffect(() => {
    if (editingRule) {
      setTargetType(editingRule.targetType);
      setTargetValue(
        editingRule.targetType === 'ROLE'
          ? editingRule.targetRole || ''
          : editingRule.targetType === 'DEPARTMENT'
          ? editingRule.targetDepartmentId || ''
          : editingRule.targetUserId || ''
      );
      setPermission(editingRule.permission);
    }
  }, [editingRule]);

  useEffect(() => {
    if (open && (departments.length === 0 || users.length === 0)) {
      setLoading(true);
      Promise.all([
        departments.length === 0 ? api.departments.getAll({ limit: 1000 }) : Promise.resolve(null),
        users.length === 0 ? api.users.search({ limit: 1000 }) : Promise.resolve(null),
      ]).then(([depts, usrs]) => {
        if (depts) setLocalDepts(depts.data as unknown as DepartmentOption[]);
        if (usrs) setLocalUsers(usrs.data as unknown as UserOption[]);
        setLoading(false);
      }).catch(() => setLoading(false));
    }
  }, [open]);

  const resetForm = () => {
    setTargetValue('');
    setTargetType('ROLE');
    setPermission('VIEW');
    setError(null);
  };

  const handleOpen = () => {
    if (editingRule) {
      setTargetType(editingRule.targetType);
      setTargetValue(
        editingRule.targetType === 'ROLE'
          ? editingRule.targetRole || ''
          : editingRule.targetType === 'DEPARTMENT'
          ? editingRule.targetDepartmentId || ''
          : editingRule.targetUserId || ''
      );
      setPermission(editingRule.permission);
    }
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
    resetForm();
  };

  const handleSave = async () => {
    if (!isEditing && !targetValue.trim()) return;
    if (isEditing && !targetType) return;
    setSaving(true);
    setError(null);
    try {
      const data: CreateAccessRuleRequest = {
        documentId: isEditing ? undefined : propDocId,
        targetType,
        permission,
      };
      if (targetType === 'ROLE') data.targetRole = targetValue.trim().toUpperCase();
      else if (targetType === 'DEPARTMENT') data.targetDepartmentId = targetValue;
      else if (targetType === 'USER') data.targetUserId = targetValue;

      if (isEditing && editingRule) {
        await api.metadata.updateAccessRule(editingRule.id, {
          targetType,
          permission,
          targetRole: data.targetRole,
          targetDepartmentId: data.targetDepartmentId,
          targetUserId: data.targetUserId,
        });
      } else {
        await api.metadata.createAccessRule(data);
      }
      handleClose();
      onSuccess();
    } catch (err: any) {
      const axiosErr = err as { response?: { data?: { message?: string } } };
      setError(axiosErr?.response?.data?.message || err?.message || 'Không thể lưu quy tắc truy cập.');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!editingRule) return;
    if (!confirm('Bạn có chắc muốn xóa quy tắc truy cập này?')) return;
    setDeleting(true);
    setError(null);
    try {
      await api.metadata.deleteAccessRule(editingRule.id);
      handleClose();
      onSuccess();
      if (onRuleDeleted) onRuleDeleted();
    } catch (err: any) {
      const axiosErr = err as { response?: { data?: { message?: string } } };
      setError(axiosErr?.response?.data?.message || err?.message || 'Không thể xóa quy tắc truy cập.');
    } finally {
      setDeleting(false);
    }
  };

  const roleOptions = [
    { value: 'MANAGER', label: 'Quản lý (MANAGER)' },
    { value: 'USER', label: 'Người dùng (USER)' },
  ];

  const deptOptions = localDepts.map((d) => ({ value: d.id, label: d.name }));
  const userOptions = localUsers.map((u) => ({
    value: u.id,
    label: u.fullName ? `${u.fullName} (${u.username})` : u.username,
  }));

  const targetOptions =
    targetType === 'ROLE' ? roleOptions :
    targetType === 'DEPARTMENT' ? deptOptions :
    userOptions;

  const canSave = isEditing
    ? !!targetType
    : !!targetValue.trim();

  return (
    <>
      {isEditing ? (
        <button
          onClick={handleOpen}
          className="p-1 text-gray-400 hover:text-indigo-600"
          title="Sửa quy tắc"
        >
          <Edit className="w-4 h-4" />
        </button>
      ) : (
        <Button
          variant="primary"
          size="sm"
          onClick={handleOpen}
          className="w-full"
        >
          Thêm quy tắc
        </Button>
      )}

      <Modal
        open={open}
        onClose={handleClose}
        title={isEditing ? 'Sửa quy tắc truy cập' : 'Thêm quy tắc truy cập'}
        size="sm"
        footer={
          <>
            {isEditing && (
              <Button
                variant="destructive"
                onClick={handleDelete}
                loading={deleting}
                className="mr-auto"
              >
                Xóa
              </Button>
            )}
            <Button variant="secondary" onClick={handleClose}>
              Hủy
            </Button>
            <Button
              variant="primary"
              loading={saving}
              onClick={handleSave}
              disabled={!canSave}
            >
              {isEditing ? 'Lưu thay đổi' : 'Thêm'}
            </Button>
          </>
        }
      >
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
            {error}
          </div>
        )}

        {isEditing && (
          <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700">
            <p className="font-medium">Đang chỉnh sửa quy tắc hiện có</p>
            <p className="mt-1 text-blue-600">
              Thay đổi loại đối tượng hoặc quyền sẽ cập nhật quy tắc này.
            </p>
          </div>
        )}

        <div className="space-y-4">
          <Select
            label="Loại đối tượng"
            value={targetType}
            onChange={(e) => {
              setTargetType(e.target.value as 'ROLE' | 'DEPARTMENT' | 'USER');
              setTargetValue('');
            }}
            options={[
              { value: 'ROLE', label: 'Vai trò' },
              { value: 'DEPARTMENT', label: 'Phòng ban' },
              { value: 'USER', label: 'Người dùng' },
            ]}
          />

          {targetType === 'ROLE' ? (
            <Select
              label="Vai trò"
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              options={roleOptions}
              placeholder="Chọn vai trò..."
              disabled={loading}
            />
          ) : (
            <Select
              label={targetType === 'DEPARTMENT' ? 'Phòng ban' : 'Người dùng'}
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              options={targetOptions}
              placeholder={loading ? 'Đang tải...' : `Chọn ${targetType === 'DEPARTMENT' ? 'phòng ban' : 'người dùng'}...`}
              disabled={loading}
            />
          )}

          <Select
            label="Quyền"
            value={permission}
            onChange={(e) => setPermission(e.target.value as 'VIEW' | 'DENY')}
            options={[
              { value: 'VIEW', label: 'Cho phép xem (VIEW)' },
              { value: 'DENY', label: 'Từ chối (DENY)' },
            ]}
          />

          <div className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600">
            <p className="font-medium text-gray-700 mb-1">Quy tắc OR:</p>
            <p>Nếu tài liệu có nhiều quy tắc truy cập cùng tồn tại, bất kỳ ai có ít nhất một quy tắc VIEW phù hợp đều được phép truy cập (trừ khi có quy tắc DENY chặn trước).</p>
            <p className="mt-1">Quy tắc trùng lặp (cùng đối tượng) sẽ không được thêm mới mà thay vào đó cập nhật quy tắc hiện có.</p>
          </div>
        </div>
      </Modal>
    </>
  );
}
