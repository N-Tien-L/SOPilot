'use client';

import React from 'react';
import { motion } from 'motion/react';
import { cn } from '@/lib/utils';

export interface BlurTextProps {
  text: string;
  className?: string;
  delay?: number;
  stepDelay?: number;
  as?: 'h1' | 'h2' | 'h3' | 'p' | 'span';
}

/**
 * Adapted from React Bits BlurText — word-by-word blur-to-sharp entrance powered by Motion.
 * Respects MotionConfig reducedMotion="user".
 */
export function BlurText({
  text,
  className,
  delay = 0,
  stepDelay = 0.045,
  as = 'h1',
}: BlurTextProps) {
  const words = text.split(' ');
  const Tag = as;

  return (
    <Tag className={cn('inline-flex flex-wrap gap-x-[0.28em]', className)}>
      {words.map((word, idx) => (
        <motion.span
          key={`${word}-${idx}`}
          initial={{ opacity: 0, filter: 'blur(8px)', y: 8 }}
          animate={{ opacity: 1, filter: 'blur(0px)', y: 0 }}
          transition={{
            duration: 0.42,
            delay: delay + idx * stepDelay,
            ease: [0.22, 1, 0.36, 1],
          }}
          className="inline-block will-change-[transform,opacity,filter]"
        >
          {word}
        </motion.span>
      ))}
    </Tag>
  );
}
