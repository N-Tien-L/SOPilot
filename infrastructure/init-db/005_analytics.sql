-- ============================================================
-- FILE: 005_analytics.sql
-- SCHEMA: ANALYTICS
-- Contains: Feedbacks, Usage stats, Audit logs, Aggregates
-- ============================================================
-- Single source of truth for analytics schema.
-- All columns defined upfront - no ALTER statements needed.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE analytics.feedback_type AS ENUM ('LIKE', 'DISLIKE');

CREATE TYPE analytics.audit_action AS ENUM (
    'LOGIN_SUCCESS', 'LOGIN_FAILED', 'LOGOUT', 'TOKEN_REFRESH', 'PASSWORD_CHANGE',
    'USER_CREATE', 'USER_UPDATE', 'USER_DEACTIVATE', 'USER_ACTIVATE', 'USER_REVOKE', 'USER_DELETE',
    'USER_PROFILE_UPDATE', 'USER_SETTINGS_UPDATE',
    'ROLE_CHANGE', 'STATUS_CHANGE',
    'DOCUMENT_UPLOAD', 'DOCUMENT_UPDATE', 'DOCUMENT_DELETE', 'DOCUMENT_PUBLISH', 'DOCUMENT_ARCHIVE', 'DOCUMENT_VERSION_CREATE',
    'QUESTION_ASK', 'CONVERSATION_CREATE', 'CONVERSATION_DELETE',
    'FEEDBACK_SUBMIT',
    'SETTINGS_UPDATE', 'BULK_IMPORT', 'REPORT_EXPORT',
    'CATEGORY_CREATE', 'CATEGORY_UPDATE', 'CATEGORY_DELETE',
    'TAG_CREATE', 'TAG_UPDATE', 'TAG_DELETE',
    'DEPARTMENT_CREATE', 'DEPARTMENT_UPDATE', 'DEPARTMENT_DELETE'
);


CREATE TYPE analytics.resource_type AS ENUM (
    'USER', 'DOCUMENT', 'CONVERSATION', 'MESSAGE', 'FEEDBACK',
    'DEPARTMENT', 'CATEGORY', 'TAG', 'SETTINGS'
);

CREATE TYPE analytics.export_format AS ENUM ('CSV', 'PDF', 'XLSX', 'JSON');

CREATE TYPE analytics.report_type AS ENUM (
    'USER_REPORT', 'DEPARTMENT_REPORT', 'USAGE_SUMMARY', 'QUESTION_ANALYTICS',
    'FEEDBACK_ANALYSIS', 'USER_ENGAGEMENT', 'DOCUMENT_POPULARITY',
    'UNANSWERED_QUESTIONS', 'DEPARTMENT_BREAKDOWN'
);

CREATE TYPE analytics.report_status AS ENUM ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED');

-- ============================================================
-- TABLE: analytics.feedbacks
-- ============================================================
CREATE TABLE analytics.feedbacks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    message_id UUID REFERENCES conversation.messages(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversation.conversations(id) ON DELETE SET NULL,

    type analytics.feedback_type NOT NULL,
    comment TEXT,

    question_text TEXT,
    answer_text TEXT,
    sources_used JSONB DEFAULT '[]',

    user_department_id UUID,
    user_role VARCHAR(20),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT uq_user_message_feedback UNIQUE (user_id, message_id)
);

-- ============================================================
-- TABLE: analytics.usage_stats
-- ============================================================
CREATE TABLE analytics.usage_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    user_id UUID,
    user_role VARCHAR(20),
    user_department_id UUID,

    service_name VARCHAR(50) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,

    response_time_ms INT NOT NULL,
    status_code INT NOT NULL,

    request_size_bytes INT,
    response_size_bytes INT,

    is_error BOOLEAN DEFAULT FALSE,
    error_code VARCHAR(50),
    error_message TEXT,

    tokens_used INT,
    model_used VARCHAR(50),
    chunks_retrieved INT,
    confidence VARCHAR(20),

    trace_id VARCHAR(100),

    ip_address INET,
    user_agent TEXT,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: analytics.audit_logs
-- ============================================================
CREATE TABLE analytics.audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    user_id UUID,
    username VARCHAR(50),
    user_role VARCHAR(20),

    action analytics.audit_action NOT NULL,

    resource_type analytics.resource_type NOT NULL,
    resource_id UUID,
    resource_name VARCHAR(255),

    old_value JSONB,
    new_value JSONB,
    changed_fields TEXT[],

    ip_address INET,
    user_agent TEXT,
    trace_id VARCHAR(100),

    service_name VARCHAR(50),

    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: analytics.daily_aggregates
-- ============================================================
CREATE TABLE analytics.daily_aggregates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL UNIQUE,

    total_questions INT DEFAULT 0,
    total_conversations INT DEFAULT 0,
    unique_users_asked INT DEFAULT 0,

    total_likes INT DEFAULT 0,
    total_dislikes INT DEFAULT 0,
    feedback_ratio DECIMAL(5,4),

    avg_response_time_ms INT,
    p50_response_time_ms INT,
    p95_response_time_ms INT,
    p99_response_time_ms INT,

    total_requests INT DEFAULT 0,
    total_errors INT DEFAULT 0,
    error_rate DECIMAL(5,4),

    total_tokens_used BIGINT DEFAULT 0,
    avg_tokens_per_question INT,
    avg_chunks_retrieved DECIMAL(5,2),

    documents_uploaded INT DEFAULT 0,
    documents_published INT DEFAULT 0,

    unique_active_users INT DEFAULT 0,
    new_users INT DEFAULT 0,

    unanswered_questions INT DEFAULT 0,
    resolved_questions INT DEFAULT 0,

    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: analytics.hourly_aggregates
