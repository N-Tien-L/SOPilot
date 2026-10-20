package com.poliwise.user.controller;

import com.fasterxml.jackson.annotation.JsonIgnore;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.SerializationFeature;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.poliwise.user.dto.roster.RosterImportResponse;
import com.poliwise.user.dto.roster.RosterResponse;
import com.poliwise.user.entity.Department;
import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.service.EmployeeRosterService;
import com.poliwise.user.service.RosterExcelService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.web.PageableHandlerMethodArgumentResolver;
import org.springframework.http.MediaType;
import org.springframework.http.converter.ByteArrayHttpMessageConverter;
import org.springframework.http.converter.json.MappingJackson2HttpMessageConverter;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.io.InputStream;
import java.time.OffsetDateTime;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@ExtendWith(MockitoExtension.class)
class EmployeeRosterControllerTest {

    @Mock
    private EmployeeRosterService employeeRosterService;

    @Mock
    private RosterExcelService rosterExcelService;

    @InjectMocks
    private EmployeeRosterController employeeRosterController;

    private MockMvc mockMvc;

    private abstract static class PageMixIn {
        @JsonIgnore
        abstract Object getPageable();
    }

    @BeforeEach
    void setUp() {
        ObjectMapper objectMapper = new ObjectMapper();
        objectMapper.registerModule(new JavaTimeModule());
        objectMapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        objectMapper.addMixIn(PageImpl.class, PageMixIn.class);

        mockMvc = MockMvcBuilders.standaloneSetup(employeeRosterController)
                .setCustomArgumentResolvers(new PageableHandlerMethodArgumentResolver())
                .setMessageConverters(
                        new ByteArrayHttpMessageConverter(),
                        new MappingJackson2HttpMessageConverter(objectMapper)
                )
                .build();
    }

    private EmployeeRoster createSampleRoster(UUID id) {
        Department dept = new Department();
        dept.setId(UUID.randomUUID());
        dept.setCode("ENG");
        dept.setName("Kỹ thuật");

        EmployeeRoster r = new EmployeeRoster();
        r.setId(id);
        r.setEmployeeCode("EMP001");
        r.setFullName("Nguyễn Văn A");
        r.setEmail("employee@company.com");
        r.setDepartment(dept);
        r.setPosition("Kỹ sư");
        r.setPhone("0901234567");
        r.setStatus(RosterStatus.PENDING);
        r.setRole(UserRole.USER);
        r.setClaimed(false);
        r.setCreatedAt(OffsetDateTime.now());
        r.setUpdatedAt(OffsetDateTime.now());
        return r;
    }

    @Test
    @DisplayName("GET /api/v1/users/roster/template: Tải file template Excel thành công")
    void downloadTemplate_shouldReturnExcelFile() throws Exception {
        byte[] dummyBytes = new byte[]{0x50, 0x4B, 0x03, 0x04}; // ZIP magic number for XLSX
        when(rosterExcelService.generateTemplate()).thenReturn(dummyBytes);

        mockMvc.perform(get("/api/v1/users/roster/template"))
                .andExpect(status().isOk())
                .andExpect(header().string("Content-Disposition", "attachment; filename=\"employee_roster_template.xlsx\""))
                .andExpect(content().contentType("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))
                .andExpect(content().bytes(dummyBytes));
    }

    @Test
    @DisplayName("POST /api/v1/users/roster/import: Upload file Excel thành công")
    void importRoster_shouldReturnImportResponse() throws Exception {
        MockMultipartFile file = new MockMultipartFile(
                "file", "roster.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                new byte[]{1, 2, 3}
        );

        RosterImportResponse mockResponse = RosterImportResponse.of(UUID.randomUUID(), 10, 10, 0, Collections.emptyList());
        when(rosterExcelService.importRoster(any(InputStream.class), any())).thenReturn(mockResponse);

        mockMvc.perform(multipart("/api/v1/users/roster/import").file(file))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.totalRows").value(10))
                .andExpect(jsonPath("$.importedCount").value(10))
                .andExpect(jsonPath("$.failedCount").value(0));
    }

    @Test
    @DisplayName("GET /api/v1/users/roster: Tìm kiếm danh bạ trả về danh sách phân trang")
    void searchRoster_shouldReturnPagedResults() throws Exception {
        UUID id = UUID.randomUUID();
        RosterResponse item = RosterResponse.fromEntity(createSampleRoster(id));
        PageImpl<RosterResponse> page = new PageImpl<>(List.of(item), PageRequest.of(0, 10), 1);

        when(employeeRosterService.searchRoster(any(), any(), any(), any(), any(Pageable.class)))
                .thenReturn(page);

        mockMvc.perform(get("/api/v1/users/roster")
                        .param("keyword", "EMP001")
                        .contentType(MediaType.APPLICATION_JSON))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.content[0].employeeCode").value("EMP001"))
                .andExpect(jsonPath("$.content[0].email").value("employee@company.com"));
    }

    @Test
    @DisplayName("GET /api/v1/users/roster/{id}: Lấy chi tiết danh bạ theo ID")
    void getById_shouldReturnRosterResponse() throws Exception {
        UUID id = UUID.randomUUID();
        RosterResponse item = RosterResponse.fromEntity(createSampleRoster(id));

        when(employeeRosterService.getById(id)).thenReturn(item);

        mockMvc.perform(get("/api/v1/users/roster/{id}", id))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.id").value(id.toString()))
                .andExpect(jsonPath("$.fullName").value("Nguyễn Văn A"));
    }

    @Test
    @DisplayName("DELETE /api/v1/users/roster/{id}: Vô hiệu hóa thành công trả về 204 No Content")
    void deactivate_shouldReturnNoContent() throws Exception {
        UUID id = UUID.randomUUID();

        mockMvc.perform(delete("/api/v1/users/roster/{id}", id))
                .andExpect(status().isNoContent());

        verify(employeeRosterService).deactivateRoster(eq(id), any());
    }
}
