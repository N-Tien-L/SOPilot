package com.poliwise.user.repository;

import com.poliwise.user.entity.Department;
import jakarta.persistence.LockModeType;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

@Repository
public interface DepartmentRepository
        extends JpaRepository<Department, UUID>, JpaSpecificationExecutor<Department> {

    Optional<Department> findByCodeIgnoreCase(String code);

    boolean existsByCodeIgnoreCase(String code);

    List<Department> findByParent_IdAndIsActiveTrue(UUID parentId);

    List<Department> findByParentIsNullAndIsActiveTrueOrderByNameAsc();

    List<Department> findByIsActiveTrueOrderByNameAsc();

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select d from Department d where d.id = :id")
    Optional<Department> findByIdForUpdate(@Param("id") UUID id);

    @Query("select d from Department d left join fetch d.subDepartments where d.parent is null and d.isActive = true order by d.name")
    List<Department> findRootDepartmentsWithChildren();
}
