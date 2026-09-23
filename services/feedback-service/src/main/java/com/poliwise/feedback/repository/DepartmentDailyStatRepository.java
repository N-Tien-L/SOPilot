package com.poliwise.feedback.repository;

import com.poliwise.feedback.entity.DepartmentDailyStat;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface DepartmentDailyStatRepository extends JpaRepository<DepartmentDailyStat, UUID> {

    Optional<DepartmentDailyStat> findByDateAndDepartmentId(LocalDate date, UUID departmentId);

    List<DepartmentDailyStat> findByDateBetweenOrderByDateDesc(LocalDate from, LocalDate to);

    List<DepartmentDailyStat> findByDepartmentIdOrderByDateDesc(UUID departmentId);
}
