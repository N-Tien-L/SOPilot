'use client';

import React, { useState, useEffect } from 'react';
import {
  Plus,
  Edit,
  Trash2,
  ChevronRight,
  ChevronDown,
  Loader2,
  AlertCircle,
  Search,
  FolderOpen,
  ArrowLeft,
} from 'lucide-react';
import {
  categoryService,
} from '@/services/document.service';
import type { Category, CategoryTree } from '@/types/document';
import { IconPicker, getIconByName } from '@/components/common/IconPicker';
import { useLanguage } from '@/providers';
import { Translator } from '@/lib/i18n';

export default function CategoriesPage() {
  const { t } = useLanguage();

  const [categories, setCategories] = useState<Category[]>([]);
  const [categoryTree, setCategoryTree] = useState<CategoryTree[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingCategory, setEditingCategory] = useState<Category | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadCategories();
  }, []);

  const loadCategories = async () => {
    setLoading(true);
    try {
      const [cats, tree] = await Promise.all([
        categoryService.getCategories(),
        categoryService.getCategoryTree(),
      ]);
      setCategories(cats);
      setCategoryTree(tree);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const toggleExpanded = (id: string) => {
    const newExpanded = new Set(expandedIds);
    if (newExpanded.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedIds(newExpanded);
  };

  const handleDelete = async (category: Category) => {
    if (!confirm(t('admin.categories.confirm.delete').replace('{name}', category.name))) return;
    try {
      await categoryService.deleteCategory(category.id);
      loadCategories();
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleEdit = (category: Category) => {
    setEditingCategory(category);
    setShowModal(true);
  };

  const handleCreate = () => {
    setEditingCategory(null);
    setShowModal(true);
  };

  const handleSuccess = () => {
    setShowModal(false);
    setEditingCategory(null);
    loadCategories();
  };

  const filteredTree = searchQuery
    ? flattenTree(categoryTree).filter(
        (c) => c.name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : categoryTree;

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="w-8 h-8 text-primary animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <div className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{t('admin.categories.title')}</h1>
              <p className="mt-1 text-sm text-muted-foreground">
                {t('admin.categories.count').replace('{count}', String(categories.length))}
              </p>
            </div>
            <button
              onClick={handleCreate}
              className="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-primary-foreground bg-primary hover:bg-primary-strong"
            >
              <Plus className="w-4 h-4 mr-2" />
              {t('admin.categories.add')}
            </button>
          </div>

          {/* Search */}
          <div className="mt-4 relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-muted-foreground" />
            <input
              type="text"
              placeholder={t('admin.categories.search.placeholder')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-input rounded-lg focus:ring-2 focus:ring-ring focus:border-primary bg-background text-foreground placeholder:text-placeholder"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {error && (
          <div className="mb-4 p-4 bg-danger-soft border border-danger rounded-lg flex items-center text-danger-foreground">
            <AlertCircle className="w-5 h-5 mr-2" />
            {error}
          </div>
        )}

        <div className="bg-card shadow rounded-lg overflow-hidden border border-border">
          {filteredTree.length === 0 ? (
            <div className="p-8 text-center text-muted-foreground">
              <FolderOpen className="w-12 h-12 text-muted-foreground/50 mx-auto mb-3" />
              <p>{t('admin.categories.empty')}</p>
              <button
                onClick={handleCreate}
                className="mt-4 text-primary hover:text-primary-strong"
              >
                {t('admin.categories.empty.start')}
              </button>
            </div>
          ) : searchQuery ? (
            // Search results (flat list)
            <div className="divide-y divide-border">
              {filteredTree.map((cat) => (
                <div
                  key={cat.id}
                  className="p-4 flex items-center justify-between hover:bg-muted"
                >
                  <div className="flex items-center">
                    <FolderOpen className="w-5 h-5 text-primary mr-3" />
                    <div>
                      <p className="text-sm font-medium text-foreground">{cat.name}</p>
                      <p className="text-xs text-muted-foreground">{cat.slug}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleEdit(cat)}
                      className="p-2 text-muted-foreground hover:text-primary"
                    >
                      <Edit className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleDelete(cat)}
                      className="p-2 text-muted-foreground hover:text-danger"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            // Tree view
            <div className="divide-y divide-border">
              {categoryTree.map((cat) => (
                <CategoryTreeItem
                  key={cat.id}
                  category={cat}
                  expandedIds={expandedIds}
                  onToggle={toggleExpanded}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Modal */}
      {showModal && (
        <CategoryModal
          category={editingCategory}
          categories={categories.filter((c) => c.id !== editingCategory?.id)}
          onClose={() => setShowModal(false)}
          onSuccess={handleSuccess}
          t={t}
        />
      )}
    </div>
  );
}

function CategoryTreeItem({
  category,
  expandedIds,
  onToggle,
  onEdit,
  onDelete,
}: {
  category: CategoryTree;
  expandedIds: Set<string>;
  onToggle: (id: string) => void;
  onEdit: (category: Category) => void;
  onDelete: (category: Category) => void;
}) {
  const hasChildren = category.children && category.children.length > 0;
  const isExpanded = expandedIds.has(category.id);

  return (
    <>
      <div className="p-4 flex items-center hover:bg-muted">
        <button
          onClick={() => hasChildren && onToggle(category.id)}
          className={`p-1 mr-2 ${hasChildren ? 'text-muted-foreground hover:text-foreground' : 'text-transparent'}`}
        >
          {hasChildren ? (
            isExpanded ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </button>
        {category.icon ? (
          <div className="w-5 h-5 mr-3 text-primary flex items-center justify-center">
            {getIconByName(category.icon, 20)}
          </div>
        ) : (
          <FolderOpen className="w-5 h-5 text-primary mr-3" />
        )}
        <div className="flex-1">
          <p className="text-sm font-medium text-foreground">{category.name}</p>
          <p className="text-xs text-muted-foreground">{category.slug}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => onEdit(category as unknown as Category)}
            className="p-2 text-muted-foreground hover:text-primary"
          >
            <Edit className="w-4 h-4" />
          </button>
          <button
            onClick={() => onDelete(category as unknown as Category)}
            className="p-2 text-muted-foreground hover:text-danger"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
      {hasChildren && isExpanded && (
        <div className="bg-muted border-l-4 border-primary-soft">
          {category.children!.map((child) => (
            <CategoryTreeItem
              key={child.id}
              category={child}
              expandedIds={expandedIds}
              onToggle={onToggle}
              onEdit={onEdit}
              onDelete={onDelete}
            />
          ))}
        </div>
      )}
    </>
  );
}

function flattenTree(tree: CategoryTree[]): CategoryTree[] {
  const result: CategoryTree[] = [];
  for (const cat of tree) {
    result.push(cat);
    if (cat.children && cat.children.length > 0) {
      result.push(...flattenTree(cat.children));
    }
  }
  return result;
}

// Category Modal
function CategoryModal({
  category,
  categories,
  onClose,
  onSuccess,
  t,
}: {
  category: Category | null;
  categories: Category[];
  onClose: () => void;
  onSuccess: () => void;
  t: Translator;
}) {
  const [formData, setFormData] = useState({
    name: category?.name || '',
    description: category?.description || '',
    parentId: category?.parentId || '',
    icon: category?.icon || '',
    displayOrder: category?.displayOrder || 0,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (category) {
        await categoryService.updateCategory(category.id, formData);
      } else {
        await categoryService.createCategory(formData);
      }
      onSuccess();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        <div className="fixed inset-0 bg-overlay/50" onClick={onClose} />
        <div className="relative bg-card rounded-xl shadow-xl w-full max-w-md p-6 border border-border">
          <h2 className="text-lg font-semibold text-foreground mb-4">
            {category ? t('admin.categories.modal.edit') : t('admin.categories.modal.create')}
          </h2>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">
                {t('admin.categories.modal.name.required')}
              </label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring bg-background text-foreground"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('admin.categories.modal.description')}</label>
              <textarea
                value={formData.description}
                onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                rows={3}
                className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring bg-background text-foreground"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">{t('admin.categories.modal.parent')}</label>
              <select
                value={formData.parentId}
                onChange={(e) => setFormData({ ...formData, parentId: e.target.value })}
                className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring bg-background text-foreground"
              >
                <option value="">{t('admin.categories.modal.parent.none')}</option>
                {categories.map((cat) => (
                  <option key={cat.id} value={cat.id}>
                    {cat.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <IconPicker
                label={t('admin.categories.modal.icon')}
                value={formData.icon}
                onChange={(icon) => setFormData({ ...formData, icon })}
              />
              <div>
                <label className="block text-sm font-medium text-foreground mb-1">{t('admin.categories.modal.order')}</label>
                <input
                  type="number"
                  value={formData.displayOrder}
                  onChange={(e) => setFormData({ ...formData, displayOrder: parseInt(e.target.value) || 0 })}
                  className="w-full border border-input rounded-lg px-3 py-2 focus:ring-2 focus:ring-ring bg-background text-foreground"
                />
              </div>
            </div>
            {error && (
              <div className="p-3 bg-danger-soft border border-danger rounded-lg text-danger-foreground text-sm">
                {error}
              </div>
            )}
            <div className="flex justify-end gap-3 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-input rounded-lg text-sm font-medium text-foreground hover:bg-muted"
              >
                {t('admin.categories.modal.cancel')}
              </button>
              <button
                type="submit"
                disabled={saving}
                className="px-4 py-2 bg-primary text-primary-foreground rounded-lg text-sm font-medium hover:bg-primary-strong disabled:opacity-50"
              >
                {saving ? t('admin.categories.modal.saving') : t('admin.categories.modal.save')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
