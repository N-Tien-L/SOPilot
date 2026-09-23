# Mock Documents Manifest

| Filename | Scenario | Target Deduplication Layer | SHA-256 Checksum |
|----------|----------|----------------------------|------------------|
| `original_safety_policy.pdf` | A1 | Baseline document for Layer 1. | `124f11d56af61e4b896dd6e0e2d533123346aed527e3b4517ec50c3205f2b34c` |
| `original_safety_policy_copy.pdf` | A2 | Exact byte-level duplicate (Layer 1 hit). | `124f11d56af61e4b896dd6e0e2d533123346aed527e3b4517ec50c3205f2b34c` |
| `safety_policy_v1.docx` | B1 | Same extracted text, different format (Layer 2 hit). | `a9d1a0ec3ac73ddafcb949fef08fd75dd204da756c5a4826a80c41ab15560f14` |
| `safety_policy_v1.txt` | B2 | Same extracted text, raw format (Layer 2 hit). | `584ca837b0e3df1206eaefa8190dd22bb676112ed91e3eb5d7069cb23e86a008` |
| `safety_policy_paraphrase.pdf` | C1 | Paraphrased text, >0.95 semantic similarity (Layer 3 hit). | `557cd4e17cec4d2edfe522a7820a36ba4ed68d019f75981e946ee13b7488fc77` |
| `safety_policy_light_edit.pdf` | C2 | Lightly edited text, >0.98 semantic similarity (Layer 3 hit). | `59227fbc8568cacc01f3457b07b1ccb7daeded9fc1a29a0a9634dcc27edfaee2` |
| `data_retention_policy.pdf` | D1 | Completely new document (No hit, passes deduplication). | `0384ed87e827af67589ab6b10f7acaab12f737a2c4f1c851db3422d802be8a84` |
| `empty_document.pdf` | E1 | PDF with no extractable text (Layer 2/3 empty text edge case). | `698f508c75872eceb509bc0ca508b7d6f43c13bdd90b4be9b51bd70b502fa29a` |
| `large_document.pdf` | E2 | Large document with first 4000 chars matching A1 (Layer 3 partial hit test). | `25b210644e661cd76c6a61aedc01392a11b62c43e6c27a02e6e5d69fe0dca179` |
