'use client';

import React, { useState, KeyboardEvent } from 'react';
import { X } from 'lucide-react';
import styles from './TagInput.module.css';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

export function TagInput({ value, onChange, placeholder = 'Thêm tag...' }: TagInputProps) {
  const [input, setInput] = useState('');

  const addTag = () => {
    const trimmed = input.trim();
    if (trimmed && !value.includes(trimmed)) {
      onChange([...value, trimmed]);
    }
    setInput('');
  };

  const removeTag = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTag();
    } else if (e.key === 'Backspace' && !input && value.length > 0) {
      removeTag(value.length - 1);
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.tagList}>
        {value.map((tag, index) => (
          <span key={`${tag}-${index}`} className={styles.tagChip}>
            {tag}
            <button type="button" className={styles.tagRemove} onClick={() => removeTag(index)}>
              <X size={12} />
            </button>
          </span>
        ))}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={addTag}
          placeholder={value.length === 0 ? placeholder : ''}
          className={styles.tagInput}
        />
      </div>
    </div>
  );
}

export default TagInput;
