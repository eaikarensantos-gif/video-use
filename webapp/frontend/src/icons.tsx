// Small inline SVG icon set — keeps the UI crisp without an icon-font
// dependency. Each icon is 1em square by default so it inherits font-size.

type IconProps = { size?: number };

const base = (size: number) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export function IconPlay({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)} fill="currentColor" stroke="none">
      <path d="M7 4.5v15l13-7.5-13-7.5z" />
    </svg>
  );
}

export function IconPause({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)} fill="currentColor" stroke="none">
      <rect x="6" y="4.5" width="4.5" height="15" rx="1" />
      <rect x="13.5" y="4.5" width="4.5" height="15" rx="1" />
    </svg>
  );
}

export function IconSkipBack({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)} fill="currentColor" stroke="none">
      <rect x="5" y="4.5" width="2.4" height="15" rx="0.8" />
      <path d="M19 5v14l-11-7 11-7z" />
    </svg>
  );
}

export function IconUndo({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M9 8 4 12l5 4" />
      <path d="M4 12h11a5 5 0 0 1 0 10h-1" />
    </svg>
  );
}

export function IconRedo({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M15 8l5 4-5 4" />
      <path d="M20 12H9a5 5 0 0 0 0 10h1" />
    </svg>
  );
}

export function IconScissors({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <circle cx="6" cy="6" r="2.6" />
      <circle cx="6" cy="18" r="2.6" />
      <path d="M8.2 7.6 20 18" />
      <path d="M20 6 8.2 16.4" />
    </svg>
  );
}

export function IconExport({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 15V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

export function IconTrash({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M4 7h16" />
      <path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" />
      <path d="M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13" />
      <path d="M10 11v6M14 11v6" />
    </svg>
  );
}

export function IconVideo({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <rect x="2.5" y="6" width="13" height="12" rx="2" />
      <path d="M15.5 10.2 21 7v10l-5.5-3.2" />
    </svg>
  );
}

export function IconText({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M5 6h14" />
      <path d="M12 6v13" />
      <path d="M9 19h6" />
    </svg>
  );
}

export function IconSparkle({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)} fill="currentColor" stroke="none">
      <path d="M11 3l1.6 5.4L18 10l-5.4 1.6L11 17l-1.6-5.4L4 10l5.4-1.6L11 3z" />
      <path d="M18.5 15l.7 2.3 2.3.7-2.3.7-.7 2.3-.7-2.3-2.3-.7 2.3-.7.7-2.3z" />
    </svg>
  );
}

export function IconMusic({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M9 18V5l11-2v13" />
      <circle cx="6" cy="18" r="3" />
      <circle cx="17" cy="16" r="3" />
    </svg>
  );
}

export function IconUpload({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 16V6" />
      <path d="M7 11l5-5 5 5" />
      <path d="M4 18v1a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-1" />
    </svg>
  );
}

export function IconPlus({ size = 16 }: IconProps) {
  return (
    <svg {...base(size)}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export function IconLogo({ size = 20 }: IconProps) {
  // A simple play-triangle-in-frame mark — the app's brand icon.
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <rect x="2" y="2" width="20" height="20" rx="6" fill="url(#vu-logo-grad)" />
      <path d="M9.5 7.5v9l7-4.5-7-4.5z" fill="white" />
      <defs>
        <linearGradient id="vu-logo-grad" x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop stopColor="#7f9bff" />
          <stop offset="1" stopColor="#5a6cff" />
        </linearGradient>
      </defs>
    </svg>
  );
}
