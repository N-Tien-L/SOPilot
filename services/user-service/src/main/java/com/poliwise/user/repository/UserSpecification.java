package com.poliwise.user.repository;

import com.poliwise.user.entity.User;
import com.poliwise.user.enums.AccountStatus;
import com.poliwise.user.enums.UserRole;
import jakarta.persistence.criteria.Join;
import jakarta.persistence.criteria.JoinType;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class UserSpecification {

    private UserSpecification() {}

    public static Specification<User> withFilters(
            String keyword,
            UserRole role,
            AccountStatus status,
            UUID departmentId,
            Boolean excludeDeleted) {

        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (excludeDeleted != null && excludeDeleted) {
                predicates.add(cb.notEqual(root.get("status"), AccountStatus.REVOKED));
            }

            if (StringUtils.hasText(keyword)) {
                String pattern = "%" + keyword.toLowerCase() + "%";
                Predicate byUsername = cb.like(cb.lower(root.get("username")), pattern);
                Predicate byEmail = cb.like(cb.lower(root.get("email")), pattern);

                // Explicitly join profile with LEFT join to safely access fullName
                Join<Object, Object> profileJoin = root.join("profile", JoinType.LEFT);
                Predicate byFullName = cb.and(
                        cb.isNotNull(profileJoin.get("fullName")),
                        cb.like(cb.lower(profileJoin.get("fullName")), pattern));

                predicates.add(cb.or(byUsername, byEmail, byFullName));
            }

            if (role != null) {
                predicates.add(cb.equal(root.get("role"), role));
            }

            if (status != null) {
                predicates.add(cb.equal(root.get("status"), status));
            }

            if (departmentId != null) {
                predicates.add(cb.equal(root.get("department").get("id"), departmentId));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }

    public static Specification<User> deletedOnly() {
        return (root, query, cb) -> cb.equal(root.get("status"), AccountStatus.REVOKED);
    }

    public static Specification<User> activeOnly() {
        return (root, query, cb) -> cb.equal(root.get("status"), AccountStatus.ACTIVE);
    }
}
