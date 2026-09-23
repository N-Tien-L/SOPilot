package com.poliwise.user.entity;

import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.OffsetDateTime;
import java.util.UUID;

@Entity
@Table(name = "users", schema = "core")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class User {

    @Id
    @EqualsAndHashCode.Include
    @Column(columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @Column(nullable = false, length = 100)
    private String username;

    @Column(nullable = false, length = 255)
    private String email;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(columnDefinition = "core.user_role", nullable = false)
    private UserRole role;

    @JdbcTypeCode(SqlTypes.NAMED_ENUM)
    @Column(name = "status", nullable = false)
    private AccountStatus status;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "department_id", foreignKey = @ForeignKey(name = "fk_users_department"))
    @ToString.Exclude
    private Department department;

    @OneToOne(mappedBy = "user", fetch = FetchType.LAZY, cascade = CascadeType.ALL,
            orphanRemoval = true)
    @ToString.Exclude
    private UserProfile profile;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    /**
     * So lan vi pham chinh sach cua nguoi dung. Duoc tang khi Layer 1 chan query.
     * Nguong: 3 -> warn, 5 -> deactivate, 10 -> revoke.
     */
    @Column(name = "strike_count")
    private Integer strikeCount;

    /**
     * Thoi diem vi pham gan nhat. Cap nhat moi khi co vi pham moi.
     */
    @Column(name = "last_violation_at")
    private OffsetDateTime lastViolationAt;

    /**
     * Thoi diem tai khoan bi vo hieu hoa (deactivated).
     */
    @Column(name = "deactivated_at")
    private OffsetDateTime deactivatedAt;

    /**
     * Thoi diem tai khoan bi thu hoi (revoked).
     */
    @Column(name = "revoked_at")
    private OffsetDateTime revokedAt;

    @PrePersist
    void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
        if (status == null) status = AccountStatus.ACTIVE;
        if (strikeCount == null) strikeCount = 0;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = OffsetDateTime.now();
    }

    public boolean isActive() { return status == AccountStatus.ACTIVE; }

    // Explicit accessors (Lombok processor does not generate them in this JDK 23 environment)
    public UUID           getId()           { return id; }
    public String         getUsername()     { return username; }
    public String         getEmail()       { return email; }
    public UserRole       getRole()        { return role; }
    public AccountStatus  getStatus(){ return status; }
    public Department      getDepartment()  { return department; }
    public UserProfile    getProfile()     { return profile; }
    public OffsetDateTime getCreatedAt()   { return createdAt; }
    public OffsetDateTime getUpdatedAt()   { return updatedAt; }
    public Integer        getStrikeCount() { return strikeCount; }
    public OffsetDateTime getLastViolationAt() { return lastViolationAt; }
    public OffsetDateTime getDeactivatedAt() { return deactivatedAt; }
    public OffsetDateTime getRevokedAt() { return revokedAt; }

    public void setId(UUID id)                        { this.id = id; }
    public void setUsername(String v)                 { this.username = v; }
    public void setEmail(String v)                  { this.email = v; }
    public void setRole(UserRole v)                  { this.role = v; }
    public void setStatus(AccountStatus v)   { this.status = v; }
    public void setDepartment(Department v)          { this.department = v; }
    public void setProfile(UserProfile v)            { this.profile = v; }
    public void setCreatedAt(OffsetDateTime v)       { this.createdAt = v; }
    public void setUpdatedAt(OffsetDateTime v)        { this.updatedAt = v; }
    public void setStrikeCount(Integer v)            { this.strikeCount = v; }
    public void setLastViolationAt(OffsetDateTime v) { this.lastViolationAt = v; }
    public void setDeactivatedAt(OffsetDateTime v) { this.deactivatedAt = v; }
    public void setRevokedAt(OffsetDateTime v) { this.revokedAt = v; }

    // Builder-style static factory method
    public static UserBuilder builder() { return new UserBuilder(); }

    public static class UserBuilder {
        private UUID id;
        private String username;
        private String email;
        private UserRole role;
        private AccountStatus status;
        private Department department;
        private UserProfile profile;
        private OffsetDateTime createdAt;
        private OffsetDateTime updatedAt;
        private Integer strikeCount;
        private OffsetDateTime lastViolationAt;
        private OffsetDateTime deactivatedAt;
        private OffsetDateTime revokedAt;

        public UserBuilder id(UUID id)               { this.id = id; return this; }
        public UserBuilder username(String v)          { this.username = v; return this; }
        public UserBuilder email(String v)            { this.email = v; return this; }
        public UserBuilder role(UserRole v)           { this.role = v; return this; }
        public UserBuilder status(AccountStatus v) { this.status = v; return this; }
        public UserBuilder department(Department v)   { this.department = v; return this; }
        public UserBuilder profile(UserProfile v)     { this.profile = v; return this; }
        public UserBuilder createdAt(OffsetDateTime v) { this.createdAt = v; return this; }
        public UserBuilder updatedAt(OffsetDateTime v) { this.updatedAt = v; return this; }
        public UserBuilder strikeCount(Integer v)    { this.strikeCount = v; return this; }
        public UserBuilder lastViolationAt(OffsetDateTime v) { this.lastViolationAt = v; return this; }
        public UserBuilder deactivatedAt(OffsetDateTime v) { this.deactivatedAt = v; return this; }
        public UserBuilder revokedAt(OffsetDateTime v) { this.revokedAt = v; return this; }

        public User build() {
            User u = new User();
            u.setId(id); u.setUsername(username); u.setEmail(email); u.setRole(role);
            u.setStatus(status); u.setDepartment(department); u.setProfile(profile);
            u.setCreatedAt(createdAt); u.setUpdatedAt(updatedAt);
            u.setStrikeCount(strikeCount); u.setLastViolationAt(lastViolationAt);
            u.setDeactivatedAt(deactivatedAt); u.setRevokedAt(revokedAt);
            return u;
        }
    }
}
