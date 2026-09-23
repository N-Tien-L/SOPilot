package com.poliwise.auth.event;

import com.poliwise.auth.config.RabbitMQConfig;
import com.poliwise.auth.dto.event.UserStatusChangedEvent;
import com.poliwise.auth.service.EmailService;
import com.poliwise.auth.service.UserManagementService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.stereotype.Component;

/**
 * Event listener nhận các events từ user-service và xử lý:
 * - Gửi email notification khi tài khoản bị thay đổi trạng thái
 * - Gửi email notification khi tài khoản bị xóa mềm (soft delete)
 */
@Component
public class UserStatusEventListener {

    private static final Logger log = LoggerFactory.getLogger(UserStatusEventListener.class);

    private final EmailService emailService;
    private final UserManagementService userManagementService;

    public UserStatusEventListener(EmailService emailService, UserManagementService userManagementService) {
        this.emailService = emailService;
        this.userManagementService = userManagementService;
    }

    /**
     * Lắng nghe event thay đổi trạng thái tài khoản từ user-service.
     * Gửi email notification cho người dùng về trạng thái mới.
     */
    @RabbitListener(queues = RabbitMQConfig.USER_SERVICE_STATUS_QUEUE)
    public void handleUserStatusChanged(UserStatusChangedEvent event) {
        log.info("Received UserStatusChangedEvent: userId={}, from={} to={}, username={}",
                event.userId(), event.previousStatus(), event.newStatus(), event.username());

        try {
            String adminName = getAdminName(event.changedBy());
            String toEmail = getUserEmail(event.userId());

            if (toEmail == null) {
                log.warn("Cannot send status change email: user {} has no email", event.userId());
                return;
            }

            switch (event.newStatus()) {
                case DEACTIVATED -> emailService.sendAccountDeactivatedEmail(toEmail, event.username(), adminName);
                case ACTIVE -> emailService.sendAccountReactivatedEmail(toEmail, event.username(), adminName);
                case REVOKED -> emailService.sendAccountRevokedEmail(toEmail, event.username(), adminName);
                default -> log.warn("Unknown status: {}", event.newStatus());
            }

            log.info("Status change email sent successfully to {} for user {}", toEmail, event.username());
        } catch (Exception e) {
            log.error("Failed to send status change email for user {}: {}", event.userId(), e.getMessage(), e);
        }
    }

    private String getUserEmail(java.util.UUID userId) {
        try {
            return userManagementService.getUserById(userId).email();
        } catch (Exception e) {
            log.warn("Could not fetch user email for {}: {}", userId, e.getMessage());
            return null;
        }
    }

    private String getAdminName(java.util.UUID adminId) {
        if (adminId == null) return "Administrator";
        try {
            return userManagementService.getUserById(adminId).username();
        } catch (Exception e) {
            return "Administrator";
        }
    }
}
