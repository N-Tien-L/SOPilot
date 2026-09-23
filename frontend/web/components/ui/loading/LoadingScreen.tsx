"use client";

import Image from "next/image";
import React, { useMemo } from "react";
import "./LoadingScreen.scss";

// ─── Particle data ────────────────────────────────────────────────────────────

interface DotConfig {
  top: string;
  left: string;
  size: number; // px
  delay: number; // s
  duration: number; // s
  blur: number; // px  (0 = sharp)
  variant: 1 | 2 | 3; // colour variant
}

interface StarConfig {
  top: string;
  left: string;
  size: number;
  delay: number;
  duration: number;
  rotate: number;
}

/**
 * Hard-coded positions keep SSR / hydration deterministic.
 * Central safe-zone ≈ 30–70 % horizontal, 35–65 % vertical → left clear.
 */
const DOT_DATA: DotConfig[] = [
  // Top band
  {
    top: "4%",
    left: "8%",
    size: 4,
    delay: 0.0,
    duration: 2.8,
    blur: 0,
    variant: 1,
  },
  {
    top: "7%",
    left: "22%",
    size: 3,
    delay: 0.6,
    duration: 3.4,
    blur: 1,
    variant: 2,
  },
  {
    top: "3%",
    left: "55%",
    size: 5,
    delay: 1.1,
    duration: 2.6,
    blur: 0,
    variant: 3,
  },
  {
    top: "9%",
    left: "74%",
    size: 3,
    delay: 0.3,
    duration: 3.1,
    blur: 2,
    variant: 1,
  },
  {
    top: "5%",
    left: "88%",
    size: 4,
    delay: 0.8,
    duration: 2.9,
    blur: 0,
    variant: 2,
  },
  // Left band
  {
    top: "20%",
    left: "4%",
    size: 3,
    delay: 1.4,
    duration: 3.5,
    blur: 1,
    variant: 3,
  },
  {
    top: "35%",
    left: "7%",
    size: 5,
    delay: 0.2,
    duration: 2.7,
    blur: 0,
    variant: 1,
  },
  {
    top: "50%",
    left: "3%",
    size: 3,
    delay: 1.9,
    duration: 3.2,
    blur: 2,
    variant: 2,
  },
  {
    top: "65%",
    left: "8%",
    size: 4,
    delay: 0.5,
    duration: 2.8,
    blur: 0,
    variant: 3,
  },
  {
    top: "80%",
    left: "5%",
    size: 3,
    delay: 1.2,
    duration: 3.6,
    blur: 1,
    variant: 1,
  },
  // Right band
  {
    top: "18%",
    left: "92%",
    size: 4,
    delay: 0.7,
    duration: 2.9,
    blur: 0,
    variant: 2,
  },
  {
    top: "33%",
    left: "95%",
    size: 3,
    delay: 1.5,
    duration: 3.3,
    blur: 1,
    variant: 3,
  },
  {
    top: "52%",
    left: "91%",
    size: 5,
    delay: 0.1,
    duration: 2.6,
    blur: 0,
    variant: 1,
  },
  {
    top: "68%",
    left: "94%",
    size: 3,
    delay: 1.8,
    duration: 3.0,
    blur: 2,
    variant: 2,
  },
  {
    top: "82%",
    left: "90%",
    size: 4,
    delay: 0.4,
    duration: 3.4,
    blur: 0,
    variant: 3,
  },
  // Bottom band
  {
    top: "91%",
    left: "15%",
    size: 3,
    delay: 1.6,
    duration: 2.8,
    blur: 1,
    variant: 1,
  },
  {
    top: "93%",
    left: "42%",
    size: 4,
    delay: 0.9,
    duration: 3.1,
    blur: 0,
    variant: 2,
  },
  {
    top: "88%",
    left: "68%",
    size: 5,
    delay: 0.3,
    duration: 2.7,
    blur: 2,
    variant: 3,
  },
  {
    top: "95%",
    left: "82%",
    size: 3,
    delay: 1.3,
    duration: 3.5,
    blur: 0,
    variant: 1,
  },
  // Mid scatter (avoiding centre 30–70% x, 35–65% y)
  {
    top: "25%",
    left: "18%",
    size: 4,
    delay: 0.6,
    duration: 3.2,
    blur: 1,
    variant: 2,
  },
  {
    top: "75%",
    left: "25%",
    size: 3,
    delay: 1.7,
    duration: 2.9,
    blur: 0,
    variant: 3,
  },
  {
    top: "28%",
    left: "80%",
    size: 5,
    delay: 0.0,
    duration: 3.6,
    blur: 0,
    variant: 1,
  },
  {
    top: "72%",
    left: "78%",
    size: 3,
    delay: 1.1,
    duration: 2.8,
    blur: 2,
    variant: 2,
  },
];

