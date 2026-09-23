-- ============================================================
-- FILE: 006_functions_triggers.sql
-- CROSS-SCHEMA: Triggers and Functions
-- ============================================================
-- Contains: Auto-updated_at triggers, conversation stats,
-- tag usage tracking, and document access functions.
-- ============================================================

-- ============================================================
-- FUNCTION: Auto-update updated_at timestamp
-- ============================================================
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- TRIGGERS: updated_at for Core schema
-- ============================================================
CREATE TRIGGER trg_core_users_updated_at
    BEFORE UPDATE ON core.users
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_core_user_profiles_updated_at
    BEFORE UPDATE ON core.user_profiles
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_core_departments_updated_at
    BEFORE UPDATE ON core.departments
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- TRIGGERS: updated_at for Metadata schema
-- ============================================================
CREATE TRIGGER trg_metadata_categories_updated_at
    BEFORE UPDATE ON metadata.categories
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_metadata_document_metadata_updated_at
    BEFORE UPDATE ON metadata.document_metadata
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- TRIGGERS: updated_at for Knowledge schema
-- ============================================================
CREATE TRIGGER trg_knowledge_documents_updated_at
    BEFORE UPDATE ON knowledge.documents
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_knowledge_chunks_updated_at
    BEFORE UPDATE ON knowledge.chunks
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_knowledge_processing_jobs_updated_at
    BEFORE UPDATE ON knowledge.processing_jobs
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- TRIGGERS: updated_at for Conversation schema
-- ============================================================
CREATE TRIGGER trg_conversation_conversations_updated_at
    BEFORE UPDATE ON conversation.conversations
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_conversation_unanswered_questions_updated_at
    BEFORE UPDATE ON conversation.unanswered_questions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- TRIGGERS: updated_at for Analytics schema
-- ============================================================
CREATE TRIGGER trg_analytics_feedbacks_updated_at
    BEFORE UPDATE ON analytics.feedbacks
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_analytics_daily_aggregates_updated_at
    BEFORE UPDATE ON analytics.daily_aggregates
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_analytics_popular_questions_updated_at
    BEFORE UPDATE ON analytics.popular_questions
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

CREATE TRIGGER trg_analytics_document_popularity_updated_at
    BEFORE UPDATE ON analytics.document_popularity
    FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================
-- FUNCTION: Tag usage count trigger
-- ============================================================
CREATE OR REPLACE FUNCTION metadata.update_tag_usage_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE metadata.tags SET usage_count = usage_count + 1 WHERE id = NEW.tag_id;
        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE metadata.tags SET usage_count = GREATEST(0, usage_count - 1) WHERE id = OLD.tag_id;
        RETURN OLD;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_metadata_document_tags_usage_count
    AFTER INSERT OR DELETE ON metadata.document_tags
    FOR EACH ROW EXECUTE FUNCTION metadata.update_tag_usage_count();

-- ============================================================
-- FUNCTION: Conversation stats trigger
-- ============================================================
CREATE OR REPLACE FUNCTION conversation.update_conversation_stats()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE conversation.conversations
        SET message_count = message_count + 1,
            last_message_at = NEW.created_at,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.conversation_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE conversation.conversations
        SET message_count = message_count - 1,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = OLD.conversation_id;

        UPDATE conversation.conversations c
        SET last_message_at = (
            SELECT MAX(created_at) FROM conversation.messages WHERE conversation_id = c.id
        )
        WHERE c.id = OLD.conversation_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_conversation_messages_stats
    AFTER INSERT OR DELETE ON conversation.messages
    FOR EACH ROW EXECUTE FUNCTION conversation.update_conversation_stats();

-- ============================================================
-- FUNCTION: Auto-generate conversation title
-- ============================================================
CREATE OR REPLACE FUNCTION conversation.generate_conversation_title()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.role = 'USER' THEN
        UPDATE conversation.conversations
        SET title = LEFT(NEW.content, 100) || CASE WHEN LENGTH(NEW.content) > 100 THEN '...' ELSE '' END
        WHERE id = NEW.conversation_id AND title IS NULL;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_conversation_messages_generate_title
    AFTER INSERT ON conversation.messages
    FOR EACH ROW EXECUTE FUNCTION conversation.generate_conversation_title();

-- ============================================================
-- FUNCTION: Check document access
-- ============================================================
CREATE OR REPLACE FUNCTION metadata.check_document_access(
    p_document_id UUID,
    p_user_id UUID,
    p_user_role core.user_role,
    p_user_department_id UUID
)
RETURNS BOOLEAN AS $$
DECLARE
    v_access_level metadata.access_level;
    v_document_department_id UUID;
    v_has_explicit_deny BOOLEAN;
    v_has_explicit_allow BOOLEAN;
BEGIN
    SELECT access_level, department_id
    INTO v_access_level, v_document_department_id
    FROM metadata.document_metadata
    WHERE document_id = p_document_id AND deleted_at IS NULL;

    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF p_user_role = 'ADMIN' THEN
        RETURN TRUE;
    END IF;

    SELECT EXISTS(
        SELECT 1 FROM metadata.document_access_rules
        WHERE document_metadata_id = (SELECT id FROM metadata.document_metadata WHERE document_id = p_document_id)
          AND permission = 'DENY'
          AND (
              (target_type = 'USER' AND target_user_id = p_user_id) OR
              (target_type = 'ROLE' AND target_role = p_user_role) OR
              (target_type = 'DEPARTMENT' AND target_department_id = p_user_department_id)
          )
    ) INTO v_has_explicit_deny;

    IF v_has_explicit_deny THEN
        RETURN FALSE;
    END IF;

    IF v_access_level = 'PUBLIC' THEN
        RETURN TRUE;
    ELSIF v_access_level = 'DEPARTMENT_ONLY' THEN
        RETURN v_document_department_id = p_user_department_id;
    ELSIF v_access_level = 'RESTRICTED' THEN
        SELECT EXISTS(
            SELECT 1 FROM metadata.document_access_rules
            WHERE document_metadata_id = (SELECT id FROM metadata.document_metadata WHERE document_id = p_document_id)
              AND permission = 'VIEW'
              AND (
                  (target_type = 'USER' AND target_user_id = p_user_id) OR
                  (target_type = 'ROLE' AND target_role = p_user_role) OR
                  (target_type = 'DEPARTMENT' AND target_department_id = p_user_department_id)
              )
        ) INTO v_has_explicit_allow;

        RETURN v_has_explicit_allow;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- FUNCTION: Ensure only one current version per document
