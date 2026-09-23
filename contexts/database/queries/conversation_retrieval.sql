-- ============================================================
-- CONVERSATION SCHEMA RETRIEVAL SCRIPTS
-- Purpose: Querying chat history and AI performance
-- ============================================================
-- 1. List user conversations with message counts
SELECT
    c.id,
    c.title,
    c.message_count,
    c.last_message_at,
    u.username
FROM
    conversation.conversations c
    JOIN core.users u ON c.user_id = u.id
WHERE
    c.deleted_at IS NULL
ORDER BY
    c.last_message_at DESC;

-- 2. View messages in a specific conversation
-- Replace :conv_id with actual UUID
SELECT
    role,
    content,
    created_at
FROM
    conversation.messages
WHERE
    conversation_id = 'REPLACE_WITH_UUID'
ORDER BY
    created_at ASC;

SELECT
    c.id,
    c.title,
    m.role,
    m.content,
    u.username
FROM
    conversation.messages m
    JOIN conversation.conversations c ON m.conversation_id = c.id
    JOIN core.users u ON c.user_id = u.id;

-- 3. Find unanswered questions (Knowledge Gaps)
SELECT
    question,
    search_query,
    top_similarity_score,
    priority,
    created_at
FROM
    conversation.unanswered_questions
WHERE
    resolved = FALSE
ORDER BY
    created_at DESC;

-- 4. Check AI sources for a message
SELECT
    sources
FROM
    conversation.messages
WHERE
    role = 'ASSISTANT'
    AND sources IS NOT NULL
ORDER BY
    created_at DESC
LIMIT
    10;