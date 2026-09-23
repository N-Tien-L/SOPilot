-- ============================================================
-- FILE: 002_metadata.sql
-- SCHEMA: METADATA
-- Contains: Document metadata, Categories, Tags, Access rules
-- ============================================================
-- Single source of truth for metadata schema.
-- All columns defined upfront - no ALTER statements needed.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE metadata.document_status AS ENUM ('DRAFT', 'PUBLISHED', 'ARCHIVED', 'EXPIRED');
CREATE TYPE metadata.access_level AS ENUM ('PUBLIC', 'DEPARTMENT_ONLY', 'RESTRICTED');
CREATE TYPE metadata.rule_target_type AS ENUM ('ROLE', 'DEPARTMENT', 'USER');
CREATE TYPE metadata.rule_permission AS ENUM ('VIEW', 'DENY');

-- ============================================================
-- TABLE: metadata.categories
-- ============================================================
CREATE TABLE metadata.categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    parent_id UUID REFERENCES metadata.categories(id) ON DELETE SET NULL,
    icon VARCHAR(50),
    display_order INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- TABLE: metadata.tags
-- ============================================================
CREATE TABLE metadata.tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) UNIQUE NOT NULL,
    color VARCHAR(7) DEFAULT '#6B7280',
    usage_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- TABLE: metadata.document_metadata
-- ============================================================
CREATE TABLE metadata.document_metadata (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID UNIQUE NOT NULL,

    title VARCHAR(255) NOT NULL,
    description TEXT,
    document_type VARCHAR(50) NOT NULL,

    category_id UUID REFERENCES metadata.categories(id) ON DELETE SET NULL,
    department_id UUID REFERENCES core.departments(id) ON DELETE SET NULL,

    access_level metadata.access_level NOT NULL DEFAULT 'PUBLIC',

    effective_date DATE,
    expiry_date DATE,

    status metadata.document_status NOT NULL DEFAULT 'DRAFT',
    current_version INT DEFAULT 1,

    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    updated_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    published_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_date_range CHECK (expiry_date IS NULL OR effective_date IS NULL OR expiry_date >= effective_date)
);

-- ============================================================
-- TABLE: metadata.document_tags
-- ============================================================
CREATE TABLE metadata.document_tags (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_metadata_id UUID NOT NULL REFERENCES metadata.document_metadata(id) ON DELETE CASCADE,
    tag_id UUID NOT NULL REFERENCES metadata.tags(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_document_tag UNIQUE (document_metadata_id, tag_id)
);

-- ============================================================
-- TABLE: metadata.document_access_rules
-- ============================================================
CREATE TABLE metadata.document_access_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_metadata_id UUID NOT NULL REFERENCES metadata.document_metadata(id) ON DELETE CASCADE,

    target_type metadata.rule_target_type NOT NULL,
    target_role core.user_role,
    target_department_id UUID REFERENCES core.departments(id) ON DELETE CASCADE,
    target_user_id UUID REFERENCES core.users(id) ON DELETE CASCADE,

    permission metadata.rule_permission NOT NULL,

    created_by UUID REFERENCES core.users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    trace_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    CONSTRAINT chk_target_consistency CHECK (
        (target_type = 'ROLE' AND target_role IS NOT NULL AND target_department_id IS NULL AND target_user_id IS NULL) OR
        (target_type = 'DEPARTMENT' AND target_role IS NULL AND target_department_id IS NOT NULL AND target_user_id IS NULL) OR
        (target_type = 'USER' AND target_role IS NULL AND target_department_id IS NULL AND target_user_id IS NOT NULL)
    )
);

-- ============================================================
-- INDEXES: Metadata schema
-- ============================================================
CREATE INDEX idx_metadata_categories_parent_id ON metadata.categories(parent_id);
CREATE INDEX idx_metadata_categories_slug ON metadata.categories(slug);
CREATE INDEX idx_metadata_categories_deleted_at ON metadata.categories(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_metadata_tags_name ON metadata.tags(name);
CREATE INDEX idx_metadata_tags_slug ON metadata.tags(slug);
CREATE INDEX idx_metadata_tags_deleted_at ON metadata.tags(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_metadata_document_metadata_document_id ON metadata.document_metadata(document_id);
CREATE INDEX idx_metadata_document_metadata_status ON metadata.document_metadata(status);
CREATE INDEX idx_metadata_document_metadata_category_id ON metadata.document_metadata(category_id);
CREATE INDEX idx_metadata_document_metadata_department_id ON metadata.document_metadata(department_id);
CREATE INDEX idx_metadata_document_metadata_deleted_at ON metadata.document_metadata(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_metadata_document_tags_metadata_id ON metadata.document_tags(document_metadata_id);
CREATE INDEX idx_metadata_document_tags_tag_id ON metadata.document_tags(tag_id);

CREATE INDEX idx_metadata_doc_access_rules_metadata_id ON metadata.document_access_rules(document_metadata_id);
CREATE INDEX idx_metadata_doc_access_rules_target_lookup
    ON metadata.document_access_rules(document_metadata_id, permission, target_type, target_role, target_department_id, target_user_id);
CREATE INDEX idx_metadata_doc_access_rules_trace_id ON metadata.document_access_rules(trace_id);
CREATE INDEX idx_access_rules_targets
    ON metadata.document_access_rules(target_type, target_role, target_department_id, target_user_id);