-- ============================================================
CREATE OR REPLACE FUNCTION knowledge.enforce_single_current_version()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_current = TRUE THEN
        UPDATE knowledge.document_versions
        SET is_current = FALSE
        WHERE document_id = NEW.document_id
          AND id != COALESCE(NEW.id, '00000000-0000-0000-0000-000000000000'::uuid)
          AND is_current = TRUE;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_enforce_single_current_version
    BEFORE INSERT OR UPDATE ON knowledge.document_versions
    FOR EACH ROW EXECUTE FUNCTION knowledge.enforce_single_current_version();

-- ============================================================
-- FUNCTION: Normalize unanswered question
-- ============================================================
CREATE OR REPLACE FUNCTION conversation.normalize_unanswered_question()
RETURNS TRIGGER AS $$
BEGIN
    NEW.question_normalized := lower(trim(
        regexp_replace(
            regexp_replace(NEW.question, '[^a-zA-Z0-9àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴĐ\s]', ' ', 'g'),
            '\s+', ' ', 'g'
        )
    ));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_normalize_unanswered_question
    BEFORE INSERT OR UPDATE OF question ON conversation.unanswered_questions
    FOR EACH ROW
    EXECUTE FUNCTION conversation.normalize_unanswered_question();

-- ============================================================
-- FUNCTION: Update tag usage on document soft delete
-- ============================================================
CREATE OR REPLACE FUNCTION metadata.update_tag_usage_on_soft_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
        -- Document was soft-deleted, decrement tag usage counts
        UPDATE metadata.tags
        SET usage_count = usage_count - 1
        WHERE id IN (
            SELECT tag_id FROM metadata.document_tags WHERE document_id = OLD.id
        );
    ELSIF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN
        -- Document was restored, increment tag usage counts
        UPDATE metadata.tags
        SET usage_count = usage_count + 1
        WHERE id IN (
            SELECT tag_id FROM metadata.document_tags WHERE document_id = OLD.id
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_update_tag_usage_on_soft_delete
    AFTER UPDATE OF deleted_at ON metadata.document_metadata
    FOR EACH ROW
    EXECUTE FUNCTION metadata.update_tag_usage_on_soft_delete();

-- ============================================================
-- MIGRATED FROM 002_fk_constraints_and_improvements.sql
-- ============================================================

-- ============================================================
-- FK: H4 - conversation.conversations.user_id
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_conversations_user_id'
    ) THEN
        ALTER TABLE conversation.conversations
            ADD CONSTRAINT fk_conversations_user_id
            FOREIGN KEY (user_id) REFERENCES core.users(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ============================================================
-- FK: H5 - metadata.document_metadata.document_id
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_document_metadata_document_id'
    ) THEN
        ALTER TABLE metadata.document_metadata
            ADD CONSTRAINT fk_document_metadata_document_id
            FOREIGN KEY (document_id) REFERENCES knowledge.documents(id) ON DELETE CASCADE;
    END IF;
END $$;

-- ============================================================
-- FK: H6 - analytics.feedbacks constraints
-- ============================================================
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_feedbacks_message_id'
    ) THEN
        ALTER TABLE analytics.feedbacks
            ADD CONSTRAINT fk_feedbacks_message_id
            FOREIGN KEY (message_id) REFERENCES conversation.messages(id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_feedbacks_conversation_id'
    ) THEN
        ALTER TABLE analytics.feedbacks
            ADD CONSTRAINT fk_feedbacks_conversation_id
            FOREIGN KEY (conversation_id) REFERENCES conversation.conversations(id) ON DELETE SET NULL;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_feedbacks_user_id'
    ) THEN
        ALTER TABLE analytics.feedbacks
            ADD CONSTRAINT fk_feedbacks_user_id
            FOREIGN KEY (user_id) REFERENCES core.users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- ============================================================
-- M8: Set vector_indexed = TRUE for chunks with embeddings
-- ============================================================
UPDATE knowledge.chunks
SET vector_indexed = TRUE
WHERE embedding_vector IS NOT NULL
  AND vector_indexed = FALSE;

-- ============================================================
-- L2: Change language default from 'vi' to NULL
-- ============================================================
ALTER TABLE knowledge.documents
    ALTER COLUMN language DROP DEFAULT;

-- ============================================================
-- L3: Change chunk_type default from 'child' to 'parent'
-- ============================================================
ALTER TABLE knowledge.chunks
    ALTER COLUMN chunk_type SET DEFAULT 'parent';

-- ============================================================
-- L9: Index for document access rules
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_access_rules_targets
    ON metadata.document_access_rules(target_type, target_role, target_department_id, target_user_id);

-- ============================================================
-- L8: Drop redundant bucket_name column
-- ============================================================
ALTER TABLE knowledge.chunks DROP COLUMN IF EXISTS bucket_name;