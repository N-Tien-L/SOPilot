-- V2-30: accepting an invitation and listing a user's pending invitations (TECH-V2-core-api §5.3).
-- Runs as sopilot_migrator. Additive only. The invitation table itself is V004.
--
-- Why SECURITY DEFINER: the invitee is not a member yet and the link carries only a token, so the caller
-- has no workspace to bind RLS to. Both helpers run as the table owner and never trust a caller-supplied
-- email: the address is read from core.users for the verified user id.

-- FORCE RLS also binds the owner; the definer helpers need their own policy on the tables they touch
-- (see V003). The migrator already owns these tables, so this grants it nothing new; sopilot_core_app
-- is unaffected.
CREATE POLICY definer_access ON core.invitations TO sopilot_migrator USING (true) WITH CHECK (true);
CREATE POLICY definer_access ON core.departments TO sopilot_migrator USING (true) WITH CHECK (true);

-- Redeem one invitation for one user, atomically. The invitation row is locked FOR UPDATE, so two
-- concurrent requests serialize: the second sees accepted_at set and cannot reuse the link.
-- Identify the invitation by token hash (the link) or by id (the pending list shown after login);
-- exactly one of p_token_hash / p_invitation_id is non-null.
--
-- o_outcome:
--   ACCEPTED          membership created (or already existed) and the invitation is now used
--   ALREADY_ACCEPTED  the same user redeemed it earlier and is still a member: idempotent success
--   ALREADY_USED      redeemed by someone else, or by this user who is no longer a member
--   NOT_FOUND         unknown token/id, workspace deleted, or (by id) the invitation is for another email
--   REVOKED, EXPIRED  invitation can no longer be used
--   EMAIL_MISMATCH    link belongs to another email; the invitation is left untouched
--   EMPLOYEE_CODE_TAKEN  another member took the employee code since the invitation was created
CREATE FUNCTION core.accept_invitation(p_user_id uuid, p_token_hash bytea, p_invitation_id uuid)
    RETURNS TABLE (o_outcome text, o_workspace_id uuid, o_invitation_id uuid, o_role text,
                   o_department_id uuid, o_department_dropped boolean)
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$
DECLARE
    v_user       core.users%ROWTYPE;
    v_inv        core.invitations%ROWTYPE;
    v_member     core.memberships%ROWTYPE;
    v_department uuid;
    v_dropped    boolean := false;
    v_constraint text;
