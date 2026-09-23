package com.poliwise.auth.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String AUTH_EXCHANGE = "poliwise.auth.exchange";
    public static final String USER_REGISTERED_QUEUE = "poliwise.auth.user.registered";
    public static final String USER_STATUS_CHANGED_QUEUE = "poliwise.auth.user.status.changed";
    public static final String USER_ROUTING_KEY_REGISTERED = "user.registered";
    public static final String USER_ROUTING_KEY_STATUS = "user.status.changed";

    // Queue nhận events từ user-service
    public static final String USER_SERVICE_STATUS_QUEUE = "poliwise.user.status.received";

    // Queue cho audit events từ user-service
    public static final String DEPT_CREATED_QUEUE = "poliwise.department.created";
    public static final String DEPT_UPDATED_QUEUE = "poliwise.department.updated";
    public static final String DEPT_DELETED_QUEUE = "poliwise.department.deleted";
    public static final String USER_ASSIGNED_DEPT_QUEUE = "poliwise.user.assigned.dept";
    public static final String USER_REMOVED_DEPT_QUEUE = "poliwise.user.removed.dept";

    @Bean
    public TopicExchange authExchange() {
        return new TopicExchange(AUTH_EXCHANGE, true, false);
    }

    @Bean
    public Queue userRegisteredQueue() {
        return QueueBuilder.durable(USER_REGISTERED_QUEUE).build();
    }

    @Bean
    public Queue userStatusChangedQueue() {
        return QueueBuilder.durable(USER_STATUS_CHANGED_QUEUE).build();
    }

    // Queue nhận status changed events từ user-service
    @Bean
    public Queue userServiceStatusQueue() {
        return QueueBuilder.durable(USER_SERVICE_STATUS_QUEUE).build();
    }

    // Queue cho audit events từ user-service
    @Bean
    public Queue deptCreatedQueue() {
        return QueueBuilder.durable(DEPT_CREATED_QUEUE).build();
    }

    @Bean
    public Queue deptUpdatedQueue() {
        return QueueBuilder.durable(DEPT_UPDATED_QUEUE).build();
    }

    @Bean
    public Queue deptDeletedQueue() {
        return QueueBuilder.durable(DEPT_DELETED_QUEUE).build();
    }

    @Bean
    public Queue userAssignedDeptQueue() {
        return QueueBuilder.durable(USER_ASSIGNED_DEPT_QUEUE).build();
    }

    @Bean
    public Queue userRemovedDeptQueue() {
        return QueueBuilder.durable(USER_REMOVED_DEPT_QUEUE).build();
    }

    @Bean
    public Binding userRegisteredBinding(Queue userRegisteredQueue, TopicExchange authExchange) {
        return BindingBuilder.bind(userRegisteredQueue)
                .to(authExchange)
                .with(USER_ROUTING_KEY_REGISTERED);
    }

    // Note: All queues are declared by feedback-service. Auth service only creates bindings to forward messages.

    @Bean
    public Binding userStatusChangedBinding(Queue userStatusChangedQueue, TopicExchange authExchange) {
        return BindingBuilder.bind(userStatusChangedQueue)
                .to(authExchange)
                .with(USER_ROUTING_KEY_STATUS);
    }

    // Exchange của user-service để nhận events
    @Bean
    public TopicExchange userExchange() {
        return new TopicExchange("poliwise.user.exchange", true, false);
    }

    // Binding để nhận events từ user-service exchange
    @Bean
    public Binding userServiceStatusBinding(Queue userServiceStatusQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userServiceStatusQueue)
                .to(userExchange)
                .with("user.status.changed");
    }

    // Bindings cho audit events từ user-service
    @Bean
    public Binding deptCreatedBinding(Queue deptCreatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptCreatedQueue)
                .to(userExchange)
                .with("department.created");
    }

    @Bean
    public Binding deptUpdatedBinding(Queue deptUpdatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptUpdatedQueue)
                .to(userExchange)
                .with("department.updated");
    }

    @Bean
    public Binding deptDeletedBinding(Queue deptDeletedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptDeletedQueue)
                .to(userExchange)
                .with("department.deleted");
    }

    @Bean
    public Binding userAssignedDeptBinding(Queue userAssignedDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userAssignedDeptQueue)
                .to(userExchange)
                .with("user.assigned.dept");
    }

    @Bean
    public Binding userRemovedDeptBinding(Queue userRemovedDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userRemovedDeptQueue)
                .to(userExchange)
                .with("user.removed.dept");
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
