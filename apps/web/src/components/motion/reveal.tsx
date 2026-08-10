"use client";

import { m, useInView } from "motion/react";
import { useRef, type ReactNode } from "react";

/**
 * Fade+rise on scroll-into-view. Animates once; respects reduced motion
 * via Motion's built-in `useReducedMotion` (Motion auto-disables transform
 * animations when prefers-reduced-motion is set).
 */
export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });

  return (
    <m.div
      ref={ref}
      className={className}
      initial={{ opacity: 0, y: 24 }}
      animate={inView ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
    >
      {children}
    </m.div>
  );
}
