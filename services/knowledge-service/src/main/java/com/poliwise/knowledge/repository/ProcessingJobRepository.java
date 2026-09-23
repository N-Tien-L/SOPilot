package com.poliwise.knowledge.repository;

import com.poliwise.knowledge.entity.ProcessingJob;
import com.poliwise.knowledge.enums.ProcessingStatus;
import com.poliwise.knowledge.enums.ProcessingStep;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.stereotype.Repository;

@Repository
public interface ProcessingJobRepository extends JpaRepository<ProcessingJob, UUID>,
                JpaSpecificationExecutor<ProcessingJob> {

        List<ProcessingJob> findByDocumentIdOrderByCreatedAtDesc(UUID documentId);

        Optional<ProcessingJob> findFirstByDocumentIdAndJobTypeOrderByCreatedAtDesc(UUID documentId,
                        ProcessingStep jobType);

        Page<ProcessingJob> findByStatusOrderByCreatedAtAsc(ProcessingStatus status,
                        Pageable pageable);

        long countByStatusAndSuccess(ProcessingStatus status, Boolean success);
}