BEGIN
    IF (p_token_hash IS NULL) = (p_invitation_id IS NULL) THEN
        RAISE EXCEPTION 'exactly one of token hash and invitation id is required';
    END IF;

    SELECT * INTO v_user FROM core.users u WHERE u.id = p_user_id;
    IF NOT FOUND THEN
        RETURN QUERY SELECT 'NOT_FOUND', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        RETURN;
    END IF;

    IF p_token_hash IS NOT NULL THEN
        SELECT * INTO v_inv FROM core.invitations i WHERE i.token_hash = p_token_hash FOR UPDATE;
    ELSE
        -- By id only the addressee may look: another email is indistinguishable from "does not exist".
        SELECT * INTO v_inv FROM core.invitations i
         WHERE i.id = p_invitation_id AND i.email = lower(v_user.email) FOR UPDATE;
    END IF;
    IF NOT FOUND OR NOT EXISTS (SELECT 1 FROM core.workspaces w
                                 WHERE w.id = v_inv.workspace_id AND w.deleted_at IS NULL) THEN
        RETURN QUERY SELECT 'NOT_FOUND', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        RETURN;
    END IF;

    SELECT * INTO v_member FROM core.memberships m
     WHERE m.workspace_id = v_inv.workspace_id AND m.user_id = p_user_id;

    IF v_inv.accepted_at IS NOT NULL THEN
        IF v_inv.accepted_by = p_user_id AND v_member.user_id IS NOT NULL THEN
            RETURN QUERY SELECT 'ALREADY_ACCEPTED', v_inv.workspace_id, v_inv.id, v_member.role,
                                v_member.department_id, false;
        ELSE
            RETURN QUERY SELECT 'ALREADY_USED', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        END IF;
        RETURN;
    END IF;
    IF v_inv.revoked_at IS NOT NULL THEN
        RETURN QUERY SELECT 'REVOKED', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        RETURN;
    END IF;
    IF v_inv.expires_at <= now() THEN
        RETURN QUERY SELECT 'EXPIRED', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        RETURN;
    END IF;
    IF v_inv.email <> lower(v_user.email) THEN
        RETURN QUERY SELECT 'EMAIL_MISMATCH', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
        RETURN;
    END IF;

    IF v_member.user_id IS NOT NULL THEN
        -- Already a member (for instance added by another path): only mark the link as used.
        UPDATE core.invitations SET accepted_at = now(), accepted_by = p_user_id WHERE id = v_inv.id;
        RETURN QUERY SELECT 'ACCEPTED', v_inv.workspace_id, v_inv.id, v_member.role,
                            v_member.department_id, false;
        RETURN;
    END IF;

    -- A department archived (or deleted) after the invitation was issued is not assigned any more
    -- (TECH §3.2); the member still joins, and the caller reports that the department was dropped.
    IF v_inv.department_id IS NOT NULL THEN
        SELECT d.id INTO v_department FROM core.departments d
         WHERE d.workspace_id = v_inv.workspace_id AND d.id = v_inv.department_id AND d.status = 'ACTIVE';
        v_dropped := v_department IS NULL;
    END IF;

    BEGIN
        INSERT INTO core.memberships (workspace_id, user_id, role, status, display_name, email,
                                      employee_code, job_title, department_id)
        VALUES (v_inv.workspace_id, p_user_id, v_inv.role, 'ACTIVE',
                coalesce(v_inv.display_name, v_user.display_name), lower(v_user.email),
                v_inv.employee_code, v_inv.job_title, v_department);
    EXCEPTION WHEN unique_violation THEN
        GET STACKED DIAGNOSTICS v_constraint = CONSTRAINT_NAME;
        IF v_constraint = 'uq_membership_employee_code' THEN
            RETURN QUERY SELECT 'EMPLOYEE_CODE_TAKEN', NULL::uuid, NULL::uuid, NULL::text, NULL::uuid, false;
            RETURN;
        END IF;
        RAISE;
    END;

    UPDATE core.invitations SET accepted_at = now(), accepted_by = p_user_id WHERE id = v_inv.id;
    RETURN QUERY SELECT 'ACCEPTED', v_inv.workspace_id, v_inv.id, v_inv.role, v_department, v_dropped;
END $$;

-- Pending invitations addressed to the user's email, for the login payload (pendingInvitations).
CREATE FUNCTION core.pending_invitations_for_user(p_user_id uuid)
    RETURNS TABLE (o_invitation_id uuid, o_workspace_name text, o_role text)
    LANGUAGE sql
    STABLE
    SECURITY DEFINER
    SET search_path = core, pg_temp
    AS $$
    SELECT i.id, w.name, i.role
      FROM core.users u
      JOIN core.invitations i ON i.email = lower(u.email)
      JOIN core.workspaces w ON w.id = i.workspace_id AND w.deleted_at IS NULL
     WHERE u.id = p_user_id
       AND i.accepted_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > now()
       AND NOT EXISTS (SELECT 1 FROM core.memberships m
                        WHERE m.workspace_id = i.workspace_id AND m.user_id = u.id)
     ORDER BY i.created_at, i.id
$$;

REVOKE EXECUTE ON FUNCTION core.accept_invitation(uuid, bytea, uuid),
                           core.pending_invitations_for_user(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION core.accept_invitation(uuid, bytea, uuid),
                          core.pending_invitations_for_user(uuid) TO sopilot_core_app;

-- Index for the pending-by-email lookup above and the admin list.
CREATE INDEX ix_invitations_email ON core.invitations(email) WHERE accepted_at IS NULL AND revoked_at IS NULL;
