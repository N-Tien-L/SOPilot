# Corporate Data Governance and Information Security Policy

## Document Control

- **Policy Number:** DGP-2024-001
- **Version:** 3.2
- **Effective Date:** January 15, 2024
- **Review Date:** July 15, 2024
- **Classification:** Internal Use Only
- **Owner:** Office of the Chief Information Security Officer
- **Approved By:** Board of Directors, Resolution 2024-0042

## 1. Purpose and Scope

This policy establishes the framework for managing corporate data assets, ensuring information security, and maintaining regulatory compliance across all business units of Meridian Technologies Inc. It applies to every employee, contractor, consultant, and third-party vendor who accesses, processes, stores, or transmits company data in any form, whether digital, physical, or verbal.

The data governance program governed by this policy is designed to protect the confidentiality, integrity, and availability of information assets throughout their entire lifecycle — from creation and initial classification through active use, archival, and eventual secure destruction. This policy also establishes accountability structures, defines roles and responsibilities, and mandates specific controls proportionate to the sensitivity and criticality of each data category.

All business units must designate a Data Steward responsible for enforcing compliance within their domain. The Data Steward reports directly to the Chief Data Officer and participates in quarterly reviews of data handling practices. Failure to comply with this policy may result in disciplinary action up to and including termination of employment or contract, as well as potential civil or criminal penalties where applicable under law.

## 2. Definitions and Data Classification

For the purposes of this policy, data is classified into four distinct tiers based on sensitivity, regulatory requirements, and business impact.

**Tier 1 — Restricted Data:** This classification applies to the most sensitive information whose unauthorized disclosure would cause severe financial, legal, or reputational harm. Examples include personally identifiable information such as Social Security numbers, financial account credentials, trade secrets, merger and acquisition plans, and unannounced product designs. Access is limited to named individuals approved by the Data Owner and requires multi-factor authentication for every access event. Data must be encrypted at rest using AES-256 and in transit using TLS 1.3 or higher.

**Tier 2 — Confidential Data:** This tier covers information that is not publicly available and whose disclosure would cause significant but non-catastrophic harm. Examples include internal financial reports, customer lists, vendor contracts, employee performance reviews, and unreleased marketing strategies. Access requires role-based authorization and must be logged. Encryption at rest is required for digital copies; physical copies must be stored in locked cabinets with access logs.

**Tier 3 — Internal Data:** This classification includes information intended for use within the organization but whose disclosure would not cause material harm. Examples include internal newsletters, organizational charts, general procedural documents, and non-sensitive training materials. Access is available to all authenticated employees. Encryption at rest is recommended but not mandatory; however, all internal data must still be transmitted over encrypted channels.

**Tier 4 — Public Data:** This tier encompasses information that is approved for public consumption, including published marketing materials, press releases, job postings, and publicly filed regulatory documents. No access restrictions apply. However, public data must still be managed through the document lifecycle process to ensure accuracy and prevent inadvertent disclosure of embedded metadata that could reveal internal information.

## 3. Data Lifecycle Management

Every data asset must be managed through six lifecycle stages, each with mandatory controls and documentation requirements.

**Creation and Capture:** All new data assets must be tagged with appropriate metadata at the moment of creation. This metadata must include the data owner, classification tier, creation date, intended retention period, and the business purpose for which the data was created. Automated tagging tools are available through the corporate data management platform and must be used for all structured data. Unstructured documents must be manually classified by the author before being stored in approved repositories.

**Storage and Processing:** Data must only be stored on approved corporate platforms that have passed the information security review process. Personal devices, unauthorized cloud services, and unapproved removable media are strictly prohibited for storing any Tier 1 or Tier 2 data. Processing of Restricted Data must occur within isolated environments with dedicated audit logging. All data processing activities must be documented in the Data Processing Register maintained by the Data Governance Office.

**Sharing and Transmission:** Tier 1 data may only be shared through the enterprise data exchange platform with end-to-end encryption and automatic expiration controls. Tier 2 data may be shared via approved corporate email with encryption or through the secure file sharing portal. Sharing of Tier 1 or Tier 2 data with external parties requires a signed Data Protection Agreement reviewed and approved by the Legal Department. Any data shared externally must be logged in the Data Transfer Register with the recipient identity, purpose, date, and classification level.

**Archival:** Data that is no longer actively used but must be retained for legal, regulatory, or business reasons must be moved to the designated archival storage within 30 days of its last active access. Archived data must maintain its original classification and access restrictions. The archival system applies automatic integrity checks on a monthly basis to detect corruption or unauthorized modification.

