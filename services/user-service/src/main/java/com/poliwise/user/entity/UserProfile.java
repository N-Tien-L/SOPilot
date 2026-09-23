package com.poliwise.user.entity;

import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import jakarta.persistence.OneToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;

import java.time.LocalDate;
import java.time.OffsetDateTime;
import java.util.UUID;

import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;
import lombok.AllArgsConstructor;
import lombok.Builder;

@Entity
@Table(name = "user_profiles", schema = "core")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class UserProfile {

    @Id
    @EqualsAndHashCode.Include
    @Column(columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @OneToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id", nullable = false,
            foreignKey = @ForeignKey(name = "fk_user_profiles_user"))
    @ToString.Exclude
    private User user;

    @Column(nullable = false, length = 255)
    private String fullName;

    @Column(length = 20)
    private String phone;

    @Column(length = 100)
    private String position;

    @Column(name = "avatar_url", length = 500)
    private String avatarUrl;

    @Column(columnDefinition = "text")
    private String bio;

    @Column(name = "date_of_birth", columnDefinition = "date")
    private LocalDate dateOfBirth;

    @Column(name = "employee_code", length = 50, nullable = false)
    private String employeeCode;

    @Column(name = "joined_date", columnDefinition = "date", nullable = false)
    private LocalDate joinedDate;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @PrePersist
    void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = OffsetDateTime.now();
    }

    // Lombok annotations provide @Getter and @Setter at class level.
    // If annotation processor fails, these explicit methods ensure compilation.

    public String getBio() { return bio; }
    public void setBio(String v) { this.bio = v; }

    public LocalDate getDateOfBirth() { return dateOfBirth; }
    public void setDateOfBirth(LocalDate v) { this.dateOfBirth = v; }

    public String getEmployeeCode() { return employeeCode; }
    public void setEmployeeCode(String v) { this.employeeCode = v; }

    public LocalDate getJoinedDate() { return joinedDate; }
    public void setJoinedDate(LocalDate v) { this.joinedDate = v; }

    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime v) { this.createdAt = v; }

    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime v) { this.updatedAt = v; }

    public String getFullName() { return fullName; }
    public void setFullName(String v) { this.fullName = v; }

    public String getPhone() { return phone; }
    public void setPhone(String v) { this.phone = v; }

    public String getPosition() { return position; }
    public void setPosition(String v) { this.position = v; }

    public String getAvatarUrl() { return avatarUrl; }
    public void setAvatarUrl(String v) { this.avatarUrl = v; }

    public UUID getId() { return id; }
    public void setId(UUID v) { this.id = v; }

    public User getUser() { return user; }
    public void setUser(User v) { this.user = v; }

    // Builder-style static factory method
    public static UserProfileBuilder builder() { return new UserProfileBuilder(); }

    public static class UserProfileBuilder {
        private UUID id;
        private User user;
        private String fullName;
        private String phone;
        private String position;
        private String avatarUrl;
        private String bio;
        private LocalDate dateOfBirth;
        private String employeeCode;
        private LocalDate joinedDate;
        private OffsetDateTime createdAt;
        private OffsetDateTime updatedAt;

        public UserProfileBuilder id(UUID v)               { this.id = v; return this; }
        public UserProfileBuilder user(User v)              { this.user = v; return this; }
        public UserProfileBuilder fullName(String v)        { this.fullName = v; return this; }
        public UserProfileBuilder phone(String v)           { this.phone = v; return this; }
        public UserProfileBuilder position(String v)        { this.position = v; return this; }
        public UserProfileBuilder avatarUrl(String v)        { this.avatarUrl = v; return this; }
        public UserProfileBuilder bio(String v)             { this.bio = v; return this; }
        public UserProfileBuilder dateOfBirth(LocalDate v)  { this.dateOfBirth = v; return this; }
        public UserProfileBuilder employeeCode(String v)    { this.employeeCode = v; return this; }
        public UserProfileBuilder joinedDate(LocalDate v)   { this.joinedDate = v; return this; }
        public UserProfileBuilder createdAt(OffsetDateTime v) { this.createdAt = v; return this; }
        public UserProfileBuilder updatedAt(OffsetDateTime v) { this.updatedAt = v; return this; }

        public UserProfile build() {
            UserProfile p = new UserProfile();
            p.setId(id); p.setUser(user); p.setFullName(fullName); p.setPhone(phone);
            p.setPosition(position); p.setAvatarUrl(avatarUrl); p.setBio(bio);
            p.setDateOfBirth(dateOfBirth); p.setEmployeeCode(employeeCode);
            p.setJoinedDate(joinedDate); p.setCreatedAt(createdAt); p.setUpdatedAt(updatedAt);
            return p;
        }
    }
}
