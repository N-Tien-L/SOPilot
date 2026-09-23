package com.poliwise.user.event;

import com.poliwise.user.config.RabbitMQConfig;
import com.poliwise.user.dto.event.UserRevokedEvent;
import com.poliwise.user.dto.event.UserStatusChangedEvent;
import com.poliwise.user.dto.event.ProfileUpdatedEvent;
import com.poliwise.user.dto.event.DepartmentCreatedEvent;
import com.poliwise.user.dto.event.DepartmentUpdatedEvent;
import com.poliwise.user.dto.event.DepartmentDeletedEvent;
import com.poliwise.user.dto.event.UserAssignedToDepartmentEvent;
import com.poliwise.user.dto.event.UserRemovedFromDepartmentEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class UserEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(UserEventPublisher.class);

    private final RabbitTemplate rabbitTemplate;

    public UserEventPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishStatusChanged(UserStatusChangedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_STATUS,
                event
        );
        log.info("Published UserStatusChangedEvent: userId={}, from={} to={}",
                event.userId(), event.previousStatus(), event.newStatus());
    }

    public void publishRevoked(UserRevokedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_REVOKED,
                event
        );
        log.info("Published UserRevokedEvent: userId={}, revokedBy={}",
                event.userId(), event.revokedBy());
    }

    public void publishProfileUpdated(ProfileUpdatedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_PROFILE,
                event
        );
        log.info("Published ProfileUpdatedEvent: userId={}, updatedBy={}",
                event.userId(), event.updatedBy());
    }

    // Department events
    public void publishDepartmentCreated(DepartmentCreatedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_DEPT_CREATED,
                event
        );
        log.info("Published DepartmentCreatedEvent: departmentId={}, name={}",
                event.departmentId(), event.departmentName());
    }

    public void publishDepartmentUpdated(DepartmentUpdatedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_DEPT_UPDATED,
                event
        );
        log.info("Published DepartmentUpdatedEvent: departmentId={}, name={}",
                event.departmentId(), event.departmentName());
    }

    public void publishDepartmentDeleted(DepartmentDeletedEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_DEPT_DELETED,
                event
        );
        log.info("Published DepartmentDeletedEvent: departmentId={}, name={}",
                event.departmentId(), event.departmentName());
    }

    public void publishUserAssignedToDepartment(UserAssignedToDepartmentEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_USER_ASSIGNED,
                event
        );
        log.info("Published UserAssignedToDepartmentEvent: userId={}, deptId={}",
                event.userId(), event.departmentId());
    }

    public void publishUserRemovedFromDepartment(UserRemovedFromDepartmentEvent event) {
        rabbitTemplate.convertAndSend(
                RabbitMQConfig.USER_EXCHANGE,
                RabbitMQConfig.USER_ROUTING_KEY_USER_REMOVED,
                event
        );
        log.info("Published UserRemovedFromDepartmentEvent: userId={}, deptId={}",
                event.userId(), event.departmentId());
    }
}
