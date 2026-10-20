package com.poliwise.user.service;

import com.poliwise.user.dto.roster.RosterImportResponse;
import com.poliwise.user.dto.roster.RosterRowError;
import com.poliwise.user.entity.Department;
import com.poliwise.user.entity.EmployeeRoster;
import com.poliwise.user.enums.RosterStatus;
import com.poliwise.user.enums.UserRole;
import com.poliwise.user.repository.DepartmentRepository;
import com.poliwise.user.repository.EmployeeRosterRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.poi.ss.usermodel.BorderStyle;
import org.apache.poi.ss.usermodel.Cell;
import org.apache.poi.ss.usermodel.CellStyle;
import org.apache.poi.ss.usermodel.CellType;
import org.apache.poi.ss.usermodel.FillPatternType;
import org.apache.poi.ss.usermodel.Font;
import org.apache.poi.ss.usermodel.HorizontalAlignment;
import org.apache.poi.ss.usermodel.IndexedColors;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.ss.usermodel.Workbook;
import org.apache.poi.ss.usermodel.WorkbookFactory;
import org.apache.poi.xssf.streaming.SXSSFWorkbook;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.time.OffsetDateTime;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Slf4j
public class RosterExcelService {

    private final DepartmentRepository departmentRepository;
    private final EmployeeRosterRepository employeeRosterRepository;

    private static final Pattern EMAIL_PATTERN = Pattern.compile("^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$");

    private static final String[] ROSTER_HEADERS = {
            "Mã nhân viên (*)",
            "Email công ty (*)",
            "Họ và tên (*)",
            "Số điện thoại",
            "Vị trí / Chức danh",
            "Mã phòng ban (*)",
            "Vai trò (USER / MANAGER / ADMIN)"
    };

    private static final String[] DEPT_HEADERS = {
            "Mã phòng ban (Department Code)",
            "Tên phòng ban (Department Name)",
            "Mô tả"
    };

    /**
     * Tạo file Excel template 2 sheets:
     * - Sheet 1: Danh sách nhân sự (Form nhập liệu với 1 dòng mẫu)
     * - Sheet 2: Danh mục phòng ban (Tra cứu mã phòng ban hợp lệ)
     */
    public byte[] generateTemplate() {
        try (SXSSFWorkbook workbook = new SXSSFWorkbook(100)) {
            // Style Header
            Font headerFont = workbook.createFont();
            headerFont.setBold(true);
            headerFont.setColor(IndexedColors.WHITE.getIndex());

            CellStyle headerStyle = workbook.createCellStyle();
            headerStyle.setFont(headerFont);
            headerStyle.setFillForegroundColor(IndexedColors.ROYAL_BLUE.getIndex());
            headerStyle.setFillPattern(FillPatternType.SOLID_FOREGROUND);
            headerStyle.setAlignment(HorizontalAlignment.CENTER);
            headerStyle.setBorderBottom(BorderStyle.THIN);
            headerStyle.setBorderTop(BorderStyle.THIN);
            headerStyle.setBorderLeft(BorderStyle.THIN);
            headerStyle.setBorderRight(BorderStyle.THIN);

            // Sheet 1: Danh sách nhân viên
            Sheet rosterSheet = workbook.createSheet("Danh sách nhân sự");
            rosterSheet.createFreezePane(0, 1);

            Row headerRow = rosterSheet.createRow(0);
            for (int i = 0; i < ROSTER_HEADERS.length; i++) {
                Cell cell = headerRow.createCell(i);
                cell.setCellValue(ROSTER_HEADERS[i]);
                cell.setCellStyle(headerStyle);
            }

            // Dòng dữ liệu mẫu
            Row sampleRow = rosterSheet.createRow(1);
            sampleRow.createCell(0).setCellValue("EMP001");
            sampleRow.createCell(1).setCellValue("nguyen.van.a@sopilot.com");
            sampleRow.createCell(2).setCellValue("Nguyễn Văn A");
            sampleRow.createCell(3).setCellValue("0901234567");
            sampleRow.createCell(4).setCellValue("Kỹ sư phần mềm");
            sampleRow.createCell(5).setCellValue("ADMIN");
            sampleRow.createCell(6).setCellValue("USER");

            // Sheet 2: Danh mục phòng ban
            Sheet deptSheet = workbook.createSheet("Danh mục phòng ban");
            deptSheet.createFreezePane(0, 1);

            Row deptHeaderRow = deptSheet.createRow(0);
            for (int i = 0; i < DEPT_HEADERS.length; i++) {
                Cell cell = deptHeaderRow.createCell(i);
                cell.setCellValue(DEPT_HEADERS[i]);
                cell.setCellStyle(headerStyle);
            }

            List<Department> departments = departmentRepository.findByIsActiveTrueOrderByNameAsc();
            int deptRowNum = 1;
            for (Department dept : departments) {
                Row row = deptSheet.createRow(deptRowNum++);
                row.createCell(0).setCellValue(dept.getCode());
                row.createCell(1).setCellValue(dept.getName());
                row.createCell(2).setCellValue(dept.getDescription() != null ? dept.getDescription() : "");
            }

            ByteArrayOutputStream out = new ByteArrayOutputStream();
            workbook.write(out);
            workbook.dispose();
            return out.toByteArray();
        } catch (IOException e) {
            log.error("Failed to generate roster excel template", e);
            throw new RuntimeException("Failed to generate excel template: " + e.getMessage(), e);
        }
    }

