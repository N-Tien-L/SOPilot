package com.poliwise.auth.repository;

import com.poliwise.auth.entity.User;
import com.poliwise.auth.enums.AccountStatus;
import jakarta.persistence.LockModeType;
import java.time.OffsetDateTime;
import java.util.Collection;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.annotation.Transactional;

@Repository
public interface UserRepository extends JpaRepository<User, UUID>, JpaSpecificationExecutor<User> {

        Optional<User> findByUsernameIgnoreCase(String username);

        Optional<User> findByEmailIgnoreCase(String email);

        Optional<User> findByUsernameIgnoreCaseOrEmailIgnoreCase(String username, String email);

        boolean existsByUsernameIgnoreCase(String username);

        boolean existsByEmailIgnoreCase(String email);

        @Query("""
                        select u
                        from User u
                        where (lower(u.username) = lower(:identifier)
                               or lower(u.email) = lower(:identifier))
                          and u.status in :statuses
                        """)
        Optional<User> findByIdentifierAndStatusIn(@Param("identifier") String identifier,
                        @Param("statuses") Collection<AccountStatus> statuses);

        @Lock(LockModeType.PESSIMISTIC_WRITE)
        @Query("select u from User u where u.id = :id")
        Optional<User> findByIdForUpdate(@Param("id") UUID id);

        @Lock(LockModeType.PESSIMISTIC_WRITE)
        @Query("select u from User u where lower(u.username) = lower(:username)")
        Optional<User> findByUsernameForUpdate(@Param("username") String username);

        @Transactional
        @Modifying(clearAutomatically = true, flushAutomatically = true)
        @Query("""
                        update User u
                        set u.failedLoginAttempts = coalesce(u.failedLoginAttempts, 0) + 1,
                            u.updatedAt = :updatedAt
                        where u.id = :userId
                        """)
        int incrementFailedLoginAttempts(@Param("userId") UUID userId,
                        @Param("updatedAt") OffsetDateTime updatedAt);

        @Transactional
        @Modifying(clearAutomatically = true, flushAutomatically = true)
        @Query("""
                        update User u
                        set u.failedLoginAttempts = 0,
                            u.lockedUntil = null,
                            u.updatedAt = :updatedAt
                        where u.id = :userId
                        """)
        int resetLoginLockState(@Param("userId") UUID userId,
                        @Param("updatedAt") OffsetDateTime updatedAt);

        @Query("""
                        select u from User u
                        where (:search is null or :search = ''
                           or lower(u.username) like lower(concat('%', :search, '%'))
                           or lower(u.email) like lower(concat('%', :search, '%')))
                          and (:role is null or :role = '' or cast(u.role as String) = :role)
                          and (:status is null or :status = '' or cast(u.status as String) = :status)
                          and (:departmentId is null or u.departmentId = :departmentId)
                        order by u.createdAt desc
                        """)
        org.springframework.data.domain.Page<User> searchUsers(
                        @Param("search") String search,
                        @Param("role") String role,
                        @Param("status") String status,
                        @Param("departmentId") UUID departmentId,
                        org.springframework.data.domain.Pageable pageable);
}
