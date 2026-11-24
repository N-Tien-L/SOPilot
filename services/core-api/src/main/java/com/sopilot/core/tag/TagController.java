package com.sopilot.core.tag;

import com.sopilot.core.common.ApiResponse;
import com.sopilot.core.security.AuthPrincipal;
import com.sopilot.core.tag.TagRepository.Tag;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.OffsetDateTime;
import java.util.List;
import java.util.UUID;

/** Tags of the caller's workspace (TECH §5.6). Workspace comes from the access token only. */
@RestController
@RequestMapping("/api/v1/tags")
public class TagController {

    private final TagService service;

    public TagController(TagService service) {
        this.service = service;
    }

    @GetMapping
    public ApiResponse<List<TagView>> list(AuthPrincipal principal) {
        return ApiResponse.of(service.list(principal).stream().map(TagView::of).toList());
    }

    public record TagView(UUID id, String name, OffsetDateTime createdAt) {
        static TagView of(Tag t) {
            return new TagView(t.id(), t.name(), t.createdAt());
        }
    }
}
