package com.poliwise.metadata.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String METADATA_EXCHANGE = "poliwise.metadata.exchange";
    public static final String DOCUMENT_UPLOADED_QUEUE = "poliwise.metadata.document.uploaded";
    public static final String DOCUMENT_DELETED_QUEUE = "poliwise.metadata.document.deleted";
    public static final String DOCUMENT_ROUTING_KEY_UPLOADED = "document.uploaded";
    public static final String DOCUMENT_ROUTING_KEY_DELETED = "document.deleted";

    @Bean
    public TopicExchange metadataExchange() {
        return new TopicExchange(METADATA_EXCHANGE, true, false);
    }

    @Bean
    public Queue documentUploadedQueue() {
        return QueueBuilder.durable(DOCUMENT_UPLOADED_QUEUE).build();
    }

    @Bean
    public Queue documentDeletedQueue() {
        return QueueBuilder.durable(DOCUMENT_DELETED_QUEUE).build();
    }

    @Bean
    public Binding documentUploadedBinding(Queue documentUploadedQueue, TopicExchange metadataExchange) {
        return BindingBuilder.bind(documentUploadedQueue)
                .to(metadataExchange)
                .with(DOCUMENT_ROUTING_KEY_UPLOADED);
    }

    @Bean
    public Binding documentDeletedBinding(Queue documentDeletedQueue, TopicExchange metadataExchange) {
        return BindingBuilder.bind(documentDeletedQueue)
                .to(metadataExchange)
                .with(DOCUMENT_ROUTING_KEY_DELETED);
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