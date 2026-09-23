package com.poliwise.auth.entity;

import jakarta.persistence.*;
import lombok.*;
import java.time.Instant;
import java.util.UUID;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Entity
@Table(name = "access_token_blacklist", schema = "core")
public class AccessTokenBlacklist {

    @Id
    @Column(name = "jti", nullable = false)
    private String jti;

    @Column(name = "user_id", nullable = false)
    private UUID userId;

    @Column(name = "expired_at", nullable = false)
    private Instant expiredAt;

    @Column(name = "blacklisted_at", nullable = false)
    private Instant blacklistedAt;

    @Column(name = "reason", length = 100)
    private String reason;

    @PrePersist
    public void prePersist() {
        if (this.blacklistedAt == null) {
            this.blacklistedAt = Instant.now();
        }
    }
}
