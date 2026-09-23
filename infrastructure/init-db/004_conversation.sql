-- ============================================================
-- FILE: 004_conversation.sql
-- SCHEMA: CONVERSATION
-- Contains: Conversations, Messages, Unanswered questions
-- ============================================================
-- Single source of truth for conversation schema.
-- All columns defined upfront - no ALTER statements needed.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- ENUM TYPES
-- ============================================================
CREATE TYPE conversation.message_role AS ENUM ('USER', 'ASSISTANT', 'SYSTEM');
CREATE TYPE conversation.confidence_level AS ENUM ('HIGH', 'MEDIUM', 'LOW', 'UNKNOWN');
CREATE TYPE conversation.priority_level AS ENUM ('LOW', 'NORMAL', 'HIGH', 'CRITICAL');

-- ============================================================
-- TABLE: conversation.conversations
-- ============================================================
CREATE TABLE conversation.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,

    title VARCHAR(255),

    message_count INT DEFAULT 0,
    last_message_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- TABLE: conversation.messages
-- ============================================================
CREATE TABLE conversation.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversation.conversations(id) ON DELETE CASCADE,

    role conversation.message_role NOT NULL,
    content TEXT NOT NULL,
    content_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', content)) STORED,

    sources JSONB DEFAULT '[]',

    model_used VARCHAR(50),
    tokens_prompt INT,
    tokens_completion INT,
    tokens_total INT,
    latency_ms INT,

    confidence conversation.confidence_level,
    has_sources BOOLEAN DEFAULT FALSE,

    is_streaming BOOLEAN DEFAULT FALSE,
    streaming_completed BOOLEAN DEFAULT TRUE,

    is_toxic BOOLEAN DEFAULT FALSE,           -- User message was flagged as toxic/blocked
    is_layer2_response BOOLEAN DEFAULT FALSE, -- Assistant response from Layer 2 (simple query)

    trace_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ,

    CONSTRAINT chk_tokens CHECK (tokens_total IS NULL OR tokens_total >= 0)
);

-- ============================================================
-- TABLE: conversation.unanswered_questions
-- ============================================================
CREATE TABLE conversation.unanswered_questions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    message_id UUID REFERENCES conversation.messages(id) ON DELETE SET NULL,
    conversation_id UUID REFERENCES conversation.conversations(id) ON DELETE SET NULL,

    question TEXT NOT NULL,
    question_normalized TEXT,

    attempted_context JSONB DEFAULT '{}',
    search_query TEXT,
    top_similarity_score DECIMAL(5,4),

    user_department_id UUID,
    user_role VARCHAR(20),

    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    resolved BOOLEAN DEFAULT FALSE,
    resolved_by UUID,
    resolved_at TIMESTAMPTZ,
    resolution_notes TEXT,
    related_document_id UUID,

    category VARCHAR(100),
    priority conversation.priority_level DEFAULT 'NORMAL',

    trace_id VARCHAR(100),
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMPTZ
);

-- ============================================================
-- INDEXES: Conversation schema
-- ============================================================
CREATE INDEX idx_conversation_conversations_user_id ON conversation.conversations(user_id);
CREATE INDEX idx_conversation_conversations_created_at ON conversation.conversations(created_at DESC);
CREATE INDEX idx_conversation_conversations_deleted_at ON conversation.conversations(deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX idx_conversation_messages_conversation_id ON conversation.messages(conversation_id);
CREATE INDEX idx_conversation_messages_role ON conversation.messages(role);
CREATE INDEX idx_conversation_messages_created_at ON conversation.messages(created_at DESC);
CREATE INDEX idx_conversation_messages_deleted_at ON conversation.messages(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversation_messages_trace_id ON conversation.messages(trace_id);
CREATE INDEX idx_messages_content_tsv ON conversation.messages USING GIN (content_tsv);

CREATE INDEX idx_conversation_unanswered_questions_user_id ON conversation.unanswered_questions(user_id);
CREATE INDEX idx_conversation_unanswered_questions_status ON conversation.unanswered_questions(status);
CREATE INDEX idx_conversation_unanswered_questions_resolved ON conversation.unanswered_questions(resolved);
CREATE INDEX idx_conversation_unanswered_questions_priority ON conversation.unanswered_questions(priority);
CREATE INDEX idx_conversation_unanswered_questions_deleted_at ON conversation.unanswered_questions(deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_conversation_unanswered_questions_trace_id ON conversation.unanswered_questions(trace_id);
