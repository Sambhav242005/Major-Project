"use client";

import { AnimatePresence, m } from "motion/react";
import type { ReactNode } from "react";

/**
 * Reordering list with layout animations. Pass a stable `items` array of
 * { id } and a render function; items animate into place on add/remove/reorder.
 */
export function AnimatedList<T extends { id: string }>({
  items,
  render,
  className,
}: {
  items: T[];
  render: (item: T) => ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <AnimatePresence initial={false}>
        {items.map((item) => (
          <m.div
            key={item.id}
            layout
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
          >
            {render(item)}
          </m.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
