package com.poliwise.user.repository;

import com.poliwise.user.entity.User;
import com.poliwise.user.enums.AccountStatus;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, UUID>, JpaSpecificationExecutor<User> {

    Optional<User> findByUsernameIgnoreCase(String username);

    Optional<User> findByEmailIgnoreCase(String email);

    Optional<User> findByUsernameIgnoreCaseOrEmailIgnoreCase(String username, String email);

    boolean existsByUsernameIgnoreCase(String username);

    boolean existsByEmailIgnoreCase(String email);

    List<User> findByDepartment_Id(UUID departmentId);

    @EntityGraph(attributePaths = {"profile", "department"})
    @Query("select u from User u where u.id = :id")
    Optional<User> findDetailedById(@Param("id") UUID id);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select u from User u where u.id = :id")
    Optional<User> findByIdForUpdate(@Param("id") UUID id);

    org.springframework.data.domain.Page<User> findByDepartmentId(
            @Param("departmentId") UUID departmentId,
            org.springframework.data.domain.Pageable pageable);

    @Query("select count(u) from User u where u.department.id = :departmentId")
    long countByDepartmentId(@Param("departmentId") UUID departmentId);

    long countByStatus(AccountStatus status);
}
