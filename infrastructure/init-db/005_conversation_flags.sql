-- ============================================================
-- MIGRATION: Add toxic and layer2 flags to messages table
-- FILE: 005_conversation_flags.sql
-- SCHEMA: CONVERSATION
-- ============================================================
-- Add flags to mark toxic messages and Layer 2 responses
-- for smarter message persistence and context filtering
-- ============================================================

-- Add is_toxic column (marks USER messages that were blocked)
ALTER TABLE conversation.messages
ADD COLUMN IF NOT EXISTS is_toxic BOOLEAN DEFAULT FALSE;

-- Add is_layer2_response column (marks ASSISTANT responses from Layer 2 simple queries)
ALTER TABLE conversation.messages
ADD COLUMN IF NOT EXISTS is_layer2_response BOOLEAN DEFAULT FALSE;

-- Add index for querying toxic messages
CREATE INDEX IF NOT EXISTS idx_messages_is_toxic ON conversation.messages(is_toxic) WHERE is_toxic = TRUE;

-- Add index for querying Layer 2 responses
CREATE INDEX IF NOT EXISTS idx_messages_is_layer2_response ON conversation.messages(is_layer2_response) WHERE is_layer2_response = TRUE;

-- Add composite index for filtered context queries
CREATE INDEX IF NOT EXISTS idx_messages_flags ON conversation.messages(conversation_id, is_toxic, is_layer2_response) WHERE deleted_at IS NULL;
