
-- =============================================================================
-- Poliwise Base Dataset Seed File
-- Generated: 2026-06-26T03:40:36.193541
-- Source: GitLab Handbook
-- =============================================================================
-- 
-- To use this file:
-- 1. Run Flyway migrations first to create tables
-- 2. psql -U poliwise -d poliwise -f seed_data.sql
--
-- IMPORTANT: This file uses ON CONFLICT DO NOTHING for idempotent execution
-- =============================================================================

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET xmlentity = no;
SET escape_string_warning = off;

-- =============================================================================
-- SECTION: Users
-- =============================================================================



-- Admin user
INSERT INTO core.users (id, username, email, password_hash, role, status)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'admin',
    'admin@poliwise.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqJ5.KK0Ke',  -- password: admin123
    'ADMIN'::core.user_role,
    'ACTIVE'::core.account_status
) ON CONFLICT (username) DO NOTHING;

-- Admin profile
INSERT INTO core.user_profiles (id, user_id, full_name)
VALUES (
    '617bd7c8-d7ab-4b7a-bdca-e9075409ca0d',
    '00000000-0000-0000-0000-000000000001',
    'System Administrator'
) ON CONFLICT (user_id) DO NOTHING;


-- =============================================================================
-- SECTION: Departments
-- =============================================================================



INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    'a097d0cd-be37-4964-a4dd-dba2d04b4417',
    'Executive & Corporate',
    'EXECUTIVE_AND_CORPOR',
    true
) ON CONFLICT (code) DO NOTHING;


INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    '3fc44b8c-2451-40da-ab28-7f5ccf89316f',
    'Engineering & Product',
    'ENGINEERING_AND_PROD',
    true
) ON CONFLICT (code) DO NOTHING;


INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    '30248dab-ef88-415c-b533-cecdd2c2e205',
    'People & Legal',
    'PEOPLE_AND_LEGAL',
    true
) ON CONFLICT (code) DO NOTHING;


INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    '235c0c79-e69e-474f-abaf-fc0652dfd411',
    'Sales & Marketing',
    'SALES_AND_MARKETING',
    true
) ON CONFLICT (code) DO NOTHING;


INSERT INTO core.departments (id, name, code, is_active)
VALUES (
    '8174a8f6-915b-4e78-b3e3-a88100830b52',
    'Infrastructure & Operations',
    'INFRASTRUCTURE_AND_O',
    true
) ON CONFLICT (code) DO NOTHING;


-- =============================================================================
-- SECTION: Categories
-- =============================================================================



INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '41cd3ad3-0419-4f8f-9eaa-a9b8f2fcc746',
    'About',
    'about',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '4c8bfa37-1804-4e5c-876b-cc15caa9004b',
    'Acquisitions',
    'acquisitions',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '28736f28-e875-4121-8b7b-da897cc50d74',
    'Alliances',
    'alliances',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '2d852c17-4d24-4193-8ab6-7cc4f8150413',
    'Board Meetings',
    'board-meetings',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '66b46c47-4e8d-4c42-8852-86f66495760d',
    'Business Technology',
    'business-technology',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '1be5b210-4da0-48db-b0a6-d2037ad54c59',
    'Ceo',
    'ceo',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '7cbbab3d-0e39-4be4-9eb5-949a515c8d8e',
    'Communication',
    'communication',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'e19da25d-95ee-4f4e-873d-64f199c1330f',
    'Company',
    'company',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '5d4be4b0-f9a8-4c2d-990a-355f45761639',
    'Customer Experience',
    'customer-experience',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'd1337108-7b13-4bc2-a99c-48acf361d2c2',
    'Customer Success',
    'customer-success',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '07f99bc0-0443-47d8-98b2-647560c75a73',
    'Eba',
    'eba',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'b00aedf8-548d-499a-9007-7520036bbf73',
    'Engineering',
    'engineering',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '23ed6fdb-f7fa-4a3b-9332-a720078637a8',
    'Enterprise Data',
    'enterprise-data',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '1c27234d-9817-4a24-9a5b-4cfd5590e0d6',
    'Entity',
    'entity',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '88d3cf8d-fb79-4eba-b625-755db54e8ecf',
    'Eta',
    'eta',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '4816b618-3998-4f5b-8f6a-a4367f9c71d4',
    'Finance',
    'finance',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '14719f90-ed16-4ea5-a854-3ae059a6d008',
    'Hiring',
    'hiring',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '2d5d486c-14da-47ab-afd9-5e1e8ee3494e',
    'It',
    'it',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'd8597071-fe50-4a78-afb9-7755c3fae5dd',
    'Job Description Library',
    'job-description-library',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'a17a9292-4e5a-498d-bc27-4b72b2b498b9',
    'Labor And Employment Notices',
    'labor-and-employment-notices',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '93bd889f-5fa0-434a-8a3e-ffc750fb4b2a',
    'Leadership',
    'leadership',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '816dc102-6071-4c7a-89a2-9eb68b72aa97',
    'Legal',
    'legal',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'fea37bc9-52b5-4b45-9943-acc03acf5278',
    'Marketing',
    'marketing',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'ceffecab-1e88-4b68-95ee-53e77066ba6f',
    'People Group',
    'people-group',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '275a6fd5-912b-4918-b8bd-c4bf11f6ea29',
    'People Policies',
    'people-policies',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '27930ebb-77c8-4b40-a754-b680ef126e23',
    'Product',
    'product',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '1b2473e3-630e-4a92-9b16-02f759b70717',
    'Product Development',
    'product-development',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'fa4967e5-fe4f-4c82-b626-6229683420a2',
    'Resellers',
    'resellers',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'f78a4777-ed23-4878-9481-9f97b47eb3c3',
    'Sales',
    'sales',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '23782b89-0f1f-4a04-977f-c241a563cbfb',
    'Security',
    'security',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '0c5afeea-f194-4f25-a3b9-5300bb1f580f',
    'Solutions Architects',
    'solutions-architects',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '1a0ee5a8-a5de-4142-a209-02b72378f518',
    'Support',
    'support',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '28eb8d8f-82a3-417d-a818-83942fa52371',
    'Teamops',
    'teamops',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'ba21503b-2550-4c92-894d-ef5e233ed4ad',
    'Tools And Tips',
    'tools-and-tips',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    'c704fed0-e4c5-41ed-a17f-cfa856e519e1',
    'Total Rewards',
    'total-rewards',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '5117112b-b227-40aa-a22b-0a1b3540a6af',
    'Upstream Studios',
    'upstream-studios',
    true
) ON CONFLICT (slug) DO NOTHING;


INSERT INTO metadata.categories (id, name, slug, is_active)
VALUES (
    '47079495-a164-4465-b078-ed2e3dbd4a0b',
    'Values',
    'values',
    true
) ON CONFLICT (slug) DO NOTHING;
