package com.poliwise.feedback.controller;

import com.poliwise.feedback.dto.request.FeedbackRequest;
import com.poliwise.feedback.dto.response.ApiResponse;
import com.poliwise.feedback.dto.response.FeedbackResponse;
import com.poliwise.feedback.security.JwtAuthenticationToken;
import com.poliwise.feedback.security.UserPrincipal;
import com.poliwise.feedback.service.FeedbackService;
import jakarta.validation.Valid;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableDefault;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/feedback")
public class FeedbackController {

    private final FeedbackService feedbackService;

    public FeedbackController(FeedbackService feedbackService) {
        this.feedbackService = feedbackService;
    }

    @PostMapping
    public ResponseEntity<ApiResponse<FeedbackResponse>> createFeedback(
            @Valid @RequestBody FeedbackRequest request, Authentication authentication) {
        UserPrincipal principal = getPrincipal(authentication);
        FeedbackResponse response = feedbackService.createFeedback(
                principal.getUserId(), principal.getRole(), principal.getDepartmentId(), request);
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.success(response, "Feedback submitted successfully"));
    }

    @GetMapping("/conversation/{conversationId}")
    public ResponseEntity<ApiResponse<List<FeedbackResponse>>> getByConversation(@PathVariable UUID conversationId) {
        return ResponseEntity.ok(ApiResponse.success(feedbackService.getFeedbacksByConversation(conversationId)));
    }

    @GetMapping("/my")
    public ResponseEntity<ApiResponse<Page<FeedbackResponse>>> getMyFeedbacks(
            Authentication authentication, @PageableDefault(size = 20) Pageable pageable) {
        UserPrincipal principal = getPrincipal(authentication);
        return ResponseEntity.ok(ApiResponse.success(feedbackService.getFeedbacksByUser(principal.getUserId(), pageable)));
    }

    @GetMapping("/{id}")
    public ResponseEntity<ApiResponse<FeedbackResponse>> getById(@PathVariable UUID id) {
        return ResponseEntity.ok(ApiResponse.success(feedbackService.getFeedbackById(id)));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<ApiResponse<Void>> deleteFeedback(@PathVariable UUID id, Authentication authentication) {
        UserPrincipal principal = getPrincipal(authentication);
        feedbackService.deleteFeedback(id, principal.getUserId(), "ADMIN".equals(principal.getRole()));
        return ResponseEntity.ok(ApiResponse.success(null, "Feedback deleted successfully"));
    }

    private UserPrincipal getPrincipal(Authentication authentication) {
        if (authentication instanceof JwtAuthenticationToken jwtAuth) return (UserPrincipal) jwtAuth.getPrincipal();
        throw new IllegalStateException("Invalid authentication type");
    }
}
