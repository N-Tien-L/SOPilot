package com.poliwise.feedback.consumer;

import com.poliwise.feedback.config.RabbitMQConfig;
import com.poliwise.feedback.entity.PopularQuestion;
import com.poliwise.feedback.entity.UnansweredQuestion;
import com.poliwise.feedback.repository.PopularQuestionRepository;
import com.poliwise.feedback.repository.UnansweredQuestionRepository;
import com.poliwise.feedback.service.AuditLogService;
import com.poliwise.feedback.enums.AuditAction;
import com.poliwise.feedback.enums.PriorityLevel;
import com.poliwise.feedback.enums.ResourceType;
import com.poliwise.feedback.enums.UnansweredStatus;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.text.Normalizer;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;
import java.util.regex.Pattern;

@Component
public class UnansweredQuestionConsumer {

    private static final Logger log = LoggerFactory.getLogger(UnansweredQuestionConsumer.class);
    private static final Pattern NON_ALPHANUMERIC = Pattern.compile("[^a-zA-Z0-9\\s]");

    private final UnansweredQuestionRepository unansweredQuestionRepository;
    private final PopularQuestionRepository popularQuestionRepository;
    private final AuditLogService auditLogService;

    public UnansweredQuestionConsumer(UnansweredQuestionRepository unansweredQuestionRepository,
                                     PopularQuestionRepository popularQuestionRepository,
                                     AuditLogService auditLogService) {
        this.unansweredQuestionRepository = unansweredQuestionRepository;
        this.popularQuestionRepository = popularQuestionRepository;
        this.auditLogService = auditLogService;
    }

    @RabbitListener(queues = RabbitMQConfig.QUEUE_UNANSWERED)
    @Transactional
    public void handleUnansweredQuestion(Map<String, Object> message) {
        try {
            // Extract payload from Python event (wrapped in "payload" key)
            Map<String, Object> payload = (Map<String, Object>) message.get("payload");
            if (payload == null) {
                log.error("Message missing 'payload' key: {}", message.keySet());
                return;
            }
            
            String question = (String) payload.get("question");
            UUID userId = parseUUID(payload.get("user_id"));
            UUID messageId = parseUUID(payload.get("message_id"));
            UUID conversationId = parseUUID(payload.get("conversation_id"));
            String userRole = (String) payload.getOrDefault("user_role", "USER");
            UUID departmentId = parseUUID(payload.get("user_department_id"));
            String category = (String) payload.get("category");
            String searchQuery = (String) payload.getOrDefault("search_query", question);
            Double similarity = (Double) payload.get("top_similarity_score");
            PriorityLevel priority = parsePriority(payload.get("priority"));

            UnansweredQuestion uq = UnansweredQuestion.builder()
                    .userId(userId)
                    .messageId(messageId)
                    .conversationId(conversationId)
                    .question(question)
                    .questionNormalized(normalizeQuestion(question))
                    .userRole(userRole)
                    .userDepartmentId(departmentId)
                    .category(category)
                    .searchQuery(searchQuery)
                    .topSimilarityScore(similarity != null ? BigDecimal.valueOf(similarity) : null)
                    .status(UnansweredStatus.PENDING)
                    .resolved(false)
                    .priority(priority)
                    .build();
            unansweredQuestionRepository.save(uq);

            updatePopularQuestion(question, userId);

            auditLogService.logAction(userId, null, userRole,
                    AuditAction.QUESTION_ASK, ResourceType.CONVERSATION, conversationId,
                    question, null, null, null, "feedback-service", Map.of("unanswered", true));

            log.info("Saved unanswered question from user {}: {}", userId, question.substring(0, Math.min(50, question.length())));
        } catch (Exception e) {
            log.error("Failed to handle unanswered question message", e);
        }
    }

    private void updatePopularQuestion(String question, UUID userId) {
        String normalized = normalizeQuestion(question);
        Optional<PopularQuestion> existing = popularQuestionRepository.findByQuestionNormalized(normalized);
        if (existing.isPresent()) {
            PopularQuestion pq = existing.get();
            pq.setAskCount(pq.getAskCount() + 1);
            pq.setLastAskedAt(Instant.now());
            popularQuestionRepository.save(pq);
        } else {
            PopularQuestion pq = PopularQuestion.builder()
                    .questionNormalized(normalized)
                    .questionSample(question.length() > 500 ? question.substring(0, 500) : question)
                    .askCount(1)
                    .uniqueUsersCount(1)
                    .firstAskedAt(Instant.now())
                    .lastAskedAt(Instant.now())
                    .build();
            popularQuestionRepository.save(pq);
        }
    }

    private String normalizeQuestion(String text) {
        if (text == null) return "";
        String normalized = Normalizer.normalize(text.toLowerCase(), Normalizer.Form.NFD);
        normalized = NON_ALPHANUMERIC.matcher(normalized).replaceAll(" ");
        return normalized.trim().replaceAll("\\s+", " ");
    }

    private UUID parseUUID(Object value) {
        if (value == null) return null;
        if (value instanceof UUID) return (UUID) value;
        try { return UUID.fromString(value.toString()); }
        catch (Exception e) { return null; }
    }

    private PriorityLevel parsePriority(Object value) {
        if (value == null) {
            return PriorityLevel.NORMAL;
        }
        try {
            return PriorityLevel.valueOf(value.toString().trim().toUpperCase());
        } catch (Exception ignored) {
            return PriorityLevel.NORMAL;
        }
    }
}
