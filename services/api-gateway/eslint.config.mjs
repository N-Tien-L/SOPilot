// @ts-check
import eslint from '@eslint/js';
import prettierRecommended from 'eslint-plugin-prettier/recommended';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  // Global ignores (flat config)
  {
    ignores: [
      'eslint.config.mjs',
      'node_modules/**',
      'dist/**',
      'coverage/**',
      'generated/**',
    ],
  },
  // Base JS rules
  eslint.configs.recommended,
  // TypeScript (non type-checked) to reduce false positives and speed
  ...tseslint.configs.recommended,
  // Project TS settings and rules
  {
    files: ['**/*.ts'],
    languageOptions: {
      sourceType: 'commonjs',
      parserOptions: {
        // Disable type-aware linting by default; opt-in later if needed
        tsconfigRootDir: import.meta.dirname,
      },
      globals: {
        ...globals.node,
        ...globals.jest,
      },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-floating-promises': 'off',
      // Avoid noisy unsafe rules without type-aware linting
      '@typescript-eslint/no-unsafe-argument': 'off',
      '@typescript-eslint/no-unsafe-call': 'off',
      '@typescript-eslint/no-unsafe-member-access': 'off',
    },
  },
  // Keep code formatted by Prettier and surface formatting as lint issues
  prettierRecommended,
);
