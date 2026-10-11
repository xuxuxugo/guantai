"use client";

import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1c1915] focus-visible:ring-offset-2 focus-visible:ring-offset-[#f3efe6] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-[#1c1915] text-[#f6f1e7] hover:bg-[#322c24]",
        light: "bg-[#f6f1e7] text-[#1c1915] hover:bg-white",
        outline: "border border-[#d9d0c1] bg-[#fbf8f2] text-[#1c1915] hover:bg-[#f3efe6]",
        ghost: "text-[#1c1915] hover:bg-[#ebe4d6]",
        danger: "border border-[#e7c4bc] bg-[#fdf6f4] text-[#9d3428] hover:bg-[#f8e6e1]",
      },
      size: {
        default: "h-9 px-3.5",
        sm: "h-8 px-2.5 text-xs",
        lg: "h-10 px-5",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  },
);

export function Button({
  className,
  variant,
  size,
  asChild = false,
  type,
  ...props
}: ComponentProps<"button"> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const classes = cn(buttonVariants({ variant, size }), className);
  if (asChild) {
    return <Slot className={classes} {...props} />;
  }
  return <button className={classes} type={type ?? "button"} {...props} />;
}
