import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function make(paths: React.ReactNode) {
  return function Icon({ size = 16, ...props }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.8}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        {...props}
      >
        {paths}
      </svg>
    );
  };
}

export const IconPlus = make(<path d="M12 5v14M5 12h14" />);
export const IconSearch = make(
  <>
    <circle cx="11" cy="11" r="7" />
    <path d="m20 20-3.5-3.5" />
  </>,
);
export const IconSend = make(<path d="M5 12h14M13 6l6 6-6 6" />);
export const IconStop = make(<rect x="7" y="7" width="10" height="10" rx="2" fill="currentColor" />);
export const IconSun = make(
  <>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </>,
);
export const IconMoon = make(<path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z" />);
export const IconSidebar = make(
  <>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="M9 4v16" />
  </>,
);
export const IconPanelRight = make(
  <>
    <rect x="3" y="4" width="18" height="16" rx="3" />
    <path d="M15 4v16" />
  </>,
);
export const IconChat = make(<path d="M4 6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4V6Z" />);
export const IconDatabase = make(
  <>
    <ellipse cx="12" cy="5.5" rx="7.5" ry="2.5" />
    <path d="M4.5 5.5v13c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-13M4.5 12c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5" />
  </>,
);
export const IconTable = make(
  <>
    <rect x="3" y="4" width="18" height="16" rx="2.5" />
    <path d="M3 10h18M9 10v10" />
  </>,
);
export const IconKey = make(
  <>
    <circle cx="8" cy="15" r="4" />
    <path d="m11 12 9-9M17 6l2 2M15 8l2 2" />
  </>,
);
export const IconLink = make(<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1" />);
export const IconCopy = make(
  <>
    <rect x="8" y="8" width="12" height="12" rx="2.5" />
    <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
  </>,
);
export const IconCheck = make(<path d="m5 12.5 4.5 4.5L19 7.5" />);
export const IconDownload = make(<path d="M12 4v11M7 10l5 5 5-5M5 20h14" />);
export const IconTrash = make(<path d="M4 7h16M9 7V4.5h6V7M6 7l1 13h10l1-13" />);
export const IconPencil = make(<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4Z" />);
export const IconPin = make(<path d="M9 4h6l-1 6 4 3v2H6v-2l4-3-1-6ZM12 15v6" />);
export const IconRefresh = make(<path d="M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4" />);
export const IconChevron = make(<path d="m9 6 6 6-6 6" />);
export const IconChart = make(<path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />);
export const IconCode = make(<path d="m8 8-4 4 4 4M16 8l4 4-4 4M14 5l-4 14" />);
export const IconInfo = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5M12 8h.01" />
  </>,
);
export const IconSparkles = make(
  <path d="M12 3l1.8 4.7L18.5 9.5l-4.7 1.8L12 16l-1.8-4.7L5.5 9.5l4.7-1.8L12 3ZM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8L19 15ZM5 15l.6 1.4L7 17l-1.4.6L5 19l-.6-1.4L3 17l1.4-.6L5 15Z" />,
);
export const IconBolt = make(<path d="M13 2 4 14h7l-1 8 9-12h-7l1-8Z" />);
export const IconShield = make(<path d="M12 3 5 6v6c0 4.5 3 7.5 7 9 4-1.5 7-4.5 7-9V6l-7-3ZM9 12l2 2 4-4" />);
export const IconWand = make(<path d="m15 4 5 5L9 20l-5-5L15 4ZM13 6l5 5M4 4v3M2.5 5.5h3M19 15v3M17.5 16.5h3" />);
export const IconAlert = make(<path d="M12 4 2.5 20h19L12 4ZM12 10v4M12 17h.01" />);
export const IconClose = make(<path d="M6 6l12 12M18 6 6 18" />);
export const IconCommand = make(<path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3V6Z" />);
export const IconPlay = make(<path d="M7 5v14l11-7L7 5Z" fill="currentColor" />);
export const IconExpand = make(<path d="M14 4h6v6M10 20H4v-6M20 4l-7 7M4 20l7-7" />);
export const IconClock = make(
  <>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </>,
);
export const IconArrowUp = make(<path d="M12 19V5M6 11l6-6 6 6" />);
export const IconFilter = make(<path d="M4 5h16l-6 8v6l-4-2v-4L4 5Z" />);
export const IconSort = make(<path d="M8 4v16M4 16l4 4 4-4M16 20V4M12 8l4-4 4 4" />);

export function Logo({ size = 32 }: { size?: number }) {
  return (
    <div
      className="bg-brand relative grid shrink-0 place-items-center rounded-[30%] text-white shadow-sm"
      style={{ width: size, height: size }}
    >
      <IconDatabase size={size * 0.56} strokeWidth={2.2} />
    </div>
  );
}
