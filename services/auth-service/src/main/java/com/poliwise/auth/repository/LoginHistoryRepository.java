package com.poliwise.auth.repository;

import com.poliwise.auth.entity.LoginHistory;
import com.poliwise.auth.enums.LoginStatus;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface LoginHistoryRepository extends JpaRepository<LoginHistory, UUID> {

    Page<LoginHistory> findByUserIdOrderByCreatedAtDesc(UUID userId, Pageable pageable);

    Page<LoginHistory> findByUsernameIgnoreCaseOrderByCreatedAtDesc(String username,
            Pageable pageable);

    long countByUserIdAndStatusAndCreatedAtAfter(UUID userId, LoginStatus status, Instant since);

    long countByStatusAndCreatedAtBetween(LoginStatus status, Instant from, Instant to);

    Optional<LoginHistory> findFirstByUserIdOrderByCreatedAtDesc(UUID userId);

    Optional<LoginHistory> findFirstByUsernameIgnoreCaseOrderByCreatedAtDesc(String username);
}
