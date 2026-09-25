package com.poliwise.user.service;

import com.poliwise.user.dto.roster.RosterImportResponse;
import com.poliwise.user.entity.Department;
import com.poliwise.user.repository.DepartmentRepository;
import com.poliwise.user.repository.EmployeeRosterRepository;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyCollection;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class RosterExcelServiceTest {

    @Mock
    private DepartmentRepository departmentRepository;

    @Mock
    private EmployeeRosterRepository employeeRosterRepository;

    @InjectMocks
    private RosterExcelService rosterExcelService;

    private Department engineeringDept;

    @BeforeEach
    void setUp() {
        engineeringDept = new Department();
        engineeringDept.setId(UUID.randomUUID());
        engineeringDept.setCode("ENG");
        engineeringDept.setName("Kỹ thuật");
        engineeringDept.setIsActive(true);
    }

    @Test
    @DisplayName("generateTemplate: tạo file Excel có đủ 2 sheet (Danh sách nhân sự và Danh mục phòng ban)")
    void generateTemplate_shouldCreateTwoSheetsWithHeaders() throws IOException {
        when(departmentRepository.findByIsActiveTrueOrderByNameAsc()).thenReturn(List.of(engineeringDept));

        byte[] bytes = rosterExcelService.generateTemplate();
        assertThat(bytes).isNotNull();
        assertThat(bytes.length).isGreaterThan(0);

        try (Workbook workbook = new XSSFWorkbook(new ByteArrayInputStream(bytes))) {
            assertThat(workbook.getNumberOfSheets()).isEqualTo(2);
            assertThat(workbook.getSheetName(0)).isEqualTo("Danh sách nhân sự");
            assertThat(workbook.getSheetName(1)).isEqualTo("Danh mục phòng ban");

            Sheet dataSheet = workbook.getSheetAt(0);
            Row headerRow = dataSheet.getRow(0);
            assertThat(headerRow.getCell(0).getStringCellValue()).contains("Mã nhân viên");
            assertThat(headerRow.getCell(1).getStringCellValue()).contains("Email");
            assertThat(headerRow.getCell(2).getStringCellValue()).contains("Họ và tên");
            assertThat(headerRow.getCell(5).getStringCellValue()).contains("Mã phòng ban");

            Sheet deptSheet = workbook.getSheetAt(1);
            Row deptRow = deptSheet.getRow(1);
            assertThat(deptRow.getCell(0).getStringCellValue()).isEqualTo("ENG");
            assertThat(deptRow.getCell(1).getStringCellValue()).isEqualTo("Kỹ thuật");
        }
    }

    @Test
    @DisplayName("importRoster: import file 2 dòng hợp lệ thành công 100%")
    void importRoster_whenValidData_shouldImportAllRows() throws IOException {
        when(departmentRepository.findAll()).thenReturn(List.of(engineeringDept));
        when(employeeRosterRepository.findExistingEmailsIn(anyCollection())).thenReturn(Collections.emptyList());
        when(employeeRosterRepository.findExistingEmployeeCodesIn(anyCollection())).thenReturn(Collections.emptyList());
        when(employeeRosterRepository.saveAll(anyCollection())).thenAnswer(invocation -> invocation.getArgument(0));

        // Format: 0: empCode, 1: email, 2: fullName, 3: phone, 4: position, 5: deptCode, 6: role
        byte[] excelBytes = createExcelFile(List.of(
                new String[]{"EMP001", "nguyenvana@company.com", "Nguyễn Văn A", "0901234567", "Kỹ sư", "ENG", "USER"},
                new String[]{"EMP002", "tranthib@company.com", "Trần Thị B", "0907654321", "Tester", "ENG", "USER"}
        ));

        UUID adminId = UUID.randomUUID();
        RosterImportResponse response = rosterExcelService.importRoster(new ByteArrayInputStream(excelBytes), adminId);

        assertThat(response.totalRows()).isEqualTo(2);
        assertThat(response.importedCount()).isEqualTo(2);
        assertThat(response.failedCount()).isZero();
        assertThat(response.errors()).isEmpty();

        verify(employeeRosterRepository, times(1)).saveAll(anyCollection());
    }

    @Test
    @DisplayName("importRoster: phát hiện lỗi thiếu trường, sai email, trùng email và sai mã phòng ban")
    void importRoster_whenValidationErrors_shouldReportDetailedErrors() throws IOException {
        when(departmentRepository.findAll()).thenReturn(List.of(engineeringDept));
        when(employeeRosterRepository.findExistingEmailsIn(anyCollection())).thenReturn(Collections.emptyList());
        when(employeeRosterRepository.findExistingEmployeeCodesIn(anyCollection())).thenReturn(Collections.emptyList());

        // Format: 0: empCode, 1: email, 2: fullName, 3: phone, 4: position, 5: deptCode, 6: role
        byte[] excelBytes = createExcelFile(List.of(
                new String[]{"", "valid1@company.com", "Thiếu Mã NV", "", "Kỹ sư", "ENG", "USER"}, // Lỗi thiếu mã NV
                new String[]{"EMP002", "invalid-email-format", "Sai Email", "", "Kỹ sư", "ENG", "USER"}, // Lỗi định dạng email
                new String[]{"EMP003", "valid2@company.com", "Sai Dept", "", "Kỹ sư", "UNKNOWN_DEPT", "USER"}, // Lỗi không tồn tại mã phòng ban
                new String[]{"EMP004", "duplicate@company.com", "Trùng Email 1", "", "Kỹ sư", "ENG", "USER"},
                new String[]{"EMP005", "duplicate@company.com", "Trùng Email 2", "", "Kỹ sư", "ENG", "USER"} // Lỗi trùng email trong file
        ));

        UUID adminId = UUID.randomUUID();
        RosterImportResponse response = rosterExcelService.importRoster(new ByteArrayInputStream(excelBytes), adminId);

        assertThat(response.totalRows()).isEqualTo(5);
        assertThat(response.failedCount()).isGreaterThan(0);
        assertThat(response.errors()).isNotEmpty();

        assertThat(response.errors()).anyMatch(e -> e.reason().contains("Mã nhân viên không được để trống"));
        assertThat(response.errors()).anyMatch(e -> e.reason().contains("Định dạng email không hợp lệ"));
        assertThat(response.errors()).anyMatch(e -> e.reason().contains("không tồn tại"));
        assertThat(response.errors()).anyMatch(e -> e.reason().contains("bị trùng lặp"));
    }

    private byte[] createExcelFile(List<String[]> dataRows) throws IOException {
        try (Workbook workbook = new XSSFWorkbook(); ByteArrayOutputStream baos = new ByteArrayOutputStream()) {
            Sheet sheet = workbook.createSheet("Data");
            Row header = sheet.createRow(0);
            header.createCell(0).setCellValue("Mã nhân viên (*)");
            header.createCell(1).setCellValue("Email (*)");
            header.createCell(2).setCellValue("Họ và tên (*)");
            header.createCell(3).setCellValue("Số điện thoại");
            header.createCell(4).setCellValue("Chức vụ / Vị trí");
            header.createCell(5).setCellValue("Mã phòng ban (*)");
            header.createCell(6).setCellValue("Vai trò");

            int rowIdx = 1;
            for (String[] rowData : dataRows) {
                Row row = sheet.createRow(rowIdx++);
                for (int col = 0; col < rowData.length; col++) {
                    row.createCell(col).setCellValue(rowData[col]);
                }
            }

            workbook.write(baos);
            return baos.toByteArray();
        }
    }
}
