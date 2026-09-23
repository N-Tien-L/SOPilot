package com.poliwise.auth.event;

import com.poliwise.auth.config.RabbitMQConfig;
import com.poliwise.auth.dto.event.UserRegisteredEvent;
import com.poliwise.auth.dto.event.UserStatusChangedEvent;
import com.poliwise.auth.dto.event.LoginAuditEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class AuthEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(AuthEventPublisher.class);

    private final RabbitTemplate rabbitTemplate;

    public AuthEventPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishUserRegistered(UserRegisteredEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.AUTH_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_REGISTERED,
                event
        );
        log.info("Published UserRegisteredEvent: userId={}, username={}, role={}, registeredBy={}",
                event.userId(), event.username(), event.role(), event.registeredBy());
    }

    public void publishStatusChanged(UserStatusChangedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.AUTH_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_STATUS,
                event
        );
        log.info("Published UserStatusChangedEvent: userId={}, from={} to={}",
                event.userId(), event.previousStatus(), event.newStatus());
    }

    public void publishLoginSuccess(LoginAuditEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.AUTH_EXCHANGE,
                "user.login.success",
                event
        );
        log.info("Published LoginAuditEvent (success): userId={}, username={}",
                event.userId(), event.username());
    }

    public void publishLoginFailed(LoginAuditEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.AUTH_EXCHANGE,
                "user.login.failed",
                event
        );
        log.info("Published LoginAuditEvent (failed): username={}, reason={}",
                event.username(), event.failureReason());
    }

    public void publishLogout(LoginAuditEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.AUTH_EXCHANGE,
                "user.logout",
                event
        );
        log.info("Published LoginAuditEvent (logout): userId={}, username={}",
                event.userId(), event.username());
    }
}