'use client';

import React, { useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';

export interface InteractiveGridProps {
  className?: string;
  squareSize?: number;
  borderColor?: string;
  hoverFillColor?: string;
  speed?: number;
}

/**
 * Adapted from React Bits Squares — Canvas2D architectural grid with subtle cursor highlight.
 * Automatically renders static when prefers-reduced-motion is enabled.
 */
export function InteractiveGrid({
  className,
  squareSize = 44,
  borderColor = 'rgba(148, 163, 184, 0.14)',
  hoverFillColor = 'rgba(20, 184, 166, 0.16)',
  speed = 0.22,
}: InteractiveGridProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let frameId = 0;
    let offset = 0;
    let hovered: { x: number; y: number } | null = null;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.max(1, Math.floor(rect.width * dpr));
      canvas.height = Math.max(1, Math.floor(rect.height * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = () => {
      const rect = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, rect.width, rect.height);
      const startX = -(offset % squareSize);
      const startY = -(offset % squareSize);

      ctx.strokeStyle = borderColor;
      ctx.lineWidth = 1;

      for (let x = startX; x < rect.width + squareSize; x += squareSize) {
        for (let y = startY; y < rect.height + squareSize; y += squareSize) {
          if (
            hovered &&
            hovered.x >= x &&
            hovered.x < x + squareSize &&
            hovered.y >= y &&
            hovered.y < y + squareSize
          ) {
            ctx.fillStyle = hoverFillColor;
            ctx.fillRect(x + 0.5, y + 0.5, squareSize - 1, squareSize - 1);
          }
          ctx.strokeRect(x + 0.5, y + 0.5, squareSize, squareSize);
        }
      }
    };

    const tick = () => {
      offset = (offset + speed) % squareSize;
      draw();
      frameId = window.requestAnimationFrame(tick);
    };

    const onMove = (event: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (x >= 0 && y >= 0 && x <= rect.width && y <= rect.height) {
        hovered = { x, y };
      } else {
        hovered = null;
      }
      if (reducedMotion) draw();
    };

    const onLeave = () => {
      hovered = null;
      if (reducedMotion) draw();
    };

    resize();
    if (reducedMotion) {
      draw();
    } else {
      frameId = window.requestAnimationFrame(tick);
    }

    const ro = new ResizeObserver(() => {
      resize();
      if (reducedMotion) draw();
    });
    ro.observe(canvas);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseout', onLeave);

    return () => {
      window.cancelAnimationFrame(frameId);
      ro.disconnect();
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseout', onLeave);
    };
  }, [squareSize, borderColor, hoverFillColor, speed]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden
      className={cn(
        'pointer-events-none absolute inset-0 h-full w-full [mask-image:radial-gradient(ellipse_80%_75%_at_50%_45%,black_30%,transparent_95%)]',
        className,
      )}
    />
  );
}
