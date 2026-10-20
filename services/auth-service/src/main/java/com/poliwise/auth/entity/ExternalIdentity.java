package com.poliwise.auth.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "external_identities", schema = "core")
@Getter
@NoArgsConstructor
public class ExternalIdentity {
    @Id
    private UUID id;
    @Column(name = "user_id", nullable = false)
    private UUID userId;
    @Column(nullable = false, length = 255)
    private String issuer;
    @Column(nullable = false, length = 255)
    private String subject;
    @Column(name = "email_at_link", nullable = false, length = 255)
    private String emailAtLink;
    @Column(name = "created_at", nullable = false)
    private OffsetDateTime createdAt;
}