-- ============================================================
CREATE TABLE analytics.hourly_aggregates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    datetime TIMESTAMPTZ NOT NULL,
    hour INT NOT NULL CHECK (hour >= 0 AND hour <= 23),

    total_questions INT DEFAULT 0,
    total_requests INT DEFAULT 0,
    total_errors INT DEFAULT 0,
    unique_users INT DEFAULT 0,

    avg_response_time_ms INT,

    likes INT DEFAULT 0,
    dislikes INT DEFAULT 0,

    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_hourly_datetime UNIQUE (datetime)
);

-- ============================================================
-- TABLE: analytics.department_daily_stats
-- ============================================================
CREATE TABLE analytics.department_daily_stats (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    date DATE NOT NULL,
    department_id UUID NOT NULL,

    total_questions INT DEFAULT 0,
    unique_users INT DEFAULT 0,

    likes INT DEFAULT 0,
    dislikes INT DEFAULT 0,

    top_categories JSONB DEFAULT '[]',

    computed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_department_daily UNIQUE (date, department_id)
);

-- ============================================================
-- TABLE: analytics.popular_questions
-- ============================================================
CREATE TABLE analytics.popular_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    question_normalized TEXT NOT NULL,
    question_sample TEXT NOT NULL,

    ask_count INT DEFAULT 1,
    unique_users_count INT DEFAULT 1,

    first_asked_at TIMESTAMPTZ NOT NULL,
    last_asked_at TIMESTAMPTZ NOT NULL,

    total_likes INT DEFAULT 0,
    total_dislikes INT DEFAULT 0,

    common_source_documents JSONB DEFAULT '[]',

    detected_category VARCHAR(100),
    detected_department_id UUID,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: analytics.document_popularity
-- ============================================================
CREATE TABLE analytics.document_popularity (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL UNIQUE,

    total_citations INT DEFAULT 0,
    unique_questions_cited INT DEFAULT 0,

    citations_with_likes INT DEFAULT 0,
    citations_with_dislikes INT DEFAULT 0,

    first_cited_at TIMESTAMPTZ,
    last_cited_at TIMESTAMPTZ,

    citations_last_7_days INT DEFAULT 0,
    citations_last_30_days INT DEFAULT 0,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- TABLE: analytics.report_exports
-- ============================================================
CREATE TABLE analytics.report_exports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    report_type analytics.report_type NOT NULL,
    title VARCHAR(255) NOT NULL,

    date_from DATE,
    date_to DATE,
    department_id UUID,
    filters JSONB DEFAULT '{}',

    format analytics.export_format NOT NULL,
    file_key VARCHAR(500),
    file_size_bytes INT,

    status analytics.report_status DEFAULT 'PENDING',
    error_message TEXT,

    requested_by UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ
);


-- ============================================================
-- INDEXES: Analytics schema
-- ============================================================
CREATE INDEX idx_analytics_feedbacks_user_id ON analytics.feedbacks(user_id);
CREATE INDEX idx_analytics_feedbacks_message_id ON analytics.feedbacks(message_id);
CREATE INDEX idx_analytics_feedbacks_type ON analytics.feedbacks(type);
CREATE INDEX idx_analytics_feedbacks_created_at ON analytics.feedbacks(created_at DESC);
CREATE INDEX idx_analytics_feedbacks_deleted_at ON analytics.feedbacks(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_analytics_usage_stats_user_id ON analytics.usage_stats(user_id);
CREATE INDEX idx_analytics_usage_stats_service ON analytics.usage_stats(service_name);
CREATE INDEX idx_analytics_usage_stats_created_at ON analytics.usage_stats(created_at DESC);
CREATE INDEX idx_analytics_usage_stats_is_error ON analytics.usage_stats(is_error) WHERE is_error = TRUE;
CREATE INDEX idx_analytics_usage_stats_trace_id ON analytics.usage_stats(trace_id);

CREATE INDEX idx_analytics_audit_logs_user_id ON analytics.audit_logs(user_id);
CREATE INDEX idx_analytics_audit_logs_action ON analytics.audit_logs(action);
CREATE INDEX idx_analytics_audit_logs_resource ON analytics.audit_logs(resource_type, resource_id);
CREATE INDEX idx_analytics_audit_logs_created_at ON analytics.audit_logs(created_at DESC);
CREATE INDEX idx_analytics_audit_logs_trace_id ON analytics.audit_logs(trace_id);

CREATE INDEX idx_analytics_daily_aggregates_date ON analytics.daily_aggregates(date DESC);
CREATE INDEX idx_analytics_hourly_aggregates_datetime ON analytics.hourly_aggregates(datetime DESC);
CREATE INDEX idx_analytics_department_daily_stats_date ON analytics.department_daily_stats(date DESC);
CREATE INDEX idx_analytics_department_daily_stats_department ON analytics.department_daily_stats(department_id);

CREATE INDEX idx_analytics_popular_questions_ask_count ON analytics.popular_questions(ask_count DESC);
CREATE INDEX idx_analytics_popular_questions_last_asked ON analytics.popular_questions(last_asked_at DESC);

CREATE INDEX idx_analytics_document_popularity_document_id ON analytics.document_popularity(document_id);
CREATE INDEX idx_analytics_document_popularity_total_citations ON analytics.document_popularity(total_citations DESC);

CREATE INDEX idx_analytics_report_exports_requested_by ON analytics.report_exports(requested_by);
CREATE INDEX idx_analytics_report_exports_status ON analytics.report_exports(status);
