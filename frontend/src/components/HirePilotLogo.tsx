interface LogoProps {
  size?: number;
  className?: string;
}

export function HirePilotLogo({ size = 32, className = "" }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 120 120"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
    >
      {/* Rounded square background */}
      <defs>
        <linearGradient id="bgGrad" x1="0" y1="0" x2="120" y2="120" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#5B8DEF" />
          <stop offset="100%" stopColor="#3B6DD6" />
        </linearGradient>
        <linearGradient id="capGrad" x1="30" y1="28" x2="90" y2="62" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1E3A6E" />
          <stop offset="100%" stopColor="#152C54" />
        </linearGradient>
      </defs>

      <rect x="4" y="4" width="112" height="112" rx="24" fill="url(#bgGrad)" />

      {/* Pilot cap — brim */}
      <ellipse cx="60" cy="52" rx="32" ry="8" fill="url(#capGrad)" />

      {/* Pilot cap — dome */}
      <path
        d="M34 52 C34 52 36 28 60 28 C84 28 86 52 86 52"
        fill="url(#capGrad)"
      />

      {/* Cap band */}
      <rect x="36" y="44" width="48" height="6" rx="3" fill="#2A4D8E" />

      {/* Wings emblem — left wing */}
      <path
        d="M60 47 C54 44 40 42 30 44 C38 40 52 40 60 44Z"
        fill="#D4DFF7"
        opacity="0.9"
      />
      {/* Wings emblem — right wing */}
      <path
        d="M60 47 C66 44 80 42 90 44 C82 40 68 40 60 44Z"
        fill="#D4DFF7"
        opacity="0.9"
      />
      {/* Wings center dot */}
      <circle cx="60" cy="44" r="3" fill="white" />

      {/* Checkmark */}
      <path
        d="M42 78 L54 90 L80 64"
        stroke="white"
        strokeWidth="8"
        strokeLinecap="round"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  );
}
