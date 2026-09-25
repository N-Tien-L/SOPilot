package com.poliwise.user.repository;

import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.enums.RosterStatus;
import jakarta.persistence.LockModeType;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface EmployeeRosterRepository extends JpaRepository<EmployeeRoster, UUID>, JpaSpecificationExecutor<EmployeeRoster> {

    @EntityGraph(attributePaths = {"department", "claimedUser"})
    Optional<EmployeeRoster> findByEmailIgnoreCaseAndDeletedAtIsNull(String email);

    @EntityGraph(attributePaths = {"department", "claimedUser"})
    Optional<EmployeeRoster> findByEmployeeCodeAndDeletedAtIsNull(String employeeCode);

    boolean existsByEmailIgnoreCaseAndDeletedAtIsNull(String email);

    boolean existsByEmployeeCodeAndDeletedAtIsNull(String employeeCode);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @EntityGraph(attributePaths = {"department", "claimedUser"})
    @Query("SELECT r FROM EmployeeRoster r WHERE LOWER(r.email) = LOWER(:email) AND r.deletedAt IS NULL")
    Optional<EmployeeRoster> findByEmailIgnoreCaseForUpdate(@Param("email") String email);

    @Query("SELECT LOWER(r.email) FROM EmployeeRoster r WHERE LOWER(r.email) IN :emails AND r.deletedAt IS NULL")
    List<String> findExistingEmailsIn(@Param("emails") Collection<String> emails);

    @Query("SELECT r.employeeCode FROM EmployeeRoster r WHERE r.employeeCode IN :codes AND r.deletedAt IS NULL")
    List<String> findExistingEmployeeCodesIn(@Param("codes") Collection<String> codes);

    Page<EmployeeRoster> findByDepartmentIdAndStatusAndDeletedAtIsNull(UUID departmentId, RosterStatus status, Pageable pageable);

    long countByStatusAndDeletedAtIsNull(RosterStatus status);

    long countByIsClaimedTrue();
}
