package com.poliwise.feedback;

import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableAsync;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
@EnableAsync
@EnableFeignClients
public class FeedbackServiceApplication {

    public static void main(String[] args) {
        SpringApplication.run(FeedbackServiceApplication.class, args);
    }
}
