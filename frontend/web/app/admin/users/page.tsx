'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  Shield,
  UserX,
  UserCheck,
  Loader2,
  ChevronLeft,
  ChevronRight,
  Plus,
  UserPlus,
  Upload,
  X,
  CheckCircle,
  AlertCircle,
  Eye,
  Edit2,
  Trash2,
  Filter,
  Building2,
  User as UserIcon,
  Mail,
  Calendar,
  Users,
  UserCog,
  TrendingUp,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useIsAdmin } from '@/store';
import { useLanguage } from '@/providers';
import { Translator } from '@/lib/i18n';
import { UserRole, AccountStatus } from '@/types';
import type { User, Department } from '@/types';
import styles from './admin-users.module.css';
import toast from 'react-hot-toast';

export default function AdminUsersPage() {
  const isAdmin = useIsAdmin();
  const router = useRouter();
  const { t } = useLanguage();

  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState({ total: 0, active: 0, deactivated: 0, admins: 0 });

  // Filter states
  const [filterRole, setFilterRole] = useState<string>('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterDepartment, setFilterDepartment] = useState<string>('');
  const [departments, setDepartments] = useState<Department[]>([]);
  const [showFilters, setShowFilters] = useState(false);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showBulkModal, setShowBulkModal] = useState(false);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [activeTab, setActiveTab] = useState<'single' | 'bulk'>('single');

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.users.search({
        page: page - 1,
        limit: 10,
        keyword: search || undefined,
        role: filterRole || undefined,
        status: filterStatus || undefined,
        departmentId: filterDepartment || undefined,
      });
      setUsers(result.data);
      setTotalPages(result.pagination.totalPages);
      setTotal(result.pagination.total);
      
      // Calculate stats from current results
      setStats({
        total: result.pagination.total,
        active: result.data.filter(u => u.status === AccountStatus.ACTIVE).length,
        deactivated: result.data.filter(u => u.status !== AccountStatus.ACTIVE).length,
        admins: result.data.filter(u => u.role === UserRole.ADMIN).length,
      });
    } catch (err) {
      console.error('Failed to load users:', err);
    } finally {
      setLoading(false);
    }
  }, [page, search, filterRole, filterStatus, filterDepartment]);

  const loadDepartments = useCallback(async () => {
    try {
      const depts = await api.departments.getActive();
      setDepartments(depts);
    } catch (err) {
      console.error('Failed to load departments:', err);
    }
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      router.push('/');
      return;
    }
    loadDepartments();
    loadUsers();
  }, [isAdmin, router, loadUsers, loadDepartments]);

  const handleStatusChange = async (userId: string, status: AccountStatus, closeModal?: () => void) => {
    try {
      if (status === AccountStatus.DEACTIVATED) {
        await api.users.deactivate(userId);
        toast.success('Đã vô hiệu hóa tài khoản thành công');
      } else if (status === AccountStatus.ACTIVE) {
        await api.users.reactivate(userId);
        toast.success('Đã kích hoạt lại tài khoản thành công');
      } else if (status === AccountStatus.REVOKED) {
        await api.users.revoke(userId);
        toast.success('Đã thu hồi tài khoản thành công');
      }
      closeModal?.();
      setShowDetailModal(false);
      setSelectedUser(null);
      loadUsers();
    } catch (err) {
      console.error('Failed to update status:', err);
      toast.error('Không thể cập nhật trạng thái. Vui lòng thử lại.');
    }
  };

  const handleDelete = async (userId: string) => {
    if (!confirm(t('admin.users.delete.confirm').replace('{username}', selectedUser?.username || ''))) return;
    try {
      await api.users.delete(userId);
      toast.success('Đã xóa tài khoản thành công');
      loadUsers();
    } catch (err) {
      console.error('Failed to delete user:', err);
      toast.error('Không thể xóa tài khoản. Vui lòng thử lại.');
    }
  };

  const openDetailModal = (user: User) => {
    setSelectedUser(user);
    setShowDetailModal(true);
  };

  const openEditModal = (user: User) => {
    setSelectedUser(user);
    setShowEditModal(true);
  };

  const openDeleteModal = (user: User) => {
    setSelectedUser(user);
    setShowDeleteModal(true);
  };

  const clearFilters = () => {
    setFilterRole('');
    setFilterStatus('');
    setFilterDepartment('');
    setSearch('');
    setPage(1);
  };

  const hasActiveFilters = filterRole || filterStatus || filterDepartment || search;

  const roleLabels: Record<UserRole, string> = {
    [UserRole.ADMIN]: t('role.admin'),
    [UserRole.MANAGER]: t('role.manager'),
    [UserRole.USER]: t('role.user'),
  };

  const statusLabels: Record<AccountStatus, string> = {
    [AccountStatus.ACTIVE]: t('admin.users.status.active'),
    [AccountStatus.DEACTIVATED]: t('admin.users.status.deactivated'),
    [AccountStatus.REVOKED]: t('admin.users.status.revoked'),
  };

  const statusBadgeClass: Record<AccountStatus, string> = {
    [AccountStatus.ACTIVE]: styles.statusActive,
    [AccountStatus.DEACTIVATED]: styles.statusDeactivated,
    [AccountStatus.REVOKED]: styles.statusRevoked,
  };

  return (
    <div className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerContent}>
          <h1>{t('admin.users.title')}</h1>
          <p>{t('admin.users.subtitle')}</p>
        </div>
        <div className={styles.headerActions}>
          <button
            className={styles.createBulkButton}
            onClick={() => { setActiveTab('bulk'); setShowBulkModal(true); }}
          >
            <Upload size={16} />
            <span>{t('admin.users.createBulk')}</span>
          </button>
          <button
            className={styles.createButton}
            onClick={() => setShowCreateModal(true)}
          >
            <Plus size={16} />
            {t('admin.users.create')}
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className={styles.statsGrid}>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.primary}`}>
            <Users size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statValue}>{total}</span>
            <span className={styles.statLabel}>Tổng người dùng</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.success}`}>
            <UserCheck size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statValue}>{stats.active}</span>
            <span className={styles.statLabel}>Đang hoạt động</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.warning}`}>
            <UserX size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statValue}>{stats.deactivated}</span>
            <span className={styles.statLabel}>Không hoạt động</span>
          </div>
        </div>
        <div className={styles.statCard}>
          <div className={`${styles.statIcon} ${styles.danger}`}>
            <Shield size={22} />
          </div>
          <div className={styles.statContent}>
            <span className={styles.statValue}>{stats.admins}</span>
            <span className={styles.statLabel}>Quản trị viên</span>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className={styles.filters}>
        <div className={styles.filterRow}>
          <div className={styles.searchWrapper}>
            <input
              type="text"
              placeholder={t('admin.users.search.placeholder')}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className={styles.searchInput}
              onKeyDown={(e) => e.key === 'Enter' && loadUsers()}
            />
            <Search size={18} className={styles.searchIcon} />
          </div>
          <button
            className={`${styles.filterToggleBtn} ${showFilters ? styles.active : ''}`}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter size={16} />
            {t('docs.filter')}
            {hasActiveFilters && <span className={styles.filterBadge} />}
          </button>
        </div>

          {showFilters && (
            <div className={styles.filterPanel}>
              <div className={styles.filterGroup}>
                <label>{t('admin.users.filter.role')}</label>
                <select
                  value={filterRole}
                  onChange={(e) => { setFilterRole(e.target.value); setPage(1); }}
                >
                  <option value="">{t('admin.users.filter.allRoles')}</option>
                  <option value="USER">{t('role.user')}</option>
                  <option value="MANAGER">{t('role.manager')}</option>
                  <option value="ADMIN">{t('role.admin')}</option>
                </select>
              </div>
              <div className={styles.filterGroup}>
                <label>{t('admin.users.filter.status')}</label>
                <select
                  value={filterStatus}
                  onChange={(e) => { setFilterStatus(e.target.value); setPage(1); }}
                >
                  <option value="">{t('admin.users.filter.allStatuses')}</option>
                  <option value="ACTIVE">{t('admin.users.status.active')}</option>
                  <option value="DEACTIVATED">{t('admin.users.status.deactivated')}</option>
                  <option value="REVOKED">{t('admin.users.status.revoked')}</option>
                </select>
              </div>
              <div className={styles.filterGroup}>
                <label>{t('admin.users.filter.department')}</label>
                <select
                  value={filterDepartment}
                  onChange={(e) => { setFilterDepartment(e.target.value); setPage(1); }}
                >
                  <option value="">{t('admin.users.filter.allDepartments')}</option>
                  {departments.map((dept) => (
                    <option key={dept.id} value={dept.id}>{dept.name}</option>
                  ))}
                </select>
              </div>
              <div className={styles.filterActions}>
                <button className={styles.applyBtn} onClick={loadUsers}>
                  {t('admin.users.filter.apply')}
                </button>
                {hasActiveFilters && (
                  <button className={styles.clearBtn} onClick={clearFilters}>
                    {t('admin.users.filter.clear')}
                  </button>
                )}
              </div>
            </div>
          )}

          {hasActiveFilters && (
            <div className={styles.activeFilters}>
              {filterRole && <span className={styles.filterChip}>{t('admin.users.filter.role')}: {roleLabels[filterRole as UserRole]}</span>}
              {filterStatus && <span className={styles.filterChip}>{t('admin.users.filter.status')}: {statusLabels[filterStatus as AccountStatus]}</span>}
              {filterDepartment && <span className={styles.filterChip}>{t('admin.users.filter.department')}: {departments.find(d => d.id === filterDepartment)?.name}</span>}
              {search && <span className={styles.filterChip}>Tìm: "{search}"</span>}
            </div>
          )}
        </div>

        <div className={styles.tableWrapper}>
          {loading ? (
            <div className={styles.loading}>
              <Loader2 size={32} className={styles.spinner} />
              <span>{t('admin.users.loading')}</span>
            </div>
          ) : users.length === 0 ? (
            <div className={styles.empty}>
              <div className={styles.emptyIcon}>
                <UserIcon size={28} />
              </div>
              <p>{t('admin.users.table.noData')}</p>
            </div>
          ) : (
            <table className={styles.table}>
              <thead>
                <tr>
                  <th>{t('admin.users.table.user')}</th>
                  <th>{t('admin.users.table.email')}</th>
                  <th>{t('admin.users.table.role')}</th>
                  <th>{t('admin.users.table.department')}</th>
                  <th>{t('admin.users.table.status')}</th>
                  <th>{t('admin.users.table.actions')}</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id}>
                    <td>
                      <div className={styles.userCell}>
                        <div className={styles.avatar}>
                          {(user.fullName || user.username || 'U').charAt(0).toUpperCase()}
                        </div>
                        <span className={styles.username}>{user.username}</span>
                      </div>
                    </td>
                    <td>{user.email}</td>
                    <td>
                      <span className={`${styles.roleBadge} ${user.role === UserRole.ADMIN ? styles.roleAdmin : user.role === UserRole.MANAGER ? styles.roleManager : styles.roleUser}`}>
                        {roleLabels[user.role]}
                      </span>
                    </td>
                    <td>
                      {user.department?.name ? (
                        <div className={styles.deptCell}>
                          <Building2 size={14} />
                          <span>{user.department.name}</span>
                        </div>
                      ) : <span className={styles.noData}>-</span>}
                    </td>
                    <td>
                      <span className={`${styles.statusBadge} ${statusBadgeClass[user.status]}`}>
                        {statusLabels[user.status]}
                      </span>
                    </td>
                    <td>
                      <div className={styles.actions}>
                        <button
                          className={styles.actionButton}
                          onClick={() => openDetailModal(user)}
                          title={t('admin.users.viewDetail')}
                        >
                          <Eye size={16} />
                        </button>
                        <button
                          className={styles.actionButton}
                          onClick={() => openEditModal(user)}
                          title={t('admin.users.edit')}
                        >
                          <Edit2 size={16} />
                        </button>
                        {user.status === AccountStatus.ACTIVE && (
                          <>
                            <button
                              className={styles.actionButton}
                              onClick={() => handleStatusChange(user.id, AccountStatus.DEACTIVATED)}
                              title={t('admin.users.deactivate')}
                            >
                              <UserX size={16} />
                            </button>
                            <button
                              className={`${styles.actionButton} ${styles.danger}`}
                              onClick={() => openDeleteModal(user)}
                              title={t('admin.users.delete')}
                            >
                              <Trash2 size={16} />
                            </button>
                          </>
                        )}
                        {(user.status === AccountStatus.DEACTIVATED || user.status === AccountStatus.REVOKED) && (
                          <button
                            className={`${styles.actionButton} ${styles.success}`}
                            onClick={() => handleStatusChange(user.id, AccountStatus.ACTIVE)}
                            title={t('admin.users.reactivate')}
                          >
                            <UserCheck size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {totalPages > 1 && (
          <div className={styles.pagination}>
            <span className={styles.paginationInfo}>
              {t('admin.users.pagination.showing').replace('{count}', String(users.length)).replace('{total}', String(total))}
            </span>
            <div className={styles.paginationControls}>
              <button
                className={styles.pageButton}
                disabled={page === 1}
                onClick={() => setPage(page - 1)}
              >
                <ChevronLeft size={16} />
              </button>
              {Array.from({ length: Math.min(totalPages, 5) }, (_, i) => {
                let pageNum = i + 1;
                if (totalPages > 5) {
                  if (page <= 3) {
                    pageNum = i + 1;
                  } else if (page >= totalPages - 2) {
                    pageNum = totalPages - 4 + i;
                  } else {
                    pageNum = page - 2 + i;
                  }
                }
                return (
                  <button
                    key={pageNum}
                    className={`${styles.pageNumber} ${page === pageNum ? styles.active : ''}`}
                    onClick={() => setPage(pageNum)}
                  >
                    {pageNum}
                  </button>
                );
              })}
              <button
                className={styles.pageButton}
                disabled={page === totalPages}
                onClick={() => setPage(page + 1)}
              >
                <ChevronRight size={16} />
              </button>
            </div>
          </div>
        )}

        {showDetailModal && selectedUser && (
          <UserDetailModal
            user={selectedUser}
            departments={departments}
            onClose={() => { setShowDetailModal(false); setSelectedUser(null); }}
            onStatusChange={handleStatusChange}
            roleLabels={roleLabels}
            statusLabels={statusLabels}
            statusBadgeClass={statusBadgeClass}
            t={t}
          />
        )}

        {/* Edit User Modal */}
        {showEditModal && selectedUser && (
          <UserEditModal
            user={selectedUser}
            departments={departments}
            onClose={() => { setShowEditModal(false); setSelectedUser(null); }}
            onSuccess={() => { setShowEditModal(false); setSelectedUser(null); loadUsers(); }}
            roleLabels={roleLabels}
            t={t}
          />
        )}

        {/* Delete Confirmation Modal */}
        {showDeleteModal && selectedUser && (
          <UserDeleteModal
            user={selectedUser}
            onClose={() => { setShowDeleteModal(false); setSelectedUser(null); }}
            onConfirm={() => { handleDelete(selectedUser.id); setShowDeleteModal(false); setSelectedUser(null); }}
            t={t}
          />
        )}

        {/* Create Single User Modal */}
        {showCreateModal && (
          <CreateUserModal
            departments={departments}
            onClose={() => setShowCreateModal(false)}
            onSuccess={() => { setShowCreateModal(false); loadUsers(); }}
            roleLabels={roleLabels}
            t={t}
          />
        )}

        {/* Bulk Create Modal */}
        {showBulkModal && (
          <BulkCreateModal
            departments={departments}
            onClose={() => setShowBulkModal(false)}
            onSuccess={() => { setShowBulkModal(false); loadUsers(); }}
            roleLabels={roleLabels}
            t={t}
          />
        )}
      </div>
  );
}

// ===============================
// User Detail Modal
// ===============================
interface UserDetailModalProps {
  user: User;
  departments: Department[];
  onClose: () => void;
  onStatusChange: (userId: string, status: AccountStatus, closeModal?: () => void) => void;
  roleLabels: Record<UserRole, string>;
  statusLabels: Record<AccountStatus, string>;
  statusBadgeClass: Record<AccountStatus, string>;
  t: Translator;
}

function UserDetailModal({ user, departments, onClose, onStatusChange, roleLabels, statusLabels, statusBadgeClass, t }: UserDetailModalProps) {
  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={`${styles.modal} ${styles.detailModal}`} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <UserIcon size={20} />
            <h2>{t('admin.users.detail.title')}</h2>
          </div>
          <button className={styles.modalClose} onClick={onClose}><X size={18} /></button>
        </div>
        <div className={styles.modalBody}>
          <div className={styles.detailHeader}>
            <div className={styles.detailAvatar}>
              {(user.fullName || user.username || 'U').charAt(0).toUpperCase()}
            </div>
            <div className={styles.detailHeaderInfo}>
              <h3>{user.fullName || user.username}</h3>
              <span className={`${styles.statusBadge} ${statusBadgeClass[user.status]}`}>
                {statusLabels[user.status]}
              </span>
            </div>
          </div>

          <div className={styles.detailSections}>
            <div className={styles.detailSection}>
              <h4>{t('admin.users.detail.accountInfo')}</h4>
              <div className={styles.detailGrid}>
                <div className={styles.detailItem}>
                  <UserIcon size={16} />
                  <label>{t('profile.username')}:</label>
                  <span>{user.username}</span>
                </div>
                <div className={styles.detailItem}>
                  <Mail size={16} />
                  <label>{t('profile.email')}:</label>
                  <span>{user.email}</span>
                </div>
                <div className={styles.detailItem}>
                  <Shield size={16} />
                  <label>{t('profile.role')}:</label>
                  <span className={`${styles.roleBadge} ${user.role === UserRole.ADMIN ? styles.roleAdmin : user.role === UserRole.MANAGER ? styles.roleManager : styles.roleUser}`}>
                    {roleLabels[user.role]}
                  </span>
                </div>
                <div className={styles.detailItem}>
                  <Building2 size={16} />
                  <label>{t('admin.users.detail.department')}:</label>
                  <span>{user.department?.name || t('admin.users.detail.unassigned')}</span>
                </div>
              </div>
            </div>

            {user.createdAt && (
              <div className={styles.detailSection}>
                <h4>{t('admin.users.detail.systemInfo')}</h4>
                <div className={styles.detailGrid}>
                  <div className={styles.detailItem}>
                    <Calendar size={16} />
                    <label>{t('admin.users.detail.created')}:</label>
                    <span>{new Date(user.createdAt).toLocaleDateString('vi-VN')}</span>
                  </div>
                  <div className={styles.detailItem}>
                    <Calendar size={16} />
                    <label>{t('admin.users.detail.updated')}:</label>
                    <span>{new Date(user.updatedAt || user.createdAt).toLocaleDateString('vi-VN')}</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
        <div className={styles.modalFooter}>
          {user.status === AccountStatus.ACTIVE && (
            <>
              <button
                className={styles.warningButton}
            onClick={() => onStatusChange(user.id, AccountStatus.DEACTIVATED, onClose)}
              >
                <UserX size={16} />
                {t('admin.users.deactivate')}
              </button>
              <button
                className={styles.dangerButton}
                onClick={() => onStatusChange(user.id, AccountStatus.REVOKED, onClose)}
              >
                <Shield size={16} />
                {t('admin.users.revoke')}
              </button>
            </>
          )}
          {(user.status === AccountStatus.DEACTIVATED || user.status === AccountStatus.REVOKED) && (
            <button
              className={styles.successButton}
              onClick={() => onStatusChange(user.id, AccountStatus.ACTIVE, onClose)}
            >
              <UserCheck size={16} />
              {t('admin.users.reactivate')}
            </button>
          )}
          <button className={styles.cancelButton} onClick={onClose}>{t('admin.users.close')}</button>
        </div>
      </div>
    </div>
  );
}

// ===============================
// User Edit Modal
// ===============================
interface UserEditModalProps {
  user: User;
  departments: Department[];
  onClose: () => void;
  onSuccess: () => void;
  roleLabels: Record<UserRole, string>;
  t: Translator;
}

function UserEditModal({ user, departments, onClose, onSuccess, roleLabels, t }: UserEditModalProps) {
  const [form, setForm] = useState({
    role: user.role,
    status: user.status,
    departmentId: user.departmentId || '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!user.id) {
      setError(t('admin.users.edit.idError'));
      return;
    }
    setError('');
    setLoading(true);
    try {
      await api.users.update(user.id, {
        role: form.role,
        status: form.status,
        departmentId: form.departmentId || undefined,
      });
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message :
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || t('admin.users.edit.updateFailed');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <Edit2 size={20} />
            <h2>{t('admin.users.edit.title')}</h2>
          </div>
          <button className={styles.modalClose} onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className={styles.modalBody}>
          {error && (
            <div className={styles.errorBanner}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className={styles.userInfoHeader}>
            <div className={styles.avatar}>
              {(user.fullName || user.username || 'U').charAt(0).toUpperCase()}
            </div>
            <div>
              <strong>{user.fullName || user.username}</strong>
              <p>{user.email}</p>
            </div>
          </div>

          <div className={styles.formGrid}>
            <div className={styles.formGroup}>
              <label>{t('profile.role')}</label>
              <select
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole }))}
              >
                <option value={UserRole.USER}>{roleLabels[UserRole.USER]}</option>
                <option value={UserRole.MANAGER}>{roleLabels[UserRole.MANAGER]}</option>
                <option value={UserRole.ADMIN}>{roleLabels[UserRole.ADMIN]}</option>
              </select>
            </div>

            <div className={styles.formGroup}>
              <label>{t('profile.department')}</label>
              <select
                value={form.departmentId}
                onChange={e => setForm(f => ({ ...f, departmentId: e.target.value }))}
              >
                <option value="">{t('admin.users.create.unassigned')}</option>
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.modalFooter}>
            <button type="button" className={styles.cancelButton} onClick={onClose}>{t('common.cancel')}</button>
            <button type="submit" className={styles.submitButton} disabled={loading}>
              {loading ? <Loader2 size={16} className={styles.spinner} /> : <CheckCircle size={16} />}
              {t('admin.users.edit.title')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ===============================
// User Delete Modal
// ===============================
interface UserDeleteModalProps {
  user: User;
  onClose: () => void;
  onConfirm: () => void;
  t: Translator;
}

function UserDeleteModal({ user, onClose, onConfirm, t }: UserDeleteModalProps) {
  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <AlertCircle size={20} />
            <h2>{t('admin.users.delete.title')}</h2>
          </div>
          <button className={styles.modalClose} onClick={onClose}><X size={18} /></button>
        </div>
        <div className={styles.modalBody}>
          <div className={styles.warningBox}>
            <p dangerouslySetInnerHTML={{ __html: t('admin.users.delete.confirm').replace('{username}', user.username) }} />
            <ul>
              <li>{t('admin.users.delete.effects')}</li>
              <li>{t('admin.users.delete.effects2')}</li>
              <li>{t('admin.users.delete.effects3')}</li>
              <li>{t('admin.users.delete.effects4')}</li>
            </ul>
          </div>
        </div>
        <div className={styles.modalFooter}>
          <button className={styles.cancelButton} onClick={onClose}>{t('common.cancel')}</button>
          <button className={styles.dangerButton} onClick={onConfirm}>
            <Trash2 size={16} />
            {t('admin.users.delete.confirmBtn')}
          </button>
        </div>
      </div>
    </div>
  );
}

// ===============================
// Create User Modal
// ===============================
interface CreateUserModalProps {
  departments: Department[];
  onClose: () => void;
  onSuccess: () => void;
  roleLabels: Record<UserRole, string>;
  t: Translator;
}

function CreateUserModal({ departments, onClose, onSuccess, roleLabels, t }: CreateUserModalProps) {
  const [form, setForm] = useState({
    username: '',
    email: '',
    fullName: '',
    role: UserRole.USER,
    departmentId: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await api.users.create({
        username: form.username,
        email: form.email,
        fullName: form.fullName,
        role: form.role,
        departmentId: form.departmentId || undefined,
      });
      toast.success(`Đã tạo tài khoản "${form.username}" thành công. Mật khẩu đã được gửi qua email.`);
      onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message :
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || t('admin.users.create.failed');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <UserPlus size={20} />
            <h2>{t('admin.users.create.title')}</h2>
          </div>
          <button className={styles.modalClose} onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className={styles.modalBody}>
          {error && (
            <div className={error.includes(t('admin.users.create.failed')) ? styles.warningBanner : styles.errorBanner}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <div className={styles.formGrid}>
            <div className={styles.formGroup}>
              <label>{t('admin.users.create.username')}</label>
              <input
                type="text"
                value={form.username}
                onChange={e => setForm(f => ({ ...f, username: e.target.value }))}
                placeholder={t('admin.users.create.username.placeholder')}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>{t('admin.users.create.fullName')}</label>
              <input
                type="text"
                value={form.fullName}
                onChange={e => setForm(f => ({ ...f, fullName: e.target.value }))}
                placeholder={t('admin.users.create.fullName.placeholder')}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>{t('admin.users.create.email')}</label>
              <input
                type="email"
                value={form.email}
                onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                placeholder={t('admin.users.create.email.placeholder')}
                required
              />
            </div>

            <div className={styles.formGroup}>
              <label>{t('admin.users.create.role')}</label>
              <select
                value={form.role}
                onChange={e => setForm(f => ({ ...f, role: e.target.value as UserRole }))}
              >
                <option value={UserRole.USER}>{roleLabels[UserRole.USER]}</option>
                <option value={UserRole.MANAGER}>{roleLabels[UserRole.MANAGER]}</option>
                <option value={UserRole.ADMIN}>{roleLabels[UserRole.ADMIN]}</option>
              </select>
            </div>

            <div className={`${styles.formGroup} ${styles.fullWidth}`}>
              <label>{t('admin.users.create.department')}</label>
              <select
                value={form.departmentId}
                onChange={e => setForm(f => ({ ...f, departmentId: e.target.value }))}
              >
                <option value="">{t('admin.users.create.unassigned')}</option>
                {departments.map((dept) => (
                  <option key={dept.id} value={dept.id}>{dept.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className={styles.modalFooter}>
            <button type="button" className={styles.cancelButton} onClick={onClose}>{t('common.cancel')}</button>
            <button type="submit" className={styles.submitButton} disabled={loading}>
              {loading ? <Loader2 size={16} className={styles.spinner} /> : <CheckCircle size={16} />}
              {t('admin.users.create.submit')}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ===============================
// Bulk Create Modal
// ===============================
interface BulkCreateModalProps {
  departments: Department[];
  onClose: () => void;
  onSuccess: () => void;
  roleLabels: Record<UserRole, string>;
  t: Translator;
}

function BulkCreateModal({ departments, onClose, onSuccess, roleLabels, t }: BulkCreateModalProps) {
  const [users, setUsers] = useState<Array<{
    username: string;
    email: string;
    fullName: string;
    role: string;
    departmentId: string;
    status: 'ok' | 'error';
    error?: string;
  }>>([]);
  const [loading, setLoading] = useState(false);
  const [successCount, setSuccessCount] = useState(0);
  const [error, setError] = useState('');

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = ev.target?.result as string;
      const lines = text.split('\n').filter(l => l.trim());
      const headers = lines[0].split(',').map(h => h.trim().toLowerCase());

      const parsed = lines.slice(1).map((line, idx) => {
        const vals = line.split(',').map(v => v.trim());
        const row: typeof users[0] = {
          username: vals[headers.indexOf('username')] || '',
          email: vals[headers.indexOf('email')] || '',
          fullName: vals[headers.indexOf('fullname')] || vals[headers.indexOf('name')] || '',
          role: vals[headers.indexOf('role')] || 'USER',
          departmentId: '',
          status: 'ok',
        };

        if (!row.username || !row.email) {
          row.status = 'error';
          row.error = t('admin.users.bulk.rowError.missingFields');
        }
        if (!row.email.includes('@')) {
          row.status = 'error';
          row.error = (row.error ? row.error + '; ' : '') + t('admin.users.bulk.rowError.invalidEmail');
        }
        return row;
      });

      setUsers(parsed);
    };
    reader.readAsText(file);
  };

  const addRow = () => {
    setUsers(u => [...u, { username: '', email: '', fullName: '', role: 'USER', departmentId: '', status: 'ok' }]);
  };

  const removeRow = (idx: number) => {
    setUsers(u => u.filter((_, i) => i !== idx));
  };

  const updateRow = (idx: number, field: string, value: string) => {
    setUsers(u => u.map((row, i) => i === idx ? { ...row, [field]: value } : row));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (users.length === 0) { setError(t('admin.users.bulk.emptyList')); return; }
    const validUsers = users.filter(u => u.status === 'ok');
    if (validUsers.length === 0) { setError(t('admin.users.bulk.noValid')); return; }

    setError('');
    setLoading(true);
    try {
      const result = await api.users.bulkCreate(validUsers.map(u => ({
        username: u.username,
        email: u.email,
        fullName: u.fullName,
        role: u.role,
        departmentId: u.departmentId || undefined,
      })));
      const successCount = result.successCount || 0;
      const failCount = validUsers.length - successCount;
      toast.success(`Đã tạo ${successCount} tài khoản thành công${failCount > 0 ? `. ${failCount} tài khoản thất bại.` : '.'}`);
      if (successCount > 0) onSuccess();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message :
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message || t('admin.users.bulk.failed');
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.modalOverlay} onClick={onClose}>
      <div className={`${styles.modal} ${styles.bulkModal}`} onClick={e => e.stopPropagation()}>
        <div className={styles.modalHeader}>
          <div className={styles.modalTitle}>
            <Upload size={20} />
            <h2>{t('admin.users.bulk.title')}</h2>
          </div>
          <button className={styles.modalClose} onClick={onClose}><X size={18} /></button>
        </div>
        <form onSubmit={handleSubmit} className={styles.modalBody}>
          {error && <div className={styles.errorBanner}><AlertCircle size={16} /><span>{error}</span></div>}
          {successCount > 0 && (
            <div className={styles.successBanner}>
              <CheckCircle size={16} />
              <span>{t('admin.users.bulk.success').replace('{count}', String(successCount))}</span>
            </div>
          )}

          <div className={styles.bulkInfo}>
            <p>{t('admin.users.bulk.info')} <code>username, email, fullname, role</code></p>
            <input type="file" accept=".csv" onChange={handleFileUpload} className={styles.fileInput} />
          </div>

          <div className={styles.bulkTableWrapper}>
            <table className={styles.bulkTable}>
              <thead>
                <tr>
                  <th>{t('admin.users.bulk.usernameCol')}</th>
                  <th>{t('admin.users.bulk.emailCol')}</th>
                  <th>{t('admin.users.bulk.fullNameCol')}</th>
                  <th>{t('admin.users.bulk.roleCol')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {users.map((row, idx) => (
                  <tr key={idx} className={row.status === 'error' ? styles.errorRow : ''}>
                    <td><input type="text" value={row.username} onChange={e => updateRow(idx, 'username', e.target.value)} placeholder="username" className={styles.inlineInput} /></td>
                    <td><input type="email" value={row.email} onChange={e => updateRow(idx, 'email', e.target.value)} placeholder="email@company.com" className={styles.inlineInput} /></td>
                    <td><input type="text" value={row.fullName} onChange={e => updateRow(idx, 'fullName', e.target.value)} placeholder={t('admin.users.bulk.fullNameCol')} className={styles.inlineInput} /></td>
                    <td>
                      <select value={row.role} onChange={e => updateRow(idx, 'role', e.target.value)} className={styles.inlineSelect}>
                        <option value="USER">{roleLabels[UserRole.USER]}</option>
                        <option value="MANAGER">{roleLabels[UserRole.MANAGER]}</option>
                        <option value="ADMIN">{roleLabels[UserRole.ADMIN]}</option>
                      </select>
                    </td>
                    <td><button type="button" className={styles.removeRowBtn} onClick={() => removeRow(idx)}><X size={14} /></button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {users.length === 0 && (
            <div className={styles.emptyBulk}>
              <UserPlus size={32} />
              <p>{t('admin.users.bulk.empty')}</p>
            </div>
          )}

          <div className={styles.bulkActions}>
            <button type="button" className={styles.addRowButton} onClick={addRow}><Plus size={14} /> {t('admin.users.bulk.addRow')}</button>
          </div>

          <div className={styles.modalFooter}>
            <button type="button" className={styles.cancelButton} onClick={onClose}>{t('common.close')}</button>
            <button type="submit" className={styles.submitButton} disabled={loading || users.length === 0}>
              {loading ? <Loader2 size={16} className={styles.spinner} /> : <CheckCircle size={16} />}
              {t('admin.users.create.submit').replace('{count}', String(users.filter(u => u.status === 'ok').length))}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
