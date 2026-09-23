'use client';

import React, { useCallback, useMemo } from 'react';
import {
  Building2,
  ChevronDown,
  Users,
  Edit2,
  Trash2,
  ToggleLeft,
  ToggleRight,
  ChevronsUpDown,
  ChevronsDownUp,
  UserX,
} from 'lucide-react';
import type { Department, DepartmentTreeNode } from '@/types';
import styles from './HierarchyTree.module.css';

// ============================================================================
// Types
// ============================================================================

export interface HierarchyTreeProps {
  nodes: DepartmentTreeNode[];
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onExpandAll?: () => void;
  onCollapseAll?: () => void;
  onEdit?: (dept: Department) => void;
  onDelete?: (dept: Department) => void;
  onToggleActive?: (dept: Department, e: React.MouseEvent) => void;
  onViewUsers?: (dept: Department) => void;
  renderNodeActions?: (dept: Department) => React.ReactNode;
}

// ============================================================================
// Helpers
// ============================================================================

function countDescendants(node: DepartmentTreeNode): number {
  if (!node.children || node.children.length === 0) return 0;
  return node.children.reduce((sum, child) => sum + 1 + countDescendants(child), 0);
}

function toFlatDept(node: DepartmentTreeNode): Department {
  return {
    id: node.id,
    name: node.name,
    code: node.code,
    isActive: node.isActive ?? true,
    description: node.description,
    parent: node.parent,
    userCount: node.userCount ?? 0,
    children: node.children,
    createdAt: node.createdAt,
    updatedAt: node.updatedAt,
  } as Department;
}

// ============================================================================
// TreeNode Component
// ============================================================================

interface TreeNodeProps {
  node: DepartmentTreeNode;
  depth: number;
  expanded: Set<string>;
  onToggle: (id: string) => void;
  onEdit?: (dept: Department) => void;
  onDelete?: (dept: Department) => void;
  onToggleActive?: (dept: Department, e: React.MouseEvent) => void;
  onViewUsers?: (dept: Department) => void;
  renderNodeActions?: (dept: Department) => React.ReactNode;
}

