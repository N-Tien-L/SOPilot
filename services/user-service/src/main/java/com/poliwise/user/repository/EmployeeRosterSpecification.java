package com.poliwise.user.repository;

import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.enums.RosterStatus;
import jakarta.persistence.criteria.Predicate;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.util.StringUtils;

import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

public class EmployeeRosterSpecification {

    private EmployeeRosterSpecification() {}

    public static Specification<EmployeeRoster> withFilters(
            String keyword,
            UUID departmentId,
            RosterStatus status,
            Boolean isClaimed,
            boolean excludeDeleted) {

        return (root, query, cb) -> {
            List<Predicate> predicates = new ArrayList<>();

            if (excludeDeleted) {
                predicates.add(cb.isNull(root.get("deletedAt")));
            }

            if (StringUtils.hasText(keyword)) {
                String pattern = "%" + keyword.toLowerCase().trim() + "%";
                Predicate byCode = cb.like(cb.lower(root.get("employeeCode")), pattern);
                Predicate byEmail = cb.like(cb.lower(root.get("email")), pattern);
                Predicate byFullName = cb.like(cb.lower(root.get("fullName")), pattern);
                predicates.add(cb.or(byCode, byEmail, byFullName));
            }

            if (departmentId != null) {
                predicates.add(cb.equal(root.get("department").get("id"), departmentId));
            }

            if (status != null) {
                predicates.add(cb.equal(root.get("status"), status));
            }

            if (isClaimed != null) {
                predicates.add(cb.equal(root.get("isClaimed"), isClaimed));
            }

            return cb.and(predicates.toArray(new Predicate[0]));
        };
    }
}
