"use client";

import { cn } from "@/lib/utils";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  fullWidth?: boolean;
}

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const base = "inline-flex items-center justify-center font-medium rounded-lg transition-colors focus:outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-50 disabled:cursor-not-allowed";

  const variants = {
    primary: "bg-primary text-white hover:bg-primary-hover active:bg-blue-700",
    secondary: "bg-gray-100 text-text-primary hover:bg-gray-200 active:bg-gray-300",
    outline: "border border-border text-text-primary hover:bg-gray-50 active:bg-gray-100",
    ghost: "text-text-secondary hover:bg-gray-100 active:bg-gray-200",
    danger: "bg-error text-white hover:bg-red-600 active:bg-red-700",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-xs",
    md: "px-4 py-2 text-sm",
    lg: "px-6 py-3 text-base",
  };

  return (
    <button
      className={cn(base, variants[variant], sizes[size], fullWidth && "w-full", className)}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="animate-spin -ml-1 mr-2 h-4 w-4" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      )}
      {children}
    </button>
  );
}
