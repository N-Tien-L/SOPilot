# Next.js / React Test Patterns

## Initial Setup (Vitest)
The frontend currently lacks a testing framework. To initialize it:

1. **Install dependencies:**
   `pnpm add -D vitest @testing-library/react @testing-library/jest-dom @vitejs/plugin-react jsdom`
2. **Create `vitest.config.ts`:**
   ```typescript
   import { defineConfig } from 'vitest/config'
   import react from '@vitejs/plugin-react'
   
   export default defineConfig({
     plugins: [react()],
     test: {
       environment: 'jsdom',
       setupFiles: ['./vitest.setup.ts'],
     },
   })
   ```
3. **Create `vitest.setup.ts`:**
   ```typescript
   import '@testing-library/jest-dom'
   ```
4. **Update `package.json`:** Add `"test": "vitest run"` and `"test:watch": "vitest"`

## 1. Component Test
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Button from './Button';

describe('Button', () => {
  it('should render children and handle click', () => {
    const handleClick = vi.fn();
    render(<Button onClick={handleClick}>Click Me</Button>);
    
    const button = screen.getByText('Click Me');
    expect(button).toBeInTheDocument();
    
    fireEvent.click(button);
    expect(handleClick).toHaveBeenCalledTimes(1);
  });
});
```

## 2. Zustand Store Test
```typescript
import { act } from '@testing-library/react';
import { useAuthStore } from './authStore';

describe('useAuthStore', () => {
  it('should update user on login', () => {
    const { login } = useAuthStore.getState();
    
    act(() => {
      login({ id: 1, name: 'Test' });
    });
    
    expect(useAuthStore.getState().user).toEqual({ id: 1, name: 'Test' });
  });
});
```
