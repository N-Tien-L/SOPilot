package com.poliwise.metadata;

import com.poliwise.metadata.feign.FeignConfig;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.cloud.openfeign.EnableFeignClients;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@ConfigurationPropertiesScan
@EnableScheduling
@EnableFeignClients(defaultConfiguration = FeignConfig.class)
public class MetadataServiceApplication {

	public static void main(String[] args) {
		SpringApplication.run(MetadataServiceApplication.class, args);
	}
}