function TreeNode({
  node,
  depth,
  expanded,
  onToggle,
  onEdit,
  onDelete,
  onToggleActive,
  onViewUsers,
  renderNodeActions,
}: TreeNodeProps) {
  const hasChildren = Boolean(node.children && node.children.length > 0);
  const isExpanded = expanded.has(node.id);
  const dept = toFlatDept(node);
  const isRoot = depth === 0;
  const descendantCount = countDescendants(node);

  return (
    <div
      className={`${styles.nodeWrapper} ${isRoot ? styles.rootNode : styles.childNode}`}
    >
      <div className={`${styles.nodeCard} ${!node.isActive ? styles.inactive : ''}`}>
        <div className={styles.cardHeader}>
          {/* Toggle Button */}
          {hasChildren ? (
            <button
              className={`${styles.toggleBtn} ${styles.hasChildren} ${isExpanded ? styles.expanded : ''}`}
              onClick={() => onToggle(node.id)}
              title={isExpanded ? 'Thu gọn' : 'Mở rộng'}
            >
              <ChevronDown size={16} />
            </button>
          ) : (
            <div className={styles.toggleBtn} />
          )}

          {/* Department Icon */}
          <div className={`${styles.deptIcon} ${!node.isActive ? styles.inactiveIcon : isRoot ? styles.rootIcon : styles.childIcon}`}>
            <Building2 size={isRoot ? 18 : 16} />
          </div>

          {/* Info */}
          <div className={styles.nodeInfo}>
            <div className={styles.nodeNameRow}>
              <span className={`${styles.nodeName} ${!node.isActive ? styles.inactiveText : ''}`}>
                {node.name}
              </span>
              {node.code && (
                <span className={styles.nodeCode}>{node.code}</span>
              )}
            </div>
            <div className={styles.nodeMeta}>
              {hasChildren && (
                <span className={`${styles.childBadge} ${isExpanded ? styles.childBadgeExpanded : ''}`}>
                  <Building2 size={10} />
                  {descendantCount} {descendantCount === 1 ? 'phòng con' : 'phòng con'}
                </span>
              )}
              {node.userCount !== undefined && node.userCount > 0 && (
                <span className={styles.userCountBadge}>
                  <Users size={10} />
                  {node.userCount} nhân viên
                </span>
              )}
              {node.description && (
                <span className={styles.nodeDesc}>{node.description}</span>
              )}
            </div>
          </div>

          {/* Status */}
          <div className={styles.statusWrapper}>
            <div className={`${styles.statusDot} ${node.isActive ? styles.statusActive : styles.statusInactive}`} />
            <span className={`${styles.statusLabel} ${node.isActive ? styles.statusLabelActive : styles.statusLabelInactive}`}>
              {node.isActive ? 'Hoạt động' : 'Tắt'}
            </span>
          </div>

          {/* Actions */}
          <div className={styles.cardActions}>
            {onToggleActive && (
              <button
                className={`${styles.actionBtn} ${node.isActive ? styles.actionSuccess : ''}`}
                onClick={(e) => onToggleActive(dept, e)}
                title={node.isActive ? 'Tắt hoạt động' : 'Bật hoạt động'}
              >
                {node.isActive ? <ToggleRight size={15} /> : <ToggleLeft size={15} />}
              </button>
            )}
            {onViewUsers && (
              <button
                className={styles.actionBtn}
                onClick={() => onViewUsers(dept)}
                title="Xem nhân viên"
              >
                <Users size={14} />
              </button>
            )}
            {onEdit && (
              <button
                className={styles.actionBtn}
                onClick={() => onEdit(dept)}
                title="Chỉnh sửa"
              >
                <Edit2 size={14} />
              </button>
            )}
            {onDelete && (
              <button
                className={`${styles.actionBtn} ${styles.actionDanger}`}
                onClick={() => onDelete(dept)}
                title="Xóa"
                disabled={(node.userCount ?? 0) > 0}
              >
                <Trash2 size={14} />
              </button>
            )}
            {renderNodeActions && renderNodeActions(dept)}
          </div>
        </div>

        {/* Children */}
        {hasChildren && isExpanded && node.children && (
          <div className={styles.childrenContainer}>
            {node.children.map((child) => (
              <TreeNode
                key={child.id}
                node={child}
                depth={depth + 1}
                expanded={expanded}
                onToggle={onToggle}
                onEdit={onEdit}
                onDelete={onDelete}
                onToggleActive={onToggleActive}
                onViewUsers={onViewUsers}
                renderNodeActions={renderNodeActions}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================================================
// Main Component
// ============================================================================

export function HierarchyTreeView({
  nodes,
  expanded,
  onToggle,
  onExpandAll,
  onCollapseAll,
  onEdit,
  onDelete,
  onToggleActive,
  onViewUsers,
  renderNodeActions,
}: HierarchyTreeProps) {
  const handleExpandAll = useCallback(() => {
    onExpandAll?.();
  }, [onExpandAll]);

  const handleCollapseAll = useCallback(() => {
    onCollapseAll?.();
  }, [onCollapseAll]);

  if (nodes.length === 0) {
    return (
      <div className={styles.container}>
        <div className={styles.empty}>
          <div className={styles.emptyIcon}>
            <Building2 size={32} />
          </div>
          <p>Không có phòng ban nào</p>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* Toolbar */}
      <div className={styles.toolbar}>
        <span className={styles.toolbarLabel}>
          <Building2 size={16} />
          Cây phân cấp tổ chức
        </span>
        <div className={styles.toolbarActions}>
          <button
            className={styles.toolbarBtn}
            onClick={handleExpandAll}
            title="Mở rộng tất cả"
          >
            <ChevronsUpDown size={14} />
            Mở rộng tất cả
          </button>
          <button
            className={styles.toolbarBtn}
            onClick={handleCollapseAll}
            title="Thu gọn tất cả"
          >
            <ChevronsDownUp size={14} />
            Thu gọn tất cả
          </button>
        </div>
      </div>

      {/* Tree */}
      <div className={styles.tree}>
        <div className={styles.treeContent}>
          {nodes.map((node) => (
            <TreeNode
              key={node.id}
              node={node}
              depth={0}
              expanded={expanded}
              onToggle={onToggle}
              onEdit={onEdit}
              onDelete={onDelete}
              onToggleActive={onToggleActive}
              onViewUsers={onViewUsers}
              renderNodeActions={renderNodeActions}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

export default HierarchyTreeView;
