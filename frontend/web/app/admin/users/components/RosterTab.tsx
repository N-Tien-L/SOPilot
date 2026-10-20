'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { Download, Upload, Search, Trash2, AlertTriangle, ShieldCheck, ShieldAlert, FileSpreadsheet, Users, X, RefreshCw } from 'lucide-react';
import { Button, Input, Select, Badge, Table, Pagination } from '@/components/ui';
import { RosterUploadModal } from './RosterUploadModal';
import { api } from '@/lib/api';
import type { Department, RosterItem, RosterSearchParams } from '@/types';
import { RosterStatus } from '@/types';
import { toast } from 'react-hot-toast';

interface RosterTabProps {
  departments: Department[];
}

export function RosterTab({ departments }: RosterTabProps) {
  const [rosterItems, setRosterItems] = useState<RosterItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filterDepartment, setFilterDepartment] = useState<string>('ALL');
  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const hasFilters = Boolean(search || filterDepartment !== 'ALL' || filterStatus !== 'ALL');
  const clearFilters = () => {
    setSearch('');
    setDebouncedSearch('');
    setFilterDepartment('ALL');
    setFilterStatus('ALL');
    setPage(1);
  };
  const limit = 20;

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 500);
    return () => clearTimeout(timer);
  }, [search]);

  const loadRoster = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const params: RosterSearchParams = {
        page,
        limit,
      };

      if (debouncedSearch) params.keyword = debouncedSearch;
      if (filterDepartment !== 'ALL') params.departmentId = filterDepartment;
      if (filterStatus !== 'ALL') params.status = filterStatus as RosterStatus;

      const res = await api.roster.list(params);
      setRosterItems(res.data);
      setTotalPages(res.pagination.totalPages);
      setTotal(res.pagination.total);
    } catch (err) {
      console.error(err);
      setLoadError(true);
      toast.error('Không thể tải danh bạ nhân sự');
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, filterDepartment, filterStatus, page]);

  useEffect(() => {
    loadRoster();
  }, [loadRoster]);

  const handleDownloadTemplate = async () => {
    setDownloading(true);
    try {
      const blob = await api.roster.downloadTemplate();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'employee_roster_template.xlsx';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
      toast.error('Không thể tải file mẫu');
    } finally {
      setDownloading(false);
    }
  };

  const handleDeactivate = async (id: string) => {
    if (!window.confirm('Bạn có chắc chắn muốn xóa bản ghi danh bạ này?')) return;
    try {
      await api.roster.deactivate(id);
      toast.success('Đã vô hiệu hóa thành công');
      loadRoster();
    } catch (err) {
      console.error(err);
      toast.error('Lỗi khi vô hiệu hóa bản ghi');
    }
  };

  const renderStatusBadge = (status: RosterStatus) => {
    switch (status) {
      case RosterStatus.PENDING:
        return <Badge variant="warning"><AlertTriangle size={12} className="mr-1" /> Chờ kích hoạt</Badge>;
      case RosterStatus.CLAIMED:
        return <Badge variant="success"><ShieldCheck size={12} className="mr-1" /> Đã đăng nhập</Badge>;
      case RosterStatus.DEACTIVATED:
        return <Badge variant="danger"><ShieldAlert size={12} className="mr-1" /> Đã vô hiệu</Badge>;
      default:
        return <Badge variant="default">{status}</Badge>;
    }
  };

  const statusOptions = [
    { value: 'ALL', label: 'Tất cả trạng thái' },
    { value: RosterStatus.PENDING, label: 'Chờ kích hoạt' },
    { value: RosterStatus.CLAIMED, label: 'Đã đăng nhập' },
    { value: RosterStatus.DEACTIVATED, label: 'Đã vô hiệu' },
  ];

  const departmentOptions = [
    { value: 'ALL', label: 'Tất cả phòng ban' },
    ...departments.map(d => ({ value: d.id, label: d.name }))
  ];

  const columns = [
    {
      key: 'employeeCode',
      header: 'Mã nhân viên',
      width: '160px',
      render: (item: RosterItem) => <span className="font-mono text-sm">{item.employeeCode}</span>
    },
    {
      key: 'fullName',
      header: 'Họ và tên',
      render: (item: RosterItem) => (
        <div>
          <div className="font-medium">{item.fullName}</div>
          <div className="text-sm text-gray-500">{item.email}</div>
        </div>
      )
    },
    {
      key: 'department',
      header: 'Phòng ban',
      render: (item: RosterItem) => item.departmentName
    },
    {
      key: 'role',
      header: 'Vai trò',
      render: (item: RosterItem) => item.role
    },
    {
      key: 'status',
      header: 'Trạng thái',
      render: (item: RosterItem) => renderStatusBadge(item.status)
    },
    {
      key: 'actions',
      header: '',
      width: '80px',
      render: (item: RosterItem) => (
        item.status === RosterStatus.PENDING && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleDeactivate(item.id)}
            title="Vô hiệu hóa bản ghi"
            aria-label={`Vô hiệu hóa ${item.fullName}`}
            className="text-red-500 hover:text-red-700 hover:bg-red-50"
          >
            <Trash2 size={16} />
          </Button>
        )
      )
    }
  ];

  return (
    <div className="space-y-5 text-[var(--foreground)]">
      <section className="flex flex-col gap-5 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 sm:p-6 xl:flex-row xl:items-center xl:justify-between" aria-labelledby="roster-heading">
        <div className="flex items-start gap-4">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-[var(--accent)] text-[var(--primary)]"><FileSpreadsheet size={24} /></div>
          <div>
            <h2 id="roster-heading" className="text-lg font-semibold">Danh bạ nhân sự</h2>
            <p className="mt-1 max-w-xl text-sm leading-6 text-[var(--muted-foreground)]">Chuẩn bị danh sách nhân viên và theo dõi trạng thái kích hoạt tài khoản.</p>
            <p className="mt-2 text-xs text-[var(--muted-foreground)]">Tải mẫu Excel → Điền thông tin → Nhập danh bạ</p>
          </div>
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button variant="outline" icon={<Download size={16} />} loading={downloading} onClick={handleDownloadTemplate}>Tải file mẫu</Button>
          <Button icon={<Upload size={16} />} onClick={() => setShowUploadModal(true)}>Nhập Excel</Button>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)]" aria-label="Danh sách nhân sự">
        <div className="space-y-4 border-b border-[var(--border)] p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Users size={17} className="text-[var(--muted-foreground)]" /> Danh sách nhân sự
              {!loading && !loadError && <span className="rounded-md bg-[var(--muted)] px-2 py-0.5 text-xs tabular-nums" aria-live="polite">{total}</span>}
            </div>
            {hasFilters && <Button variant="ghost" size="sm" icon={<X size={14} />} onClick={clearFilters}>Xóa bộ lọc</Button>}
          </div>
          <div className="grid items-end gap-3 md:grid-cols-2 xl:grid-cols-[minmax(280px,1fr)_220px_200px]">
            <div className="min-w-0 md:col-span-2 xl:col-span-1">
              <Input label="Tìm kiếm nhân sự" placeholder="Nhập mã nhân viên, họ tên hoặc email…" value={search} onChange={(e) => setSearch(e.target.value)} leftIcon={<Search size={18} />} />
            </div>
            <Select label="Phòng ban" value={filterDepartment} onChange={(e) => { setFilterDepartment(e.target.value); setPage(1); }} options={departmentOptions} />
            <Select label="Trạng thái" value={filterStatus} onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }} options={statusOptions} />
          </div>
        </div>

        {loadError ? (
          <div role="alert" className="flex min-h-72 flex-col items-center justify-center gap-3 p-6 text-center">
            <AlertTriangle size={30} className="text-[var(--warning-foreground)]" />
            <h3 className="font-semibold">Không thể tải danh bạ</h3>
            <p className="text-sm text-[var(--muted-foreground)]">Vui lòng thử lại để cập nhật danh sách nhân sự.</p>
            <Button variant="outline" icon={<RefreshCw size={16} />} onClick={loadRoster}>Thử lại</Button>
          </div>
        ) : (
          <Table
            className="[&>div]:rounded-none [&>div]:border-0"
            columns={columns}
            data={rosterItems}
            keyExtractor={(item) => item.id}
            loading={loading}
            empty={
              <tr><td colSpan={columns.length}>
                <div className="flex min-h-80 flex-col items-center justify-center px-5 py-12 text-center">
                  <div className="mb-4 flex size-16 items-center justify-center rounded-2xl bg-[var(--muted)] text-[var(--primary)]">{hasFilters ? <Search size={28} /> : <Users size={28} />}</div>
                  <h3 className="text-base font-semibold">{hasFilters ? 'Không tìm thấy nhân sự phù hợp' : 'Danh bạ đang trống'}</h3>
                  <p className="mb-5 mt-2 max-w-sm text-sm leading-6 text-[var(--muted-foreground)]">{hasFilters ? 'Thử tìm bằng từ khóa khác hoặc xóa bộ lọc để xem toàn bộ danh sách.' : 'Bắt đầu bằng cách nhập danh sách nhân viên từ file Excel theo mẫu.'}</p>
                  {hasFilters ? <Button variant="outline" icon={<X size={16} />} onClick={clearFilters}>Xóa bộ lọc</Button> : <Button icon={<Upload size={16} />} onClick={() => setShowUploadModal(true)}>Nhập danh bạ đầu tiên</Button>}
                </div>
              </td></tr>
            }
          />
        )}

        {!loading && !loadError && total > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[var(--border)] px-5 py-4">
            <p className="text-sm text-[var(--muted-foreground)]">Hiển thị {(page - 1) * limit + 1}–{Math.min(page * limit, total)} trong {total} nhân sự</p>
            {totalPages > 1 && <Pagination page={page} totalPages={totalPages} onPageChange={setPage} />}
          </div>
        )}
      </section>

      <RosterUploadModal open={showUploadModal} onClose={() => setShowUploadModal(false)} onSuccess={() => { if (page === 1) loadRoster(); else setPage(1); }} />
    </div>
  );
}
