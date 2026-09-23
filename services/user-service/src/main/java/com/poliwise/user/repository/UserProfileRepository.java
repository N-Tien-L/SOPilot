package com.poliwise.user.repository;

import com.poliwise.user.entity.UserProfile;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface UserProfileRepository
                extends JpaRepository<UserProfile, UUID>, JpaSpecificationExecutor<UserProfile> {

        @EntityGraph(attributePaths = {"user", "user.department"})
        Optional<UserProfile> findByUser_Id(UUID userId);

        Optional<UserProfile> findByEmployeeCodeIgnoreCase(String employeeCode);

        boolean existsByEmployeeCodeIgnoreCase(String employeeCode);

        @Query("""
                        select up
                        from UserProfile up
                        where lower(up.fullName) like lower(concat('%', :keyword, '%'))
                        order by up.updatedAt desc
                        """)
        Page<UserProfile> searchByFullName(@Param("keyword") String keyword, Pageable pageable);
}
