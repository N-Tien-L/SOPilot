package com.poliwise.feedback.service;

import com.poliwise.feedback.dto.request.FeedbackRequest;
import com.poliwise.feedback.dto.response.FeedbackResponse;
import com.poliwise.feedback.entity.Feedback;
import com.poliwise.feedback.exception.FeedbackNotFoundException;
import com.poliwise.feedback.exception.UnauthorizedFeedbackAccessException;
import com.poliwise.feedback.repository.FeedbackRepository;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Service
@Transactional
public class FeedbackService {

    private final FeedbackRepository feedbackRepository;

    public FeedbackService(FeedbackRepository feedbackRepository) {
        this.feedbackRepository = feedbackRepository;
    }

    public FeedbackResponse createFeedback(UUID userId, String userRole, UUID departmentId, FeedbackRequest request) {
        if (feedbackRepository.existsByUserIdAndMessageId(userId, request.messageId())) {
            throw new IllegalStateException("Feedback already exists for this message");
        }
        Feedback feedback = Feedback.builder()
                .userId(userId)
                .messageId(request.messageId())
                .conversationId(request.conversationId())
                .type(request.type())
                .comment(request.comment())
                .userRole(userRole)
                .userDepartmentId(departmentId)
                .build();
        Feedback saved = feedbackRepository.save(feedback);
        return FeedbackResponse.fromEntity(saved);
    }

    @Transactional(readOnly = true)
    public List<FeedbackResponse> getFeedbacksByConversation(UUID conversationId) {
        return feedbackRepository.findByConversationId(conversationId).stream()
                .map(FeedbackResponse::fromEntity).toList();
    }

    @Transactional(readOnly = true)
    public Page<FeedbackResponse> getFeedbacksByUser(UUID userId, Pageable pageable) {
        return feedbackRepository.findByUserId(userId, pageable).map(FeedbackResponse::fromEntity);
    }

    @Transactional(readOnly = true)
    public FeedbackResponse getFeedbackById(UUID id) {
        return feedbackRepository.findById(id)
                .map(FeedbackResponse::fromEntity)
                .orElseThrow(() -> new FeedbackNotFoundException(id));
    }

    public void deleteFeedback(UUID feedbackId, UUID userId, boolean isAdmin) {
        Feedback feedback = feedbackRepository.findById(feedbackId)
                .orElseThrow(() -> new FeedbackNotFoundException(feedbackId));
        if (!isAdmin && !feedback.getUserId().equals(userId)) {
            throw new UnauthorizedFeedbackAccessException();
        }
        feedbackRepository.delete(feedback);
    }
}
