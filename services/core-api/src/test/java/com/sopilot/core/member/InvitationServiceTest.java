package com.sopilot.core.member;

import com.sopilot.core.common.ApiException;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/** Input rules and token handling of invitations without a database (V2-30, TECH-V2-core-api §5.3). */
class InvitationServiceTest {

    @Test
    void emailsAreTrimmedAndLowerCased() {
        assertThat(InvitationService.normalizeEmail("  Binh@Acme.COM ")).isEqualTo("binh@acme.com");
    }

    @Test
    void malformedEmailsAreRejected() {
        for (String bad : new String[] {null, "", "  ", "no-at-sign", "a@b", "a b@c.com", "a@@c.com",
                "x".repeat(250) + "@a.com"}) {
            assertThatThrownBy(() -> InvitationService.normalizeEmail(bad))
                    .isInstanceOfSatisfying(ApiException.class,
                            e -> assertThat(e.status()).isEqualTo(HttpStatus.BAD_REQUEST));
        }
    }

    @Test
    void anInvitationCanNeverGrantOwner() {
        assertThat(InvitationService.parseInvitedRole("ADMIN")).isEqualTo("ADMIN");
        assertThat(InvitationService.parseInvitedRole("MEMBER")).isEqualTo("MEMBER");
        for (String bad : new String[] {"OWNER", "owner", "", null, "ROOT"}) {
            assertThatThrownBy(() -> InvitationService.parseInvitedRole(bad)).isInstanceOf(ApiException.class);
        }
    }

    @Test
    void optionalTextIsTrimmedBlankBecomesNullAndLongTextIsRejected() {
        assertThat(InvitationService.optionalText("  Kế toán ", 100, "jobTitle")).isEqualTo("Kế toán");
        assertThat(InvitationService.optionalText("   ", 100, "jobTitle")).isNull();
        assertThat(InvitationService.optionalText(null, 100, "jobTitle")).isNull();
        assertThatThrownBy(() -> InvitationService.optionalText("x".repeat(101), 100, "jobTitle"))
                .isInstanceOf(ApiException.class);
    }

    @Test
    void tokensAreRandomHaveAtLeast256BitsAndHashToThirtyTwoBytes() {
        String a = InvitationService.newToken();
        String b = InvitationService.newToken();

        assertThat(a).isNotEqualTo(b).hasSize(43).matches("[A-Za-z0-9_-]+");
        assertThat(InvitationService.hash(a)).hasSize(32).isNotEqualTo(InvitationService.hash(b));
        assertThat(InvitationService.hash(a)).isEqualTo(InvitationService.hash(a));
    }

    @Test
    void createdLinkIsNeverPrintedByToString() {
        var created = new InvitationService.Created(java.util.UUID.randomUUID(), java.time.OffsetDateTime.now(),
                "http://localhost:3000/invite#token=SECRET");

        assertThat(created.toString()).doesNotContain("SECRET");
    }
}