const STAR_DATA: StarConfig[] = [
  { top: "11%", left: "14%", size: 10, delay: 0.0, duration: 3.5, rotate: 0 },
  { top: "16%", left: "37%", size: 8, delay: 0.8, duration: 4.0, rotate: 45 },
  { top: "8%", left: "63%", size: 12, delay: 1.5, duration: 3.2, rotate: 20 },
  { top: "14%", left: "84%", size: 9, delay: 0.3, duration: 4.4, rotate: 60 },
  { top: "30%", left: "12%", size: 11, delay: 1.2, duration: 3.8, rotate: 15 },
  { top: "45%", left: "16%", size: 8, delay: 2.0, duration: 3.0, rotate: 30 },
  { top: "60%", left: "11%", size: 10, delay: 0.6, duration: 4.2, rotate: 75 },
  { top: "78%", left: "20%", size: 9, delay: 1.8, duration: 3.6, rotate: 10 },
  { top: "32%", left: "85%", size: 12, delay: 0.4, duration: 3.4, rotate: 50 },
  { top: "48%", left: "89%", size: 8, delay: 1.6, duration: 4.1, rotate: 35 },
  { top: "64%", left: "83%", size: 10, delay: 0.9, duration: 3.7, rotate: 80 },
  { top: "80%", left: "88%", size: 9, delay: 2.2, duration: 3.3, rotate: 5 },
  { top: "85%", left: "48%", size: 11, delay: 1.0, duration: 4.0, rotate: 25 },
  { top: "86%", left: "33%", size: 8, delay: 0.2, duration: 3.9, rotate: 55 },
  { top: "84%", left: "65%", size: 10, delay: 1.4, duration: 3.1, rotate: 40 },
];

// ─── Component ────────────────────────────────────────────────────────────────

interface LoadingScreenProps {
  /** Image src – replace with your actual asset path */
  imageSrc?: string;
  /** Alt text for the icon */
  imageAlt?: string;
  /** Image size in px */
  imageSize?: number;
  /** Displayed status message */
  text?: string;
}

export default function LoadingScreen({
  imageSrc = "/images/Poliwise-user.png",
  imageAlt = "logo-user",
  imageSize = 200,
  text = "Đang tải...",
}: LoadingScreenProps) {
  /* Inline CSS custom-props for each particle so SCSS can read them */
  const dots = useMemo(() => DOT_DATA, []);
  const stars = useMemo(() => STAR_DATA, []);

  return (
    <div className="pattern-loading-user" aria-label="Loading" role="status">
      {/* ── Dot-light particles ── */}
      {dots.map((d, i) => (
        <span
          key={`dot-${i}`}
          className={`pattern-loading-user-dot-light variant-${d.variant}`}
          style={
            {
              top: d.top,
              left: d.left,
              "--dot-size": `${d.size}px`,
              "--dot-delay": `${d.delay}s`,
              "--dot-duration": `${d.duration}s`,
              "--dot-blur": `${d.blur}px`,
            } as React.CSSProperties
          }
          aria-hidden="true"
        />
      ))}

      {/* ── Star-light particles ── */}
      {stars.map((s, i) => (
        <span
          key={`star-${i}`}
          className="pattern-loading-user-star-light"
          style={
            {
              top: s.top,
              left: s.left,
              "--star-size": `${s.size}px`,
              "--star-delay": `${s.delay}s`,
              "--star-duration": `${s.duration}s`,
              "--star-rotate": `${s.rotate}deg`,
            } as React.CSSProperties
          }
          aria-hidden="true"
        />
      ))}

      {/* ── Centre content ── */}
      <div className="pattern-loading-user-center">
        <div className="pattern-loading-user-icon-wrap">
          {/* Glow ring */}
          <div className="pattern-loading-user-ring" aria-hidden="true" />

          <div className="pattern-loading-user-icon">
            <Image
              src={imageSrc}
              alt={imageAlt}
              width={imageSize}
              height={imageSize}
              priority
            />
          </div>
        </div>

        <p className="pattern-loading-user-text">{text}</p>
      </div>
    </div>
  );
}
