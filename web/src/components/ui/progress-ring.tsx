"use client";

interface ProgressRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  className?: string;
}

export function ProgressRing({ percent, size = 64, strokeWidth = 6, className }: ProgressRingProps) {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (percent / 100) * circumference;

  return (
    <div className={className} style={{ width: size, height: size, position: "relative" }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#E5E7EB" strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2} cy={size / 2} r={radius}
          fill="none" stroke="#3B82F6" strokeWidth={strokeWidth}
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-[stroke-dashoffset] duration-500 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-semibold text-text-primary">
        {percent}%
      </div>
    </div>
  );
}
