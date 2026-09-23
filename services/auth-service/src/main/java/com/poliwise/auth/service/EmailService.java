package com.poliwise.auth.service;

import com.poliwise.auth.config.EmailProperties;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.mail.javamail.MimeMessageHelper;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.concurrent.CompletableFuture;

@Service
public class EmailService {

    private static final Logger log = LoggerFactory.getLogger(EmailService.class);

    private final JavaMailSender mailSender;
    private final EmailProperties emailProperties;

    public EmailService(JavaMailSender mailSender, EmailProperties emailProperties) {
        this.mailSender = mailSender;
        this.emailProperties = emailProperties;
    }

    public CompletableFuture<Boolean> sendAccountCredentials(String toEmail, String username, String password) {
        log.info("[EMAIL] sendAccountCredentials called - to: {}, username: {}", maskEmail(toEmail), username);
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send credentials to {} for user {}", maskEmail(toEmail), username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Tài khoản Poliwise của bạn đã được tạo",
                buildCredentialsEmail(username, password));
    }

    public CompletableFuture<Boolean> sendPasswordResetLink(String toEmail, String username, String resetLink, Duration ttl) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send password reset link to {} for user {}", maskEmail(toEmail), username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Poliwise password reset",
                buildPasswordResetLinkEmail(username, resetLink, ttl));
    }

    public CompletableFuture<Boolean> sendOtpEmail(String toEmail, String username, String otpCode) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send OTP to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Mã xác thực Poliwise",
                buildOtpEmail(username, otpCode));
    }

    public CompletableFuture<Boolean> sendBulkAccountCredentials(
            String toEmail,
            String username,
            String password,
            String adminName
    ) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send bulk credentials to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Tài khoản Poliwise - Thông tin đăng nhập",
                buildBulkCredentialsEmail(username, password, adminName));
    }

    /**
     * Gửi email thông báo khi tài khoản bị vô hiệu hóa (DEACTIVATED).
     */
    public CompletableFuture<Boolean> sendAccountDeactivatedEmail(String toEmail, String username, String adminName) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send deactivated email to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Thông báo: Tài khoản Poliwise của bạn đã bị tạm ngưng",
                buildAccountDeactivatedEmail(username, adminName));
    }

    /**
     * Gửi email thông báo khi tài khoản được kích hoạt lại (ACTIVE).
     */
    public CompletableFuture<Boolean> sendAccountReactivatedEmail(String toEmail, String username, String adminName) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send reactivated email to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Thông báo: Tài khoản Poliwise của bạn đã được kích hoạt lại",
                buildAccountReactivatedEmail(username, adminName));
    }

    /**
     * Gửi email thông báo khi tài khoản bị thu hồi (REVOKED).
     */
    public CompletableFuture<Boolean> sendAccountRevokedEmail(String toEmail, String username, String adminName) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send revoked email to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Thông báo: Tài khoản Poliwise của bạn đã bị thu hồi",
                buildAccountRevokedEmail(username, adminName));
    }

    /**
     * Gửi email thông báo khi tài khoản bị xóa (SOFT DELETED).
     */
    public CompletableFuture<Boolean> sendAccountDeletedEmail(String toEmail, String username, String adminName) {
        if (!emailProperties.enabled()) {
            log.warn("[EMAIL DISABLED] Would send deleted email to {} for user {}", toEmail, username);
            return CompletableFuture.completedFuture(false);
        }

        return sendEmailAsync(toEmail, "Thông báo: Tài khoản Poliwise của bạn đã bị xóa",
                buildAccountDeletedEmail(username, adminName));
    }

    private String buildAccountDeactivatedEmail(String username, String adminName) {
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #f39c12 0%, #e67e22 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .alert { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f39c12; }
                .info { background: #e8f4f8; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Tài khoản bị tạm ngưng</h1>
                <p>Thông báo từ hệ thống Poliwise</p>
            </div>
            <div class="content">
                <p>Xin chào <strong>__USERNAME__</strong>,</p>
                <p>Tài khoản Poliwise của bạn đã bị <strong>tạm ngưng</strong> bởi quản trị viên <strong>__ADMINNAME__</strong>.</p>

                <div class="alert">
                    <h3>Tình trạng tài khoản</h3>
                    <ul>
                        <li>Tên đăng nhập: <strong>__USERNAME__</strong></li>
                        <li>Trạng thái: <span style="color: #e67e22;">TẠM NGƯNG</span></li>
                    </ul>
                </div>

                <div class="info">
                    <strong>Lưu ý:</strong>
                    <ul>
                        <li>Bạn hiện không thể đăng nhập vào hệ thống</li>
                        <li>Liên hệ quản trị viên nếu bạn cần được hỗ trợ</li>
                        <li>Tài khoản có thể được kích hoạt lại trong tương lai</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """.replace("__USERNAME__", escapeHtml(username))
          .replace("__ADMINNAME__", escapeHtml(adminName));
    }

    private String buildAccountReactivatedEmail(String username, String adminName) {
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #27ae60 0%, #2ecc71 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .success { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #27ae60; }
                .info { background: #e8f8f5; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
                a { color: #27ae60; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Tài khoản đã được kích hoạt lại</h1>
                <p>Thông báo từ hệ thống Poliwise</p>
            </div>
            <div class="content">
                <p>Xin chào <strong>__USERNAME__</strong>,</p>
                <p>Tài khoản Poliwise của bạn đã được <strong>kích hoạt lại</strong> bởi quản trị viên <strong>__ADMINNAME__</strong>.</p>

                <div class="success">
                    <h3>Tình trạng tài khoản</h3>
                    <ul>
                        <li>Tên đăng nhập: <strong>__USERNAME__</strong></li>
                        <li>Trạng thái: <span style="color: #27ae60;">HOẠT ĐỘNG</span></li>
                    </ul>
                </div>

                <div class="info">
                    <strong>Bạn có thể:</strong>
                    <ul>
                        <li>Đăng nhập vào hệ thống Poliwise</li>
                        <li>Sử dụng tất cả các tính năng như bình thường</li>
                    </ul>
                    <p>Đăng nhập tại: <a href="#">https://poliwise.vn</a></p>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """.replace("__USERNAME__", escapeHtml(username))
          .replace("__ADMINNAME__", escapeHtml(adminName));
    }

    private String buildAccountRevokedEmail(String username, String adminName) {
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #c0392b 0%, #e74c3c 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .alert { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #c0392b; }
                .warning { background: #fdf2f2; border: 1px solid #f5c6cb; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Tài khoản đã bị thu hồi</h1>
                <p>Thông báo từ hệ thống Poliwise</p>
            </div>
            <div class="content">
                <p>Xin chào <strong>__USERNAME__</strong>,</p>
                <p>Tài khoản Poliwise của bạn đã bị <strong>thu hồi</strong> bởi quản trị viên <strong>__ADMINNAME__</strong>.</p>

                <div class="alert">
                    <h3>Tình trạng tài khoản</h3>
                    <ul>
                        <li>Tên đăng nhập: <strong>__USERNAME__</strong></li>
                        <li>Trạng thái: <span style="color: #c0392b;">THU HỒI</span></li>
                    </ul>
                </div>

                <div class="warning">
                    <strong>Lưu ý quan trọng:</strong>
                    <ul>
                        <li>Bạn không thể đăng nhập vào hệ thống</li>
                        <li>Tất cả các phiên đăng nhập đã bị thu hồi</li>
                        <li>Liên hệ quản trị viên nếu bạn cần được hỗ trợ</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """.replace("__USERNAME__", escapeHtml(username))
          .replace("__ADMINNAME__", escapeHtml(adminName));
    }

    private String buildAccountDeletedEmail(String username, String adminName) {
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #8e44ad 0%, #9b59b6 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .alert { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #8e44ad; }
                .warning { background: #f5eef8; border: 1px solid #d7bde2; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Tài khoản đã bị xóa</h1>
                <p>Thông báo từ hệ thống Poliwise</p>
            </div>
            <div class="content">
                <p>Xin chào <strong>__USERNAME__</strong>,</p>
                <p>Tài khoản Poliwise của bạn đã bị <strong>xóa</strong> bởi quản trị viên <strong>__ADMINNAME__</strong>.</p>

                <div class="alert">
                    <h3>Tình trạng tài khoản</h3>
                    <ul>
                        <li>Tên đăng nhập: <strong>[ĐÃ XÓA]</strong></li>
                        <li>Trạng thái: <span style="color: #8e44ad;">ĐÃ XÓA</span></li>
                    </ul>
                </div>

                <div class="warning">
                    <strong>Thông tin quan trọng:</strong>
                    <ul>
                        <li>Tài khoản và thông tin cá nhân đã được xóa khỏi hệ thống</li>
                        <li>Bạn không thể đăng nhập hoặc khôi phục tài khoản</li>
                        <li>Liên hệ quản trị viên nếu bạn cần được hỗ trợ</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """.replace("__USERNAME__", escapeHtml(username))
          .replace("__ADMINNAME__", escapeHtml(adminName));
    }

    private CompletableFuture<Boolean> sendEmailAsync(String to, String subject, String htmlBody) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                log.info("[EMAIL] Attempting to send - to: {}, subject: {}", maskEmail(to), subject);

                MimeMessage message = mailSender.createMimeMessage();
                MimeMessageHelper helper = new MimeMessageHelper(message, true, "UTF-8");

                helper.setFrom(emailProperties.fromAddress());
                helper.setTo(to);
                helper.setSubject(subject);
                helper.setText(htmlBody, true);

                mailSender.send(message);

                log.info("[EMAIL] SUCCESS - Email sent to {}", maskEmail(to));
                return true;
            } catch (MessagingException e) {
                log.error("[EMAIL] FAILED - Messaging error for {}: {}", maskEmail(to), e.getMessage(), e);
                return false;
            } catch (Exception e) {
                log.error("[EMAIL] FAILED - Unexpected error for {}: {}", maskEmail(to), e.getMessage(), e);
                return false;
            }
        });
    }

    private String maskEmail(String email) {
        if (email == null || email.length() < 4) return "***";
        int atIndex = email.indexOf('@');
        if (atIndex <= 1) return "***" + email.substring(atIndex);
        return email.substring(0, 2) + "***" + email.substring(atIndex);
    }

    private String buildCredentialsEmail(String username, String password) {
        String html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .credentials { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea; }
                .credentials-row { display: flex; justify-content: space-between; margin: 10px 0; }
                .label { font-weight: bold; color: #555; }
                .value { font-family: monospace; background: #f0f0f0; padding: 5px 10px; border-radius: 4px; }
                .warning { background: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
                a { color: #667eea; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Poliwise</h1>
                <p>Tài khoản của bạn đã được tạo thành công</p>
            </div>
            <div class="content">
                <p>Xin chào,</p>
                <p>Tài khoản Poliwise của bạn đã được tạo. Vui lòng sử dụng thông tin đăng nhập bên dưới:</p>

                <div class="credentials">
                    <div class="credentials-row">
                        <span class="label">Tên đăng nhập:</span>
                        <span class="value">__USERNAME__</span>
                    </div>
                    <div class="credentials-row">
                        <span class="label">Mật khẩu:</span>
                        <span class="value">__PASSWORD__</span>
                    </div>
                </div>

                <div class="warning">
                    <strong>Vì lý do bảo mật:</strong>
                    <ul>
                        <li>Đổi mật khẩu ngay sau khi đăng nhập lần đầu</li>
                        <li>Không chia sẻ thông tin đăng nhập với người khác</li>
                        <li>Sử dụng mật khẩu mạnh (ít nhất 8 ký tự, bao gồm chữ hoa, chữ thường, số và ký tự đặc biệt)</li>
                    </ul>
                </div>

                <p>Đăng nhập tại: <a href="#">https://poliwise.vn</a></p>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """;
        return html
                .replace("__USERNAME__", escapeHtml(username))
                .replace("__PASSWORD__", escapeHtml(password));
    }

    private String buildPasswordResetLinkEmail(String username, String resetLink, Duration ttl) {
        long minutes = Math.max(1, ttl.toMinutes());
        String html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: #2563eb; color: white; padding: 24px; border-radius: 8px 8px 0 0; text-align: center; }
                .content { background: #f9fafb; padding: 24px; border-radius: 0 0 8px 8px; }
                .button { display: inline-block; background: #2563eb; color: white; padding: 12px 18px; border-radius: 6px; text-decoration: none; font-weight: bold; }
                .warning { background: #fff7ed; border: 1px solid #fed7aa; padding: 12px; border-radius: 6px; margin-top: 18px; }
                .footer { text-align: center; color: #6b7280; font-size: 12px; margin-top: 18px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Password reset</h1>
            </div>
            <div class="content">
                <p>Hello <strong>__USERNAME__</strong>,</p>
                <p>Use the link below to set a new password for your Poliwise account.</p>
                <p><a class="button" href="__RESETLINK__">Reset password</a></p>
                <div class="warning">
                    This link expires in __MINUTES__ minutes. If you did not request it, ignore this email.
                </div>
            </div>
            <div class="footer">
                <p>This automated email does not contain your password.</p>
            </div>
        </body>
        </html>
        """;
        return html
                .replace("__USERNAME__", escapeHtml(username))
                .replace("__RESETLINK__", escapeHtml(resetLink))
                .replace("__MINUTES__", Long.toString(minutes));
    }

    private String buildBulkCredentialsEmail(String username, String password, String adminName) {
        String html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #3498db 0%, #2980b9 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center; }
                .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                .credentials { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #3498db; }
                .credentials-row { display: flex; justify-content: space-between; margin: 10px 0; }
                .label { font-weight: bold; color: #555; }
                .value { font-family: monospace; background: #f0f0f0; padding: 5px 10px; border-radius: 4px; }
                .warning { background: #d1ecf1; border: 1px solid #17a2b8; padding: 15px; border-radius: 8px; margin-top: 20px; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Tài khoản Poliwise</h1>
                <p>Thông tin đăng nhập mới</p>
            </div>
            <div class="content">
                <p>Xin chào,</p>
                <p>Tài khoản Poliwise của bạn đã được tạo bởi <strong>__ADMINNAME__</strong>. Dưới đây là thông tin đăng nhập:</p>

                <div class="credentials">
                    <div class="credentials-row">
                        <span class="label">Tên đăng nhập:</span>
                        <span class="value">__USERNAME__</span>
                    </div>
                    <div class="credentials-row">
                        <span class="label">Mật khẩu:</span>
                        <span class="value">__PASSWORD__</span>
                    </div>
                </div>

                <div class="warning">
                    <strong>Mẹo bảo mật:</strong>
                    <ul>
                        <li>Đổi mật khẩu ngay sau khi đăng nhập lần đầu</li>
                        <li>Đăng nhập tại: <strong>https://poliwise.vn</strong></li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
            </div>
        </body>
        </html>
        """;
        return html
                .replace("__ADMINNAME__", escapeHtml(adminName))
                .replace("__USERNAME__", escapeHtml(username))
                .replace("__PASSWORD__", escapeHtml(password));
    }

    private String buildOtpEmail(String username, String otpCode) {
        String html = """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }
                .header { background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%); color: white; padding: 30px; border-radius: 16px 16px 0 0; text-align: center; }
                .content { background: #fafafa; padding: 30px; border-radius: 0 0 16px 16px; }
                .otp-box { background: white; border-radius: 12px; padding: 30px; margin: 25px 0; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.08); }
                .otp-code { font-size: 2.5rem; font-weight: 700; letter-spacing: 0.5em; color: #6366f1; margin: 10px 0; }
                .otp-label { font-size: 0.875rem; color: #6b7280; text-transform: uppercase; letter-spacing: 0.1em; }
                .warning { background: #fef3c7; border: 1px solid #fbbf24; padding: 15px; border-radius: 8px; margin-top: 20px; font-size: 0.875rem; }
                .footer { text-align: center; color: #888; font-size: 12px; margin-top: 20px; }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Xác thực đặt lại mật khẩu</h1>
                <p>Poliwise</p>
            </div>
            <div class="content">
                <p>Xin chào <strong>__USERNAME__</strong>,</p>
                <p>Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn. Vui lòng sử dụng mã xác thực bên dưới:</p>

                <div class="otp-box">
                    <div class="otp-label">Mã xác thực</div>
                    <div class="otp-code">__OTPCODE__</div>
                    <div style="font-size: 0.8125rem; color: #6b7280; margin-top: 8px;">Mã có hiệu lực trong 5 phút</div>
                </div>

                <div class="warning">
                    <strong>Lưu ý bảo mật:</strong>
                    <ul style="margin: 8px 0 0; padding-left: 20px;">
                        <li>Không chia sẻ mã này với bất kỳ ai</li>
                        <li>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này</li>
                        <li>Đội ngũ Poliwise không bao giờ hỏi mã OTP của bạn</li>
                    </ul>
                </div>
            </div>
            <div class="footer">
                <p>Email này được gửi tự động từ hệ thống Poliwise.</p>
                <p>Không trả lời email này.</p>
            </div>
        </body>
        </html>
        """;
        return html
                .replace("__USERNAME__", escapeHtml(username))
                .replace("__OTPCODE__", escapeHtml(otpCode));
    }

    private String escapeHtml(String input) {
        if (input == null) return "";
        return input
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace("\"", "&quot;")
                .replace("'", "&#39;");
    }
}
