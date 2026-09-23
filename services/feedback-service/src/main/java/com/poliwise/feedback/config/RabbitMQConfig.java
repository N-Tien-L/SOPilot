package com.poliwise.feedback.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.config.RetryInterceptorBuilder;
import org.springframework.amqp.rabbit.config.SimpleRabbitListenerContainerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.rabbit.retry.MessageRecoverer;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String EXCHANGE_NAME = "poliwise.events";
    public static final String USER_EXCHANGE_NAME = "poliwise.user.exchange";
    public static final String AUTH_EXCHANGE_NAME = "poliwise.auth.exchange";
    public static final String QUEUE_UNANSWERED = "poliwise.feedback.unanswered";
    public static final String QUEUE_DOCUMENT = "poliwise.feedback.document";
    public static final String QUEUE_USER = "poliwise.feedback.user";
    public static final String QUEUE_USER_PROFILE = "poliwise.feedback.user.profile";
    public static final String QUEUE_AUTH_LOGIN = "poliwise.feedback.auth.login";
    public static final String QUEUE_USER_REGISTERED = "poliwise.feedback.user.registered";
    public static final String ROUTING_UNANSWERED = "unanswered.question";
    public static final String ROUTING_DOCUMENT_UPLOADED = "document.uploaded";
    public static final String ROUTING_DOCUMENT_DELETED = "document.deleted";
    public static final String ROUTING_DOCUMENT_VERSION_CREATED = "document.version.created";
    public static final String ROUTING_USER_STATUS = "user.status.changed";
    public static final String ROUTING_USER_PROFILE = "user.profile.updated";
    public static final String ROUTING_AUTH_LOGIN = "user.login.*";
    public static final String ROUTING_USER_REGISTERED = "user.registered";
    public static final String QUEUE_REPORT_EXPORT = "poliwise.feedback.report.export";
    public static final String ROUTING_REPORT_EXPORT = "report.export.requested";
    public static final String DEAD_LETTER_EXCHANGE_NAME = EXCHANGE_NAME + ".dlx";
    public static final String QUEUE_REPORT_EXPORT_DLQ = QUEUE_REPORT_EXPORT + ".dlq";

    // Department events
    public static final String QUEUE_DEPT_CREATED = "poliwise.feedback.dept.created";
    public static final String QUEUE_DEPT_UPDATED = "poliwise.feedback.dept.updated";
    public static final String QUEUE_DEPT_DELETED = "poliwise.feedback.dept.deleted";
    public static final String QUEUE_USER_ASSIGNED_DEPT = "poliwise.feedback.user.assigned.dept";
    public static final String QUEUE_USER_REMOVED_DEPT = "poliwise.feedback.user.removed.dept";
    public static final String ROUTING_DEPT_CREATED = "department.created";
    public static final String ROUTING_DEPT_UPDATED = "department.updated";
    public static final String ROUTING_DEPT_DELETED = "department.deleted";
    public static final String ROUTING_USER_ASSIGNED = "user.assigned.dept";
    public static final String ROUTING_USER_REMOVED = "user.removed.dept";

    @Bean public TopicExchange poliwiseExchange() { return new TopicExchange(EXCHANGE_NAME); }
    @Bean public TopicExchange poliwiseDeadLetterExchange() { return new TopicExchange(DEAD_LETTER_EXCHANGE_NAME); }
    @Bean public TopicExchange userExchange() { return new TopicExchange(USER_EXCHANGE_NAME, true, false); }
    @Bean public TopicExchange authExchange() { return new TopicExchange(AUTH_EXCHANGE_NAME, true, false); }

    @Bean public Queue unansweredQueue() {
        return QueueBuilder.durable(QUEUE_UNANSWERED).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue documentQueue() {
        return QueueBuilder.durable(QUEUE_DOCUMENT).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue userQueue() {
        return QueueBuilder.durable(QUEUE_USER).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue userProfileQueue() {
        return QueueBuilder.durable(QUEUE_USER_PROFILE).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue authLoginQueue() {
        return QueueBuilder.durable(QUEUE_AUTH_LOGIN).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue userRegisteredQueue() {
        return QueueBuilder.durable(QUEUE_USER_REGISTERED).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue reportExportQueue() {
        return QueueBuilder.durable(QUEUE_REPORT_EXPORT).withArgument("x-dead-letter-exchange", DEAD_LETTER_EXCHANGE_NAME).build();
    }
    @Bean public Queue reportExportDeadLetterQueue() { return QueueBuilder.durable(QUEUE_REPORT_EXPORT_DLQ).build(); }

    // Department queues
    @Bean public Queue deptCreatedQueue() {
        return QueueBuilder.durable(QUEUE_DEPT_CREATED).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue deptUpdatedQueue() {
        return QueueBuilder.durable(QUEUE_DEPT_UPDATED).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue deptDeletedQueue() {
        return QueueBuilder.durable(QUEUE_DEPT_DELETED).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue userAssignedDeptQueue() {
        return QueueBuilder.durable(QUEUE_USER_ASSIGNED_DEPT).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }
    @Bean public Queue userRemovedDeptQueue() {
        return QueueBuilder.durable(QUEUE_USER_REMOVED_DEPT).withArgument("x-dead-letter-exchange", EXCHANGE_NAME + ".dlx").build();
    }

    @Bean public Binding unansweredBinding(Queue unansweredQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(unansweredQueue).to(poliwiseExchange).with(ROUTING_UNANSWERED);
    }
    @Bean public Binding documentUploadedBinding(Queue documentQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(documentQueue).to(poliwiseExchange).with(ROUTING_DOCUMENT_UPLOADED);
    }
    @Bean public Binding documentDeletedBinding(Queue documentQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(documentQueue).to(poliwiseExchange).with(ROUTING_DOCUMENT_DELETED);
    }
    @Bean public Binding documentVersionCreatedBinding(Queue documentQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(documentQueue).to(poliwiseExchange).with(ROUTING_DOCUMENT_VERSION_CREATED);
    }
    @Bean public Binding userStatusBindingFromEvents(Queue userQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(userQueue).to(poliwiseExchange).with(ROUTING_USER_STATUS);
    }
    @Bean public Binding userStatusBindingFromUserExchange(Queue userQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userQueue).to(userExchange).with(ROUTING_USER_STATUS);
    }
    @Bean public Binding userProfileBinding(Queue userProfileQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userProfileQueue).to(userExchange).with(ROUTING_USER_PROFILE);
    }
    @Bean public Binding authLoginBinding(Queue authLoginQueue, TopicExchange authExchange) {
        return BindingBuilder.bind(authLoginQueue).to(authExchange).with(ROUTING_AUTH_LOGIN);
    }
    @Bean public Binding userRegisteredBinding(Queue userRegisteredQueue, TopicExchange authExchange) {
        return BindingBuilder.bind(userRegisteredQueue).to(authExchange).with(ROUTING_USER_REGISTERED);
    }
    @Bean public Binding reportExportBinding(Queue reportExportQueue, TopicExchange poliwiseExchange) {
        return BindingBuilder.bind(reportExportQueue).to(poliwiseExchange).with(ROUTING_REPORT_EXPORT);
    }
    @Bean public Binding reportExportDeadLetterBinding(
            Queue reportExportDeadLetterQueue,
            TopicExchange poliwiseDeadLetterExchange) {
        return BindingBuilder.bind(reportExportDeadLetterQueue)
                .to(poliwiseDeadLetterExchange)
                .with(ROUTING_REPORT_EXPORT);
    }

    // Department bindings
    @Bean public Binding deptCreatedBinding(Queue deptCreatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptCreatedQueue).to(userExchange).with(ROUTING_DEPT_CREATED);
    }
    @Bean public Binding deptUpdatedBinding(Queue deptUpdatedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptUpdatedQueue).to(userExchange).with(ROUTING_DEPT_UPDATED);
    }
    @Bean public Binding deptDeletedBinding(Queue deptDeletedQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(deptDeletedQueue).to(userExchange).with(ROUTING_DEPT_DELETED);
    }
    @Bean public Binding userAssignedDeptBinding(Queue userAssignedDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userAssignedDeptQueue).to(userExchange).with(ROUTING_USER_ASSIGNED);
    }
    @Bean public Binding userRemovedDeptBinding(Queue userRemovedDeptQueue, TopicExchange userExchange) {
        return BindingBuilder.bind(userRemovedDeptQueue).to(userExchange).with(ROUTING_USER_REMOVED);
    }

    @Bean public MessageConverter jsonMessageConverter() { return new Jackson2JsonMessageConverter(); }
    @Bean public RabbitTemplate rabbitTemplate(ConnectionFactory connectionFactory) {
        RabbitTemplate t = new RabbitTemplate(connectionFactory);
        t.setMessageConverter(jsonMessageConverter());
        return t;
    }

    @Bean
    public SimpleRabbitListenerContainerFactory reportExportRabbitListenerContainerFactory(
            ConnectionFactory connectionFactory,
            MessageConverter messageConverter,
            MessageRecoverer reportExportMessageRecoverer) {
        SimpleRabbitListenerContainerFactory factory = new SimpleRabbitListenerContainerFactory();
        factory.setConnectionFactory(connectionFactory);
        factory.setMessageConverter(messageConverter);
        factory.setAdviceChain(RetryInterceptorBuilder.stateless()
                .maxAttempts(3)
                .backOffOptions(1_000, 2.0, 5_000)
                .recoverer(reportExportMessageRecoverer)
                .build());
        return factory;
    }
}
