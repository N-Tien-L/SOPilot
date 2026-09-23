package com.poliwise.user.config;

import com.poliwise.user.entity.Department;
import com.poliwise.user.repository.DepartmentRepository;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.transaction.annotation.Transactional;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

@Configuration
public class DataInitializer {

    private static final Logger log = LoggerFactory.getLogger(DataInitializer.class);

    @Bean
    @Transactional
    public CommandLineRunner initDepartments(DepartmentRepository departmentRepository) {
        return args -> {
            if (departmentRepository.count() > 0) {
                log.info("Departments already initialized, skipping...");
                return;
            }

            log.info("Initializing default departments...");

            List<Department> defaultDepartments = List.of(
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000001"), "Kỹ thuật", "ENG", "Phòng ban kỹ thuật và phát triển"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000002"), "Nhân sự", "HR", "Phòng ban nhân sự và hành chính"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000003"), "Tài chính", "FIN", "Phòng ban tài chính và kế toán"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000004"), "Pháp lý", "LEGAL", "Phòng ban pháp lý và tuân thủ"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000005"), "Vận hành", "OPS", "Phòng ban vận hành và hỗ trợ"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000006"), "Marketing", "MKT", "Phòng ban marketing và truyền thông"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000007"), "Công nghệ thông tin", "IT", "Phòng ban IT và hạ tầng"),
                    createDepartment(UUID.fromString("00000000-0000-0000-0000-000000000008"), "Quản trị", "ADMIN", "Phòng ban quản trị hệ thống")
            );

            for (Department dept : defaultDepartments) {
                departmentRepository.save(dept);
                log.info("Created department: {} ({})", dept.getName(), dept.getCode());
            }

            log.info("Successfully initialized {} departments", defaultDepartments.size());
        };
    }

    private Department createDepartment(UUID id, String name, String code, String description) {
        OffsetDateTime now = OffsetDateTime.now();
        return Department.builder()
                .id(id)
                .name(name)
                .code(code)
                .description(description)
                .isActive(true)
                .createdAt(now)
                .updatedAt(now)
                .build();
    }
}