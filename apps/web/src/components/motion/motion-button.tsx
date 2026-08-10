"use client";

import { m, type HTMLMotionProps } from "motion/react";
import { forwardRef } from "react";

/**
 * Tactile motion button — scales slightly on hover/press.
 * Spreads all standard button props onto the motion.button.
 */
export const MotionButton = forwardRef<
  HTMLButtonElement,
  HTMLMotionProps<"button">
>(function MotionButton({ children, ...props }, ref) {
  return (
    <m.button
      ref={ref}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: "spring", stiffness: 400, damping: 25 }}
      {...props}
    >
      {children}
    </m.button>
  );
});
