package com.poliwise.user.entity;

import jakarta.persistence.*;

import java.time.OffsetDateTime;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import java.time.OffsetDateTime;
import java.util.HashSet;
import java.util.Set;
import java.util.UUID;

import lombok.EqualsAndHashCode;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;
import lombok.AllArgsConstructor;

@Entity
@Table(name = "departments", schema = "core")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@EqualsAndHashCode(onlyExplicitlyIncluded = true)
public class Department {

    @Id
    @EqualsAndHashCode.Include
    @Column(columnDefinition = "uuid", nullable = false, updatable = false)
    private UUID id;

    @Column(nullable = false, length = 255)
    private String name;

    @Column(nullable = false, length = 50)
    private String code;

    @Column(columnDefinition = "text")
    private String description;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "parent_id", foreignKey = @ForeignKey(name = "fk_departments_parent"))
    @ToString.Exclude
    private Department parent;

    @OneToMany(mappedBy = "parent", fetch = FetchType.LAZY, cascade = CascadeType.ALL,
            orphanRemoval = true)
    @ToString.Exclude
    private Set<Department> subDepartments = new HashSet<>();

    @Column(name = "is_active", nullable = false, columnDefinition = "boolean default true")
    private Boolean isActive = true;

    @Column(name = "created_at", nullable = false, updatable = false)
    private OffsetDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private OffsetDateTime updatedAt;

    @PrePersist
    void onCreate() {
        OffsetDateTime now = OffsetDateTime.now();
        if (createdAt == null) createdAt = now;
        if (updatedAt == null) updatedAt = now;
        if (isActive == null) isActive = true;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = OffsetDateTime.now();
    }

    // Lombok annotations provide @Getter and @Setter at class level.
    // If annotation processor fails, these explicit methods ensure compilation.

    public UUID getId() { return id; }
    public void setId(UUID id) { this.id = id; }

    public String getName() { return name; }
    public void setName(String name) { this.name = name; }

    public String getCode() { return code; }
    public void setCode(String code) { this.code = code; }

    public String getDescription() { return description; }
    public void setDescription(String desc) { this.description = desc; }

    public Department getParent() { return parent; }
    public void setParent(Department parent) { this.parent = parent; }

    public Set<Department> getSubDepartments() { return subDepartments; }
    public void setSubDepartments(Set<Department> subs) { this.subDepartments = subs; }

    public Boolean getIsActive() { return isActive; }
    public void setIsActive(Boolean active) { this.isActive = active; }

    public OffsetDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(OffsetDateTime ts) { this.createdAt = ts; }

    public OffsetDateTime getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(OffsetDateTime ts) { this.updatedAt = ts; }

    // Builder-style static factory method
    public static DepartmentBuilder builder() { return new DepartmentBuilder(); }

    public static class DepartmentBuilder {
        private UUID id;
        private String name;
        private String code;
        private String description;
        private Department parent;
        private Set<Department> subDepartments = new HashSet<>();
        private Boolean isActive = true;
        private OffsetDateTime createdAt;
        private OffsetDateTime updatedAt;

        public DepartmentBuilder id(UUID id) { this.id = id; return this; }
        public DepartmentBuilder name(String name) { this.name = name; return this; }
        public DepartmentBuilder code(String code) { this.code = code; return this; }
        public DepartmentBuilder description(String description) { this.description = description; return this; }
        public DepartmentBuilder parent(Department parent) { this.parent = parent; return this; }
        public DepartmentBuilder subDepartments(Set<Department> subs) { this.subDepartments = subs; return this; }
        public DepartmentBuilder isActive(Boolean active) { this.isActive = active; return this; }
        public DepartmentBuilder createdAt(OffsetDateTime ts) { this.createdAt = ts; return this; }
        public DepartmentBuilder updatedAt(OffsetDateTime ts) { this.updatedAt = ts; return this; }

        public Department build() {
            Department d = new Department();
            d.setId(id); d.setName(name); d.setCode(code); d.setDescription(description);
            d.setParent(parent); d.setSubDepartments(subDepartments); d.setIsActive(isActive);
            d.setCreatedAt(createdAt); d.setUpdatedAt(updatedAt);
            return d;
        }
    }
}
