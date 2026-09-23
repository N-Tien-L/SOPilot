'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Building2, Plus, Search, Edit2, Trash2, X, Loader2,
  ChevronLeft, ChevronRight, AlertCircle, CheckCircle,
  ToggleLeft, ToggleRight, Users, LayoutGrid, TreeDeciduous,
  UserPlus, ArrowRight, UserCheck2, UserMinus,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useIsAdmin } from '@/store';
import { useLanguage } from '@/providers';
import { useRouter } from 'next/navigation';
import { HierarchyTreeView } from '@/components/hierarchy-tree/HierarchyTreeView';
import type {
  Department,
  DepartmentTreeNode,
  CreateDepartmentRequest,
  UpdateDepartmentRequest,
  AssignUserDepartmentRequest,
} from '@/types';
import styles from './departments.module.css';

type ViewMode = 'grid' | 'tree';
type ModalMode = 'create' | 'edit' | 'delete' | 'users' | 'assign';

// ============================================================================
// Types
// ============================================================================

interface DepartmentFormData {
  name: string;
  code: string;
  description: string;
  parentId: string;
}

const EMPTY_FORM: DepartmentFormData = { name: '', code: '', description: '', parentId: '' };

/** Represents a user returned by the user-search and department-users endpoints */
interface DeptUser {
  id: string;
  username: string;
  email: string;
  role: string;
  status: string;
  fullName?: string;
  departmentId?: string | null;
  department?: string | null;
}

// ============================================================================
// Main Page Component
// ============================================================================

export default function DepartmentsPage() {
  const isAdmin = useIsAdmin();
  const router = useRouter();
  const { t } = useLanguage();

  const [departments, setDepartments] = useState<Department[]>([]);
  const [treeData, setTreeData] = useState<DepartmentTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [childCount, setChildCount] = useState(0);

  // Modal state
  const [modalMode, setModalMode] = useState<ModalMode | null>(null);
  const [selectedDept, setSelectedDept] = useState<Department | null>(null);
  const [formData, setFormData] = useState<DepartmentFormData>(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [formSuccess, setFormSuccess] = useState('');
  const [formLoading, setFormLoading] = useState(false);

  // Tree expanded state
  const [expandedTree, setExpandedTree] = useState<Set<string>>(new Set());

  // Users modal state
  const [deptUsers, setDeptUsers] = useState<DeptUser[]>([]);
  const [usersLoading, setUsersLoading] = useState(false);
  const [usersPage, setUsersPage] = useState(1);
  const [usersTotalPages, setUsersTotalPages] = useState(1);

  // Assign user state
  const [assignSearch, setAssignSearch] = useState('');
  const [assignResults, setAssignResults] = useState<DeptUser[]>([]);
  const [assignLoading, setAssignLoading] = useState(false);
  const [assignedUser, setAssignedUser] = useState<DeptUser | null>(null);
  const [assignError, setAssignError] = useState('');
  const [assignLoadingSubmit, setAssignLoadingSubmit] = useState(false);
  const [unassignedUsers, setUnassignedUsers] = useState<DeptUser[]>([]);

  // ============================================================================
  // Load Data
  // ============================================================================

  const loadDepartments = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.departments.getAll({
        page: page - 1,
        limit: 12,
        sortBy: 'name',
        sortDir: 'ASC',
      });
      console.log('[Departments] Loaded:', result.data.length, 'items, pagination:', result.pagination);
      setDepartments(result.data);
      setTotalPages(result.pagination.totalPages);
      setTotalCount(result.pagination.total);
      const activeDepts = result.data.filter(d => d.isActive);
      setActiveCount(activeDepts.length);
    } catch (err) {
      console.error('Lỗi khi tải phòng ban:', err);
    } finally {
      setLoading(false);
    }
  }, [page]);

  const loadTree = useCallback(async () => {
    try {
      const tree = await api.departments.getTree();
      setTreeData(tree);
      let childrenCount = 0;
      tree.forEach(node => {
        if (node.children && node.children.length > 0) childrenCount += node.children.length;
      });
      setChildCount(childrenCount);
      const allIds = new Set<string>();
      tree.forEach(n => collectIds(n, allIds));
      setExpandedTree(allIds);
    } catch (err) {
      console.error('Lỗi khi tải cây phòng ban:', err);
    }
  }, []);

function collectIds(node: DepartmentTreeNode, set: Set<string>) {
  if (node.children && node.children.length > 0) {
    set.add(node.id);
    node.children.forEach(c => collectIds(c, set));
  }
}

