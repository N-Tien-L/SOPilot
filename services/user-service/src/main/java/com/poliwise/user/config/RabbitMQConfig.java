package com.poliwise.user.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String USER_EXCHANGE = "poliwise.user.exchange";
    public static final String USER_STATUS_CHANGED_QUEUE = "poliwise.user.status.changed";
    public static final String USER_REVOKED_QUEUE = "poliwise.user.revoked";
    public static final String USER_PROFILE_UPDATED_QUEUE = "poliwise.user.profile.updated";
    public static final String USER_ROUTING_KEY_STATUS = "user.status.changed";
    public static final String USER_ROUTING_KEY_REVOKED = "user.revoked";
    public static final String USER_ROUTING_KEY_PROFILE = "user.profile.updated";

    // Department events
    public static final String DEPARTMENT_CREATED_QUEUE = "poliwise.department.created";
    public static final String DEPARTMENT_UPDATED_QUEUE = "poliwise.department.updated";
    public static final String DEPARTMENT_DELETED_QUEUE = "poliwise.department.deleted";
    public static final String USER_ASSIGNED_TO_DEPT_QUEUE = "poliwise.user.assigned.dept";
    public static final String USER_REMOVED_FROM_DEPT_QUEUE = "poliwise.user.removed.dept";
    public static final String USER_ROUTING_KEY_DEPT_CREATED = "department.created";
    public static final String USER_ROUTING_KEY_DEPT_UPDATED = "department.updated";
    public static final String USER_ROUTING_KEY_DEPT_DELETED = "department.deleted";
    public static final String USER_ROUTING_KEY_USER_ASSIGNED = "user.assigned.dept";
    public static final String USER_ROUTING_KEY_USER_REMOVED = "user.removed.dept";

    @Bean
    public TopicExchange userExchange() {
        return new TopicExchange(USER_EXCHANGE, true, false);
    }

    @Bean
    public Queue userStatusChangedQueue() {
        return QueueBuilder.durable(USER_STATUS_CHANGED_QUEUE).build();
    }

    @Bean
    public Queue userRevokedQueue() {
        return QueueBuilder.durable(USER_REVOKED_QUEUE).build();
    }

    @Bean
    public Queue userProfileUpdatedQueue() {
        return QueueBuilder.durable(USER_PROFILE_UPDATED_QUEUE).build();
    }

    @Bean
    public Queue departmentCreatedQueue() {
        return QueueBuilder.durable(DEPARTMENT_CREATED_QUEUE).build();
    }

    @Bean
    public Queue departmentUpdatedQueue() {
        return QueueBuilder.durable(DEPARTMENT_UPDATED_QUEUE).build();
    }

    @Bean
    public Queue departmentDeletedQueue() {
        return QueueBuilder.durable(DEPARTMENT_DELETED_QUEUE).build();
    }

    @Bean
    public Queue userAssignedToDeptQueue() {
        return QueueBuilder.durable(USER_ASSIGNED_TO_DEPT_QUEUE).build();
    }

    @Bean
    public Queue userRemovedFromDeptQueue() {
        return QueueBuilder.durable(USER_REMOVED_FROM_DEPT_QUEUE).build();
    }

    @Bean
    public Binding statusChangedBinding(Queue userStatusChangedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userStatusChangedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_STATUS);
    }

    @Bean
    public Binding revokedBinding(Queue userRevokedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userRevokedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_REVOKED);
    }

    @Bean
    public Binding profileUpdatedBinding(Queue userProfileUpdatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userProfileUpdatedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_PROFILE);
    }

    @Bean
    public Binding deptCreatedBinding(Queue departmentCreatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(departmentCreatedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_DEPT_CREATED);
    }

    @Bean
    public Binding deptUpdatedBinding(Queue departmentUpdatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(departmentUpdatedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_DEPT_UPDATED);
    }

    @Bean
    public Binding deptDeletedBinding(Queue departmentDeletedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(departmentDeletedQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_DEPT_DELETED);
    }

    @Bean
    public Binding userAssignedBinding(Queue userAssignedToDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userAssignedToDeptQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_USER_ASSIGNED);
    }

    @Bean
    public Binding userRemovedBinding(Queue userRemovedFromDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userRemovedFromDeptQueue)
                .to(userExchange)
                .with(USER_ROUTING_KEY_USER_REMOVED);
    }

    @Bean
    public MessageConverter jsonMessageConverter() {
        return new Jackson2JsonMessageConverter();
    }

    @Bean
    public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory, MessageConverter jsonMessageConverter) {
        RabbitTemplate template = new RabbitTemplate(connectionFactory);
        template.setMessageConverter(jsonMessageConverter);
        return template;
    }
}