**Retention:** Retention periods are determined by the applicable regulatory framework, the data classification tier, and the specific business purpose. The Minimum Retention Schedule, maintained by the Legal Department, specifies the mandatory retention period for each data category. No data may be destroyed before the expiration of its applicable retention period, regardless of classification tier.

**Destruction:** Upon expiration of the retention period, data must be securely destroyed using methods appropriate to its classification. Tier 1 and Tier 2 digital data must be destroyed using NIST SP 800-88 compliant methods. Physical documents must be cross-cut shredded to particle size not exceeding 2mm by 15mm. Destruction events must be logged with the date, method, data description, and the identity of the person who authorized and performed the destruction.

## 4. Access Control and Authentication

Access to data assets is governed by the principle of least privilege and the need-to-know basis. Every access decision must be documented and justified.

**User Account Management:** All user accounts must be provisioned through the Identity Governance and Administration platform with approval from the employee's direct manager and the relevant Data Steward. Accounts must be reviewed quarterly through a formal recertification process. Terminated employee accounts must be deactivated within four hours of the termination effective date. Dormant accounts with no activity for 90 consecutive days must be automatically suspended pending investigation.

**Authentication Requirements:** All systems containing Tier 1 or Tier 2 data must enforce multi-factor authentication using a hardware security key or authenticator application. SMS-based two-factor authentication is explicitly prohibited for Tier 1 data systems due to known SIM-swapping vulnerabilities. Password policies require a minimum of 16 characters for privileged accounts and 12 characters for standard accounts, with mandatory rotation every 180 days for privileged accounts.

**Authorization Controls:** Role-based access control must be implemented on all enterprise systems. Privileged access beyond standard role permissions requires just-in-time provisioning with automatic expiration within eight hours. All privileged access sessions must be recorded and retained for 180 days. Emergency access procedures, commonly known as break-glass accounts, must be tested quarterly and used only when normal access procedures cannot be followed, with mandatory post-incident review within 24 hours.

## 5. Monitoring, Auditing, and Incident Response

Continuous monitoring and periodic auditing are essential components of the data governance framework. These mechanisms ensure that controls remain effective and that deviations are detected and remediated promptly.

**Security Monitoring:** The Security Operations Center maintains 24/7 monitoring of all data access events through the Security Information and Event Management platform. Anomalous access patterns, including unusual data volumes, access outside normal business hours, and access from unrecognized locations, trigger automated alerts for investigation. High-severity alerts must be acknowledged within 15 minutes and escalated to the Incident Response Team within one hour.

**Audit Programs:** The Internal Audit Department conducts annual assessments of data governance compliance across all business units. Audit scope includes access control effectiveness, data classification accuracy, retention policy adherence, and incident response readiness. Audit findings are reported to the Audit Committee of the Board of Directors and must be remediated within the timelines specified in the Audit Remediation Tracking System.

**Incident Response:** Data security incidents must be reported to the Security Operations Center within 30 minutes of discovery through the Incident Reporting Portal or the 24/7 hotline. The Incident Response Team classifies incidents by severity and initiates the appropriate response procedure. Incidents involving Tier 1 data require notification to affected individuals within 72 hours and to relevant regulatory authorities as mandated by applicable data protection laws. Post-incident reviews must be completed within 14 days of incident closure, with lessons learned incorporated into the governance program.

## 6. Training, Enforcement, and Policy Maintenance

Effective data governance requires continuous education and consistent enforcement across the organization.

**Training Requirements:** All employees must complete mandatory data governance and security awareness training within 30 days of hire and annually thereafter. Role-specific training is required for Data Stewards, system administrators, and personnel with access to Tier 1 data. Training completion is tracked through the Learning Management System, and non-completion results in automatic suspension of data access privileges until the requirement is fulfilled.

**Enforcement and Consequences:** Violations of this policy are taken seriously and addressed proportionate to the severity and intent of the violation. Minor or first-time violations typically result in mandatory remedial training and a formal warning. Repeated violations or those involving willful negligence may result in suspension of data access, reassignment of duties, or termination of employment. Violations that constitute criminal offenses under applicable law are reported to the appropriate law enforcement authorities.

**Policy Maintenance:** This policy is reviewed and updated semi-annually by the Data Governance Committee, or more frequently if triggered by significant regulatory changes, security incidents, or organizational restructuring. All proposed changes must be reviewed by the Legal Department, approved by the Chief Information Security Officer, and ratified by the Board of Directors before implementation. The version history and change log are maintained as appendices to this document.

---

**Document Classification:** Internal Use Only
**Retention Period:** 10 years from effective date
**Distribution:** All employees, contractors, and third-party vendors
**Next Scheduled Review:** July 15, 2024

For questions about this policy, contact the Data Governance Office at governance@meridiantech.com or extension 4500.
