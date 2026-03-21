import { cn } from "@/lib/utils";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  padding?: boolean;
}

export function Card({ children, className, padding = true, ...props }: CardProps) {
  return (
    <div
      className={cn("bg-card rounded-xl border border-border shadow-sm", padding && "p-5 md:p-6", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardTitle({ children, className }: { children: React.ReactNode; className?: string }) {
  return <h3 className={cn("text-lg font-semibold text-text-primary mb-3", className)}>{children}</h3>;
}

export function CardDivider() {
  return <hr className="border-border-light my-4" />;
}