    /**
     * Import danh bạ nhân sự từ file Excel (.xlsx / .xls).
     * Áp dụng In-Memory Preload + Validation + Batch Insert an toàn bộ nhớ.
     */
    @Transactional
    public RosterImportResponse importRoster(InputStream inputStream, UUID adminUserId) {
        UUID batchId = UUID.randomUUID();
        List<RosterRowError> errors = new ArrayList<>();
        List<EmployeeRoster> validEntities = new ArrayList<>();

        // 1. Preload toàn bộ Department vào Map (Key: CODE viết hoa) để tra cứu O(1)
        Map<String, Department> deptMap = departmentRepository.findAll().stream()
                .filter(Department::getIsActive)
                .collect(Collectors.toMap(
                        d -> d.getCode().toUpperCase().trim(),
                        d -> d,
                        (existing, replacement) -> existing
                ));

        Set<String> seenEmailsInFile = new HashSet<>();
        Set<String> seenCodesInFile = new HashSet<>();

        int totalDataRows = 0;

        try (Workbook workbook = WorkbookFactory.create(inputStream)) {
            Sheet sheet = workbook.getSheetAt(0);
            if (sheet == null) {
                throw new IllegalArgumentException("File Excel không chứa bất kỳ sheet nào");
            }

            int lastRowNum = sheet.getLastRowNum();
            OffsetDateTime now = OffsetDateTime.now();

            // Đọc từ dòng 1 (bỏ qua header dòng 0)
            for (int rowIndex = 1; rowIndex <= lastRowNum; rowIndex++) {
                Row row = sheet.getRow(rowIndex);
                if (row == null || isRowEmpty(row)) {
                    continue;
                }

                totalDataRows++;
                int displayRow = rowIndex + 1;

                String empCode = getCellString(row.getCell(0));
                String email = getCellString(row.getCell(1));
                String fullName = getCellString(row.getCell(2));
                String phone = getCellString(row.getCell(3));
                String position = getCellString(row.getCell(4));
                String deptCode = getCellString(row.getCell(5));
                String roleStr = getCellString(row.getCell(6));

                // Validate 1: Các trường bắt buộc
                if (!StringUtils.hasText(empCode)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Mã nhân viên không được để trống"));
                    continue;
                }
                if (!StringUtils.hasText(email)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Email không được để trống"));
                    continue;
                }
                if (!StringUtils.hasText(fullName)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Họ và tên không được để trống"));
                    continue;
                }
                if (!StringUtils.hasText(deptCode)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Mã phòng ban không được để trống"));
                    continue;
                }

                // Chuẩn hóa
                empCode = empCode.trim();
                email = email.trim().toLowerCase();
                fullName = fullName.trim();
                deptCode = deptCode.trim().toUpperCase();

                // Validate 2: Định dạng email
                if (!EMAIL_PATTERN.matcher(email).matches()) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Định dạng email không hợp lệ: " + email));
                    continue;
                }

                // Validate 3: Giới hạn độ dài
                if (empCode.length() > 50) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Mã nhân viên vượt quá 50 ký tự"));
                    continue;
                }
                if (email.length() > 255) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Email vượt quá 255 ký tự"));
                    continue;
                }
                if (fullName.length() > 255) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Họ và tên vượt quá 255 ký tự"));
                    continue;
                }

                // Validate 4: Trùng lặp trong chính file Excel
                if (!seenEmailsInFile.add(email)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Email bị trùng lặp trong file: " + email));
                    continue;
                }
                if (!seenCodesInFile.add(empCode)) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Mã nhân viên bị trùng lặp trong file: " + empCode));
                    continue;
                }

                // Validate 5: Phòng ban tồn tại
                Department department = deptMap.get(deptCode);
                if (department == null) {
                    errors.add(new RosterRowError(displayRow, empCode, email, "Mã phòng ban không tồn tại hoặc đã bị vô hiệu hóa: " + deptCode));
                    continue;
                }

                // Validate 6: Phân quyền UserRole
                UserRole role = UserRole.USER;
                if (StringUtils.hasText(roleStr)) {
                    try {
                        role = UserRole.valueOf(roleStr.trim().toUpperCase());
                    } catch (IllegalArgumentException e) {
                        errors.add(new RosterRowError(displayRow, empCode, email, "Vai trò không hợp lệ: '" + roleStr + "'. Chỉ chấp nhận USER, MANAGER, ADMIN"));
                        continue;
                    }
                }

                // Tạo Entity EmployeeRoster
                EmployeeRoster roster = EmployeeRoster.builder()
                        .id(UUID.randomUUID())
                        .employeeCode(empCode)
                        .email(email)
                        .fullName(fullName)
                        .phone(StringUtils.hasText(phone) ? phone.trim() : null)
                        .position(StringUtils.hasText(position) ? position.trim() : null)
                        .department(department)
                        .role(role)
                        .status(RosterStatus.PENDING)
                        .isClaimed(false)
                        .importBatchId(batchId)
                        .createdBy(adminUserId)
                        .updatedBy(adminUserId)
                        .createdAt(now)
                        .updatedAt(now)
                        .build();

                validEntities.add(roster);
            }
        } catch (Exception e) {
            log.error("Failed to parse roster excel file", e);
            throw new IllegalArgumentException("Không thể đọc file Excel: " + e.getMessage(), e);
        }

        // Validate 7: Kiểm tra trùng lặp với Database (Batch Lookup)
        if (!validEntities.isEmpty()) {
            Set<String> emailSet = validEntities.stream().map(EmployeeRoster::getEmail).collect(Collectors.toSet());
            Set<String> codeSet = validEntities.stream().map(EmployeeRoster::getEmployeeCode).collect(Collectors.toSet());

            Set<String> existingEmails = new HashSet<>(employeeRosterRepository.findExistingEmailsIn(emailSet));
            Set<String> existingCodes = new HashSet<>(employeeRosterRepository.findExistingEmployeeCodesIn(codeSet));

            List<EmployeeRoster> finalValidEntities = new ArrayList<>();
            for (EmployeeRoster entity : validEntities) {
                boolean hasDbConflict = false;
                if (existingEmails.contains(entity.getEmail())) {
                    errors.add(new RosterRowError(0, entity.getEmployeeCode(), entity.getEmail(), "Email đã tồn tại trong danh bạ hệ thống: " + entity.getEmail()));
                    hasDbConflict = true;
                }
                if (existingCodes.contains(entity.getEmployeeCode())) {
                    errors.add(new RosterRowError(0, entity.getEmployeeCode(), entity.getEmail(), "Mã nhân viên đã tồn tại trong danh bạ hệ thống: " + entity.getEmployeeCode()));
                    hasDbConflict = true;
                }
                if (!hasDbConflict) {
                    finalValidEntities.add(entity);
                }
            }

            // Lưu toàn bộ danh sách hợp lệ theo Batch
            if (!finalValidEntities.isEmpty()) {
                employeeRosterRepository.saveAll(finalValidEntities);
                log.info("Batch imported {} valid employee roster entries with batchId={}", finalValidEntities.size(), batchId);
            }

            return RosterImportResponse.of(batchId, totalDataRows, finalValidEntities.size(), errors.size(), errors);
        }

        return RosterImportResponse.of(batchId, totalDataRows, 0, errors.size(), errors);
    }

    private String getCellString(Cell cell) {
        if (cell == null) {
            return null;
        }
        if (cell.getCellType() == CellType.STRING) {
            return cell.getStringCellValue();
        } else if (cell.getCellType() == CellType.NUMERIC) {
            long longVal = (long) cell.getNumericCellValue();
            if (cell.getNumericCellValue() == longVal) {
                return String.valueOf(longVal);
            }
            return String.valueOf(cell.getNumericCellValue());
        } else if (cell.getCellType() == CellType.BOOLEAN) {
            return String.valueOf(cell.getBooleanCellValue());
        }
        return cell.toString();
    }

    private boolean isRowEmpty(Row row) {
        if (row == null) return true;
        for (int c = row.getFirstCellNum(); c < row.getLastCellNum(); c++) {
            Cell cell = row.getCell(c);
            if (cell != null && cell.getCellType() != CellType.BLANK && StringUtils.hasText(cell.toString())) {
                return false;
            }
        }
        return true;
    }
}
