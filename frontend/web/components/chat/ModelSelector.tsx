'use client';

import React from 'react';
import { ChevronDown } from 'lucide-react';
import type { ModelInfo } from '@/types';

interface ModelSelectorProps {
  models: ModelInfo[];
  value: string;
  onChange: (id: string) => void;
  disabled?: boolean;
}

const statusColors = {
  available: 'bg-green-500',
  rate_limited: 'bg-yellow-500',
  unavailable: 'bg-red-500',
};

const statusLabels = {
  available: '',
  rate_limited: '(Giới hạn)',
  unavailable: '(Không khả dụng)',
};

export function ModelSelector({ models, value, onChange, disabled }: ModelSelectorProps) {
  if (models.length === 0) return null;

  const selectedModel = models.find((m) => m.id === value) || models.find((m) => m.isDefault) || models[0];

  return (
    <div className="relative">
      <select
        value={selectedModel?.id || value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        className="appearance-none cursor-pointer bg-muted border border-input rounded-lg pl-6 pr-8 py-2 text-xs font-medium text-foreground focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50 disabled:cursor-not-allowed hover:bg-muted/80 transition-colors"
      >
        {models.map((model) => {
          const isDisabled = model.status !== 'available';
          return (
            <option
              key={model.id}
              value={model.id}
              disabled={isDisabled}
              className="text-sm"
            >
              {model.name}
              {model.isDefault ? ' (Mặc định)' : ''}
              {statusLabels[model.status] ? ` ${statusLabels[model.status]}` : ''}
            </option>
          );
        })}
      </select>
      <ChevronDown
        size={14}
        className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none text-muted-foreground"
      />
      <span
        className={`absolute left-2.5 top-1/2 -translate-y-1/2 w-2 h-2 rounded-full ${statusColors[selectedModel?.status || 'unavailable']}`}
      />
    </div>
  );
}

export default ModelSelector;