function collectAllIds(nodes: DepartmentTreeNode[], ids = new Set<string>()): Set<string> {
  for (const node of nodes) {
    if (node.children && node.children.length > 0) {
      ids.add(node.id);
      collectAllIds(node.children, ids);
    }
  }
  return ids;
}

  useEffect(() => {
    if (!isAdmin) {
      router.push('/');
      return;
    }
    loadDepartments();
    loadTree();
  }, [isAdmin, router, loadDepartments, loadTree]);

  // ============================================================================
  // Search
  // ============================================================================

  const filteredGrid = departments.filter(dept =>
    dept.name.toLowerCase().includes(search.toLowerCase()) ||
    dept.code.toLowerCase().includes(search.toLowerCase()) ||
    (dept.description?.toLowerCase() || '').includes(search.toLowerCase())
  );

  // ============================================================================
  // CRUD Handlers
  // ============================================================================

  const openCreateModal = () => {
    setFormData(EMPTY_FORM);
    setFormError('');
    setFormSuccess('');
    setModalMode('create');
  };

  const openEditModal = (dept: Department) => {
    setSelectedDept(dept);
    setFormData({
      name: dept.name,
      code: dept.code,
      description: dept.description || '',
      parentId: dept.parent?.id || '',
    });
    setFormError('');
    setFormSuccess('');
    setModalMode('edit');
  };

  const openDeleteModal = (dept: Department) => {
    setSelectedDept(dept);
    setFormError('');
    setFormSuccess('');
    setModalMode('delete');
  };

  const handleCreate = async () => {
    if (!formData.name.trim() || !formData.code.trim()) return;
    setFormLoading(true);
    setFormError('');
    try {
      await api.departments.create({
        name: formData.name.trim(),
        code: formData.code.trim().toUpperCase(),
        description: formData.description.trim() || undefined,
        parentId: formData.parentId || undefined,
      } as CreateDepartmentRequest);
      setFormSuccess(t('admin.depts.form.success.create'));
      setTimeout(() => {
        setModalMode(null);
        loadDepartments();
        loadTree();
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || t('admin.depts.form.failed.create');
      setFormError(msg);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedDept || !formData.name.trim()) return;
    setFormLoading(true);
    setFormError('');
    try {
      await api.departments.update(selectedDept.id, {
        name: formData.name.trim(),
        description: formData.description.trim() || undefined,
        parentId: formData.parentId || undefined,
      } as UpdateDepartmentRequest);
      setFormSuccess(t('admin.depts.form.success.update'));
      setTimeout(() => {
        setModalMode(null);
        loadDepartments();
        loadTree();
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || t('admin.depts.form.failed.update');
      setFormError(msg);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedDept) return;
    setFormLoading(true);
    setFormError('');
    try {
      await api.departments.delete(selectedDept.id);
      setFormSuccess(t('admin.depts.form.success.delete') || 'Xóa phòng ban thành công!');
      setTimeout(() => {
        setModalMode(null);
        loadDepartments();
        loadTree();
      }, 1200);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || t('admin.depts.delete.failed');
      setFormError(msg);
    } finally {
      setFormLoading(false);
    }
  };

  const handleToggleActive = async (dept: Department, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await api.departments.update(dept.id, { isActive: !dept.isActive });
      loadDepartments();
    } catch (err) {
      console.error('Lỗi khi thay đổi trạng thái:', err);
    }
  };

  const toggleTreeNode = (id: string) => {
    setExpandedTree(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // ============================================================================
  // Users Modal
  // ============================================================================

  const openUsersModal = async (dept: Department) => {
    setSelectedDept(dept);
    setModalMode('users');
    setUsersPage(1);
    setDeptUsers([]);
    await loadDeptUsers(dept.id, 1);
  };

  const loadDeptUsers = async (deptId: string, pg: number) => {
    setUsersLoading(true);
    try {
      const result = await api.departments.getUsers(deptId, { page: pg - 1, limit: 10 });
      const users: DeptUser[] = result.data.map(u => ({
        id: u.id,
        username: u.username,
        email: u.email,
        role: u.role,
        status: u.status,
        fullName: u.fullName,
        departmentId: u.departmentId,
        department: u.department?.name ?? null,
      }));
      setDeptUsers(users);
      setUsersTotalPages(result.pagination.totalPages);
    } catch (err) {
      console.error('Lỗi khi tải nhân viên:', err);
    } finally {
      setUsersLoading(false);
    }
  };

  const openAssignModal = async (dept: Department) => {
    setSelectedDept(dept);
    setModalMode('assign');
    setAssignSearch('');
    setAssignResults([]);
    setAssignedUser(null);
    setAssignError('');
    
    // Load unassigned users immediately when modal opens
    await loadUnassignedUsers();
  };

  const loadUnassignedUsers = async () => {
    setAssignLoading(true);
    try {
      // Get all users and filter by unassigned (no departmentId)
      const result = await api.users.search({ keyword: '', limit: 100 });
      const users: DeptUser[] = result.data.map(u => ({
        id: u.id,
        username: u.username,
        email: u.email,
        role: u.role,
        status: u.status,
        fullName: u.fullName,
        departmentId: u.departmentId,
        department: u.department?.name ?? null,
      }));
      // Filter to only unassigned users
      const unassigned = users.filter(u => !u.departmentId);
      setUnassignedUsers(unassigned);
      setAssignResults(unassigned); // Initialize results with unassigned users
    } catch {
      setUnassignedUsers([]);
      setAssignResults([]);
    } finally {
      setAssignLoading(false);
    }
  };

  const handleAssignUserSearch = useCallback((value: string) => {
    setAssignSearch(value);
    setAssignError('');
    
    if (!value.trim()) {
      // Show all unassigned users when search is empty
      setAssignResults(unassignedUsers);
      return;
    }
    
    // Search through unassigned users locally
    const searchLower = value.toLowerCase();
    const filtered = unassignedUsers.filter(u => 
      (u.fullName?.toLowerCase() || '').includes(searchLower) ||
      u.username.toLowerCase().includes(searchLower) ||
      u.email.toLowerCase().includes(searchLower)
    );
    setAssignResults(filtered);
  }, [unassignedUsers]);

  const handleAssignUser = async () => {
    if (!assignedUser || !selectedDept) return;
    setAssignLoadingSubmit(true);
    setAssignError('');
    try {
      await api.departments.assignUser({
        userId: assignedUser.id,
        departmentId: selectedDept.id,
      } as AssignUserDepartmentRequest);
      
      // Remove assigned user from unassigned list
      setUnassignedUsers(prev => prev.filter(u => u.id !== assignedUser.id));
      setAssignedUser(null);
      setAssignResults([]);
      setAssignSearch('');
      setAssignError('');
      await loadDeptUsers(selectedDept.id, usersPage);
      loadDepartments();
      loadTree();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || t('admin.depts.users.assignFailed');
      setAssignError(msg);
    } finally {
      setAssignLoadingSubmit(false);
    }
  };

  const handleRemoveUserFromDept = async (userId: string) => {
    if (!selectedDept) return;
    
    // Remove user from department (set departmentId to null)
    try {
      await api.departments.assignUser({
        userId: userId,
        departmentId: null as unknown as string, // null to remove from department
      } as AssignUserDepartmentRequest);
      
      // Reload the user list
      await loadDeptUsers(selectedDept.id, usersPage);
      loadDepartments();
      loadTree();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message
        : (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || 'Không thể xóa nhân viên khỏi phòng ban';
      alert(msg);
    }
  };

  // ============================================================================
  // Render helpers
  // ============================================================================

  function getUserInitial(user: DeptUser) {
    return (user.fullName || user.username || 'U').charAt(0).toUpperCase();
  }

  function getRoleClass(role?: string) {
    switch (role?.toUpperCase()) {
      case 'ADMIN': return styles.admin;
      case 'MANAGER': return styles.manager;
      case 'USER': return styles.user;
      default: return styles.unknown;
    }
  }

  function getStatusClass(status?: string) {
    switch (status?.toUpperCase()) {
      case 'ACTIVE': return styles.active;
      case 'DEACTIVATED': return styles.deactivated;
      case 'REVOKED': return styles.revoked;
      default: return '';
    }
  }

  // ============================================================================
  // Render
  // ============================================================================

  return (
    <div className={styles.container}>

        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerLeft}>
            <h1>{t('admin.depts.title')}</h1>
            <p>{t('admin.depts.subtitle')}</p>
          </div>
          <div className={styles.headerActions}>
            <button className={styles.createBtn} onClick={openCreateModal}>
              <Plus size={16} />
              {t('admin.depts.create')}
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className={styles.statsRow}>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.purple}`}>
              <Building2 size={20} />
            </div>
            <div className={styles.statContent}>
              <span className={styles.statValue}>{totalCount}</span>
              <span className={styles.statLabel}>{t('admin.depts.stats.total')}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.green}`}>
              <CheckCircle size={20} />
            </div>
            <div className={styles.statContent}>
              <span className={styles.statValue}>{activeCount}</span>
              <span className={styles.statLabel}>{t('admin.depts.status.active')}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.blue}`}>
              <TreeDeciduous size={20} />
            </div>
            <div className={styles.statContent}>
              <span className={styles.statValue}>{childCount}</span>
              <span className={styles.statLabel}>{t('admin.depts.stats.children')}</span>
            </div>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.amber}`}>
              <Users size={20} />
            </div>
            <div className={styles.statContent}>
              <span className={styles.statValue}>
                {departments.reduce((sum, d) => sum + d.userCount, 0)}
              </span>
              <span className={styles.statLabel}>{t('admin.depts.stats.staff')}</span>
            </div>
          </div>
        </div>

        {/* Toolbar */}
        <div className={styles.toolbar}>
          <div className={styles.searchWrapper}>
            <Search size={16} className={styles.searchIcon} />
            <input
              type="text"
              placeholder={t('admin.depts.search.placeholder')}
              value={search}
              onChange={e => setSearch(e.target.value)}
              className={styles.searchInput}
            />
          </div>
          <div className={styles.viewToggle}>
            <button
              className={`${styles.viewToggleBtn} ${viewMode === 'grid' ? styles.active : ''}`}
              onClick={() => setViewMode('grid')}
              title={t('admin.depts.view.grid')}
            >
              <LayoutGrid size={16} />
            </button>
            <button
              className={`${styles.viewToggleBtn} ${viewMode === 'tree' ? styles.active : ''}`}
              onClick={() => setViewMode('tree')}
              title={t('admin.depts.view.tree')}
            >
              <TreeDeciduous size={16} />
            </button>
          </div>
        </div>

        {/* Content */}
        {loading ? (
          <div className={styles.loading}>
            <Loader2 size={32} className={styles.spinner} />
            <span>{t('admin.depts.loading')}</span>
          </div>
        ) : filteredGrid.length === 0 && viewMode === 'grid' ? (
          <div className={styles.empty}>
            <div className={styles.emptyIcon}>
              <Building2 size={32} />
            </div>
            <p>{t('admin.depts.empty')}</p>
            <span className={styles.emptySub}>
              {search ? t('admin.depts.empty.search') : t('admin.depts.empty.start')}
            </span>
          </div>
        ) : viewMode === 'grid' ? (
          <>
            <div className={styles.grid}>
              {filteredGrid.map(dept => (
                <div key={dept.id} className={`${styles.deptCard} ${!dept.isActive ? styles.inactive : ''}`}>
                  <div className={styles.deptCardTop}>
                    <div className={`${styles.deptIcon} ${!dept.isActive ? styles.inactive : ''}`}>
                      <Building2 size={22} />
                    </div>
                    <div className={styles.deptInfo}>
                      <div className={styles.deptName}>{dept.name}</div>
                      <div className={styles.deptCode}>{dept.code}</div>
                      {dept.description && (
                        <p className={styles.deptDesc}>{dept.description}</p>
                      )}
                    </div>
                  </div>
                  <div className={styles.deptMeta}>
                    <span className={styles.deptMetaItem}>
                      <Users size={13} />
                      {dept.userCount} {t('admin.depts.stats.employees')}
                    </span>
                    {dept.parent && (
                      <span className={styles.deptParent}>
                        {t('admin.depts.parent')} {dept.parent.name}
                      </span>
                    )}
                  </div>
                  <div className={styles.deptCardFooter}>
                    <span className={`${styles.deptStatus} ${dept.isActive ? styles.active : styles.inactive}`}>
                      <span className={`${styles.statDot} ${dept.isActive ? styles.active : styles.inactive}`} />
                      {dept.isActive ? t('admin.depts.status.active') : t('admin.depts.status.inactive')}
                    </span>
                    <div className={styles.deptActions}>
                      <button
                        className={`${styles.actionBtn} ${dept.isActive ? styles.success : ''}`}
                        onClick={e => handleToggleActive(dept, e)}
                        title={dept.isActive ? t('admin.depts.turnOff') : t('admin.depts.turnOn')}
                      >
                        {dept.isActive ? <ToggleRight size={16} /> : <ToggleLeft size={16} />}
                      </button>
                      <button
                        className={styles.actionBtn}
                        onClick={() => openUsersModal(dept)}
                        title={t('admin.depts.employees')}
                      >
                        <Users size={15} />
                      </button>
                      <button
                        className={styles.actionBtn}
                        onClick={() => openEditModal(dept)}
                        title={t('admin.depts.edit')}
                      >
                        <Edit2 size={15} />
                      </button>
                      <button
                        className={`${styles.actionBtn} ${styles.danger}`}
                        onClick={() => openDeleteModal(dept)}
                        title={t('admin.depts.delete')}
                        disabled={dept.userCount > 0}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className={styles.paginationWrapper}>
                <span className={styles.paginationInfo}>
                  {t('admin.depts.pagination').replace('{page}', String(page)).replace('{totalPages}', String(totalPages)).replace('{total}', String(totalCount))}
                </span>
                <div style={{ display: 'flex', gap: '0.25rem' }}>
                  <button
                    className={styles.pageBtn}
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    className={styles.pageBtn}
                    disabled={page === totalPages}
                    onClick={() => setPage(p => p + 1)}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <>
            {/* Hierarchy Tree View */}
            <div className={styles.treeView}>
              <HierarchyTreeView
                nodes={treeData}
                expanded={expandedTree}
                onToggle={toggleTreeNode}
                onExpandAll={() => {
                  const allIds = new Set<string>();
                  collectAllIds(treeData, allIds);
                  setExpandedTree(allIds);
                }}
                onCollapseAll={() => setExpandedTree(new Set())}
                onEdit={(dept) => openEditModal(dept)}
                onDelete={(dept) => openDeleteModal(dept)}
                onToggleActive={handleToggleActive}
                onViewUsers={openUsersModal}
              />
            </div>
          </>
        )}

        {/* ================================================================ */}
        {/* CREATE / EDIT MODAL */}
        {/* ================================================================ */}
        {(modalMode === 'create' || modalMode === 'edit') && (
          <div className={styles.modalOverlay} onClick={() => !formLoading && setModalMode(null)}>
            <div className={styles.modal} onClick={e => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div className={styles.modalTitleGroup}>
                  <div className={styles.modalTitleIcon}>
                    <Building2 size={18} />
                  </div>
                  <h2 className={styles.modalTitle}>
                    {modalMode === 'create' ? t('admin.depts.create.title') : t('admin.depts.edit.title')}
                  </h2>
                </div>
                <button className={styles.modalClose} onClick={() => setModalMode(null)}>
                  <X size={18} />
                </button>
              </div>

              <div className={styles.modalBody}>
                {formError && (
                  <div className={styles.errorBanner}>
                    <AlertCircle size={16} />
                    {formError}
                  </div>
                )}
                {formSuccess && (
                  <div className={styles.successBanner}>
                    <CheckCircle size={16} />
                    {formSuccess}
                  </div>
                )}

                <div className={styles.formGrid}>
                  <div className={styles.formGroup}>
                    <label>{t('admin.depts.form.name.required')}</label>
                    <input
                      type="text"
                      value={formData.name}
                      onChange={e => setFormData(f => ({ ...f, name: e.target.value }))}
                      placeholder={t('admin.depts.form.name.placeholder')}
                      disabled={formLoading}
                    />
                  </div>

                  <div className={styles.formGroup}>
                    <label>{t('admin.depts.form.code.required')}</label>
                    <input
                      type="text"
                      value={formData.code}
                      onChange={e => setFormData(f => ({ ...f, code: e.target.value.toUpperCase() }))}
                      placeholder={t('admin.depts.form.code.placeholder')}
                      disabled={formLoading}
                      style={{ fontFamily: 'monospace', textTransform: 'uppercase' }}
                    />
                    <span className={styles.formHint}>{t('admin.depts.form.code.hint')}</span>
                  </div>

                  <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                    <label>{t('admin.depts.form.description')}</label>
                    <textarea
                      value={formData.description}
                      onChange={e => setFormData(f => ({ ...f, description: e.target.value }))}
                      placeholder={t('admin.depts.form.description.placeholder')}
                      rows={2}
                      disabled={formLoading}
                    />
                  </div>

                  <div className={`${styles.formGroup} ${styles.fullWidth}`}>
                    <label>{t('admin.depts.form.parent')}</label>
                    <select
                      value={formData.parentId}
                      onChange={e => setFormData(f => ({ ...f, parentId: e.target.value }))}
                      disabled={formLoading}
                    >
                      <option value="">{t('admin.depts.form.parent.none')}</option>
                      {departments
                        .filter(d => d.id !== selectedDept?.id && d.isActive)
                        .map(dept => (
                          <option key={dept.id} value={dept.id}>
                            {dept.name} ({dept.code})
                          </option>
                        ))}
                    </select>
                    <span className={styles.formHint}>{t('admin.depts.form.parent.hint')}</span>
                  </div>
                </div>
              </div>

              <div className={styles.modalFooter}>
                <button
                  className={styles.cancelBtn}
                  onClick={() => setModalMode(null)}
                  disabled={formLoading}
                >
                  {t('common.cancel')}
                </button>
                <button
                  className={styles.submitBtn}
                  onClick={modalMode === 'create' ? handleCreate : handleUpdate}
                  disabled={formLoading || !formData.name.trim() || !formData.code.trim()}
                >
                  {formLoading ? <Loader2 size={16} className={styles.spinner} /> : <CheckCircle size={16} />}
                  {modalMode === 'create' ? t('admin.depts.form.submit.create') : t('admin.depts.form.submit.update')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* DELETE MODAL */}
        {/* ================================================================ */}
        {modalMode === 'delete' && (
          <div className={styles.modalOverlay} onClick={() => !formLoading && setModalMode(null)}>
            <div className={styles.modal} onClick={e => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div className={styles.modalTitleGroup}>
                  <div className={styles.modalTitleIcon} style={{ background: 'rgba(220, 38, 38, 0.1)', color: '#dc2626' }}>
                    <AlertCircle size={18} />
                  </div>
                  <h2 className={styles.modalTitle}>{t('admin.depts.delete.title')}</h2>
                </div>
                <button className={styles.modalClose} onClick={() => setModalMode(null)}>
                  <X size={18} />
                </button>
              </div>
              <div className={styles.modalBody}>
                {formError && (
                  <div className={styles.errorBanner}>
                    <AlertCircle size={16} />
                    {formError}
                  </div>
                )}
                {formSuccess && (
                  <div className={styles.successBanner}>
                    <CheckCircle size={16} />
                    {formSuccess}
                  </div>
                )}
                <p style={{ margin: '0 0 0.5rem', color: 'var(--foreground)' }}>
                  {t('admin.depts.delete.confirm').replace('{name}', selectedDept?.name || '').replace('{code}', selectedDept?.code || '')}
                </p>
                <p className={styles.warningText}>
                  {t('admin.depts.delete.warning')}
                </p>
              </div>
              <div className={styles.modalFooter}>
                <button
                  className={styles.cancelBtn}
                  onClick={() => setModalMode(null)}
                  disabled={formLoading}
                >
                  {t('common.cancel')}
                </button>
                <button
                  className={styles.deleteBtn}
                  onClick={handleDelete}
                  disabled={formLoading}
                >
                  {formLoading ? <Loader2 size={16} className={styles.spinner} /> : <Trash2 size={16} />}
                  {t('admin.depts.delete.submit')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* USERS MODAL */}
        {/* ================================================================ */}
        {modalMode === 'users' && (
          <div className={styles.modalOverlay} onClick={() => setModalMode(null)}>
            <div className={`${styles.modal} ${styles.large}`} onClick={e => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div className={styles.modalTitleGroup}>
                  <div className={styles.modalTitleIcon}>
                    <Users size={18} />
                  </div>
                  <div>
                    <h2 className={styles.modalTitle}>{t('admin.depts.users.title')}</h2>
                    <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--muted-foreground)' }}>
                      {selectedDept?.name} ({selectedDept?.code})
                    </p>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: '0.375rem', marginRight: 'auto', marginLeft: '1rem' }}>
                  <button
                    className={styles.assignBtn}
                    onClick={() => openAssignModal(selectedDept!)}
                  >
                    <UserPlus size={14} />
                    {t('admin.depts.users.assign')}
                  </button>
                </div>
                <button className={styles.modalClose} onClick={() => setModalMode(null)}>
                  <X size={18} />
                </button>
              </div>
              <div className={styles.modalBody}>
                {usersLoading ? (
                  <div className={styles.loading}>
                    <Loader2 size={24} className={styles.spinner} />
                    <span>{t('admin.depts.users.loading')}</span>
                  </div>
                ) : deptUsers.length === 0 ? (
                  <div className={styles.empty}>
                    <Users size={40} />
                    <p>{t('admin.depts.users.empty')}</p>
                    <button
                      className={styles.assignBtn}
                      style={{ marginTop: '0.5rem' }}
                      onClick={() => openAssignModal(selectedDept!)}
                    >
                      <UserPlus size={14} />
                      {t('admin.depts.users.assignFirst')}
                    </button>
                  </div>
                ) : (
                  <>
                    <div className={styles.usersSectionHeader}>
                      <span className={styles.usersSectionTitle}>{t('admin.depts.users.list')}</span>
                      <span className={styles.usersSectionCount}>{t('admin.depts.users.count').replace('{count}', String(deptUsers.length))}</span>
                    </div>
                    <div className={styles.usersList}>
                      {deptUsers.map(user => (
                        <div key={user.id} className={styles.userItem}>
                          <div className={styles.userAvatar}>{getUserInitial(user)}</div>
                          <div className={styles.userInfo}>
                            <div className={styles.userName}>{user.fullName || user.username}</div>
                            <div className={styles.userEmail}>{user.email}</div>
                          </div>
                          <div className={styles.userMeta}>
                            <span className={`${styles.userRoleBadge} ${getRoleClass(user.role)}`}>
                              {user.role}
                            </span>
                            <span className={`${styles.userStatusBadge} ${getStatusClass(user.status)}`}>
                              {user.status}
                            </span>
                          </div>
                          <button
                            className={styles.removeUserBtn}
                            onClick={() => handleRemoveUserFromDept(user.id)}
                            title="Xóa khỏi phòng ban"
                          >
                            <UserMinus size={14} />
                          </button>
                        </div>
                      ))}
                    </div>
                    {usersTotalPages > 1 && (
                      <div className={styles.usersListPagination}>
                        <span className={styles.usersListPaginationInfo}>
                          {t('admin.depts.users.pagination').replace('{page}', String(usersPage)).replace('{totalPages}', String(usersTotalPages))}
                        </span>
                        <div className={styles.usersListPaginationBtns}>
                          <button
                            className={styles.pageBtn}
                            disabled={usersPage === 1}
                            onClick={() => { const p = usersPage - 1; setUsersPage(p); loadDeptUsers(selectedDept!.id, p); }}
                          >
                            <ChevronLeft size={14} />
                          </button>
                          <button
                            className={styles.pageBtn}
                            disabled={usersPage === usersTotalPages}
                            onClick={() => { const p = usersPage + 1; setUsersPage(p); loadDeptUsers(selectedDept!.id, p); }}
                          >
                            <ChevronRight size={14} />
                          </button>
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
              <div className={styles.modalFooter}>
                <button className={styles.cancelBtn} onClick={() => setModalMode(null)}>
                  {t('common.close')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================ */}
        {/* ASSIGN USER MODAL */}
        {/* ================================================================ */}
        {modalMode === 'assign' && (
          <div className={styles.modalOverlay} onClick={() => setModalMode(null)}>
            <div className={`${styles.modal} ${styles.large}`} onClick={e => e.stopPropagation()}>
              <div className={styles.modalHeader}>
                <div className={styles.modalTitleGroup}>
                  <div className={styles.modalTitleIcon}>
                    <UserPlus size={18} />
                  </div>
                  <div>
                    <h2 className={styles.modalTitle}>{t('admin.depts.users.assignTitle')}</h2>
                    <p style={{ margin: 0, fontSize: '0.8125rem', color: 'var(--muted-foreground)' }}>
                      {t('admin.depts.users.assignTo').replace('{name}', selectedDept?.name || '')}
                    </p>
                  </div>
                </div>
                <button className={styles.modalClose} onClick={() => setModalMode(null)}>
                  <X size={18} />
                </button>
              </div>
              <div className={`${styles.modalBody} ${styles.assignModalBody}`}>
                {assignError && (
                  <div className={styles.errorBanner}>
                    <AlertCircle size={16} />
                    {assignError}
                  </div>
                )}

                {assignedUser ? (
                  <div className={styles.assignResultCard}>
                    <div className={styles.assignResultAvatar}>{getUserInitial(assignedUser)}</div>
                    <div className={styles.assignResultInfo}>
                      <div className={styles.assignResultName}>{assignedUser.fullName || assignedUser.username}</div>
                      <div className={styles.assignResultEmail}>{assignedUser.email}</div>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span className={styles.assignResultBadge}>{t('admin.depts.users.willAssign')}</span>
                      <button
                        className={styles.actionBtn}
                        style={{ border: '1px solid var(--border)', width: '1.75rem', height: '1.75rem', display: 'flex', alignItems: 'center', justifyContent: 'center', borderRadius: '0.25rem', background: 'transparent', cursor: 'pointer' }}
                        onClick={() => setAssignedUser(null)}
                        title={t('admin.depts.users.cancelSelect')}
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </div>
                ) : (
                  <>
                    {/* Search Input */}
                    <div className={styles.usersSearchWrapper}>
                      <Search size={15} className={styles.usersSearchIcon} />
                      <input
                        type="text"
                        className={styles.usersSearchInput}
                        placeholder={t('admin.depts.users.search.placeholder')}
                        value={assignSearch}
                        onChange={e => handleAssignUserSearch(e.target.value)}
                        autoFocus
                      />
                      {assignLoading && (
                        <Loader2
                          size={15}
                          className={styles.spinner}
                          style={{ position: 'absolute', right: '0.75rem', top: '50%', transform: 'translateY(-50%)' }}
                        />
                      )}
                    </div>

                    {/* User List */}
                    {assignLoading ? (
                      <div className={styles.loading} style={{ padding: '2rem' }}>
                        <Loader2 size={24} className={styles.spinner} />
                        <span>Đang tải...</span>
                      </div>
                    ) : unassignedUsers.length === 0 ? (
                      <div className={styles.empty} style={{ padding: '2rem' }}>
                        <Users size={32} />
                        <p>Không có nhân viên nào chưa có phòng ban</p>
                      </div>
                    ) : (
                      <div className={styles.userListContainer}>
                        <div className={styles.userListHeader}>
                          {!assignSearch.trim() 
                            ? `${unassignedUsers.length} nhân viên chưa có phòng ban`
                            : `${assignResults.length} kết quả tìm kiếm`}
                        </div>
                        {(assignSearch.trim() ? assignResults : unassignedUsers).map(user => (
                          <div
                            key={user.id}
                            className={styles.searchDropdownItem}
                            onClick={() => {
                              setAssignedUser(user);
                              setAssignSearch(user.fullName || user.username || '');
                            }}
                          >
                            <div className={styles.userAvatar}>{getUserInitial(user)}</div>
                            <div className={styles.userInfo}>
                              <div className={styles.userName}>{user.fullName || user.username}</div>
                              <div className={styles.userEmail}>{user.email}</div>
                            </div>
                            <span className={`${styles.userRoleBadge} ${getRoleClass(user.role)}`} style={{ fontSize: '0.6875rem' }}>
                              {user.role}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </>
                )}

                {assignedUser && (
                  <div style={{ marginTop: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                      <UserCheck2 size={16} style={{ color: '#059669' }} />
                      <span style={{ fontSize: '0.875rem', fontWeight: 500 }}>
                        {t('admin.depts.users.selected')} <strong>{assignedUser.fullName || assignedUser.username}</strong>
                      </span>
                    </div>
                    <div style={{ fontSize: '0.8125rem', color: 'var(--muted-foreground)', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                      <span>{t('admin.depts.users.assignEmail')}</span>
                      <span>{assignedUser.email}</span>
                      <span style={{ margin: '0 0.25rem' }}>•</span>
                      <span>{t('admin.depts.users.assignRole')}</span>
                      <span className={`${styles.userRoleBadge} ${getRoleClass(assignedUser.role)}`}>
                        {assignedUser.role}
                      </span>
                    </div>
                    {assignedUser.departmentId && (
                      <div style={{ fontSize: '0.8125rem', color: 'var(--muted-foreground)', marginTop: '0.25rem', display: 'flex', alignItems: 'center', gap: '0.375rem' }}>
                        <span style={{ color: '#d97706' }}>
                          {t('admin.depts.users.warningTransfer')}
                        </span>
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div className={styles.modalFooter}>
                <button className={styles.cancelBtn} onClick={() => setModalMode(null)}>
                  {t('common.cancel')}
                </button>
                <button
                  className={styles.confirmAssignBtn}
                  onClick={handleAssignUser}
                  disabled={!assignedUser || assignLoadingSubmit}
                >
                  {assignLoadingSubmit ? (
                    <Loader2 size={16} className={styles.spinner} />
                  ) : (
                    <CheckCircle size={16} />
                  )}
                  {t('admin.depts.users.confirm')}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
  );
}
