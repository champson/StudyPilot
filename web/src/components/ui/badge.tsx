import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "primary" | "success" | "warning" | "error";
  className?: string;
}

export function Badge({ children, variant = "default", className }: BadgeProps) {
  const variants = {
    default: "bg-gray-100 text-text-secondary",
    primary: "bg-primary-light text-primary",
    success: "bg-success-light text-success",
    warning: "bg-warning-light text-warning",
    error: "bg-error-light text-error",
  };

  return (
    <span className={cn("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium", variants[variant], className)}>
      {children}
    </span>
  );
}
