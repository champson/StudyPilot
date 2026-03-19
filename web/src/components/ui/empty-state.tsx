import { Button } from "./button";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  actionLabel?: string;
  onAction?: () => void;
}

export function EmptyState({ icon = "📭", title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <span className="text-5xl mb-4">{icon}</span>
      <h3 className="text-lg font-medium text-text-primary mb-2">{title}</h3>
      {description && <p className="text-sm text-text-secondary mb-4 max-w-md">{description}</p>}
      {actionLabel && onAction && (
        <Button variant="primary" onClick={onAction}>{actionLabel}</Button>
      )}
    </div>
  );
}
