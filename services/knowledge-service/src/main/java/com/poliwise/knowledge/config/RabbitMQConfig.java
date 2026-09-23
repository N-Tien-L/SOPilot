package com.poliwise.knowledge.config;

import org.springframework.amqp.core.*;
import org.springframework.amqp.rabbit.connection.ConnectionFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.amqp.support.converter.Jackson2JsonMessageConverter;
import org.springframework.amqp.support.converter.MessageConverter;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class RabbitMQConfig {

    public static final String KNOWLEDGE_EXCHANGE = "poliwise.events";
    public static final String DOCUMENT_ROUTING_KEY_UPLOADED = "document.uploaded";
    public static final String DOCUMENT_ROUTING_KEY_DELETED = "document.deleted";
    public static final String DOCUMENT_ROUTING_KEY_VERSION_CREATED = "document.version.created";
    public static final String INGESTION_ROUTING_KEY_REQUESTED = "ingestion.requested";

    @Bean
    public TopicExchange knowledgeExchange() {
        return new TopicExchange(KNOWLEDGE_EXCHANGE, true, false);
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