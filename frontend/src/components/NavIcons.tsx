// Inline SVG nav icons - Lucide-style 24×24 stroke icons (MIT).
// No external dep. `currentColor` so they pick up the row's text color.
import type { SVGProps } from "react";

const base: SVGProps<SVGSVGElement> = {
  width: 22,
  height: 22,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function HomeIcon(props: SVGProps<SVGSVGElement>) {
  // Flaticon UICONS "house-chimney" (Regular Rounded) - user's icon-manager pick.
  return (
    <svg width={22} height={22} viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M20.33 6.8V3.67Q20.33 3.33 20.1 3.07Q19.87 2.8 19.5 2.8Q19.13 2.8 18.9 3.07Q18.67 3.33 18.67 3.67V5.67L14.33 2.73Q13.27 2 12 2Q10.73 2 9.67 2.73L3.87 6.67Q3 7.2 2.5 8.13Q2 9.07 2 10.13V17.8Q2 18.93 2.57 19.9Q3.13 20.87 4.1 21.43Q5.07 22 6.2 22H8.67Q9 22 9.27 21.77Q9.53 21.53 9.53 21.13V14.47Q9.53 14.13 9.77 13.9Q10 13.67 10.33 13.67H13.67Q14 13.67 14.23 13.9Q14.47 14.13 14.47 14.53V21.13Q14.53 21.53 14.77 21.77Q15 22 15.33 22H17.87Q18.93 22 19.9 21.43Q20.87 20.87 21.43 19.9Q22 18.93 22 17.8V10.13Q22 9.13 21.57 8.23Q21.13 7.33 20.33 6.8ZM20.33 17.8Q20.33 18.87 19.6 19.6Q18.87 20.33 17.8 20.33H16.2V14.47Q16.13 13.47 15.43 12.73Q14.73 12 13.67 12H10.33Q9.27 12 8.53 12.73Q7.8 13.47 7.8 14.47V20.33H6.2Q5.13 20.33 4.4 19.6Q3.67 18.87 3.67 17.8V10.13Q3.67 9.47 3.97 8.93Q4.27 8.4 4.8 8L10.6 4.07Q11.27 3.67 12 3.67Q12.73 3.67 13.4 4.07L19.2 8Q19.73 8.4 20.03 8.93Q20.33 9.47 20.33 10.13Z" />
    </svg>
  );
}

export function LibraryIcon(props: SVGProps<SVGSVGElement>) {
  // Lucide "gamepad-2" - a balanced controller that FILLS the 24×24 box (y 5→19)
  // instead of the old short/wide pad that read squished/low at 20px. D-pad +
  // two face buttons, proper grip shoulders.
  return (
    <svg {...base} {...props}>
      <line x1="6" y1="11" x2="10" y2="11" />
      <line x1="8" y1="9" x2="8" y2="13" />
      <line x1="15" y1="12" x2="15.01" y2="12" />
      <line x1="18" y1="10" x2="18.01" y2="10" />
      <path d="M17.32 5H6.68a4 4 0 0 0-3.978 3.59c-.006.052-.01.101-.017.152C2.604 9.416 2 14.456 2 16a3 3 0 0 0 3 3c1 0 1.5-.5 2-1l1.414-1.414A2 2 0 0 1 9.828 16h4.344a2 2 0 0 1 1.414.586L17 18c.5.5 1 1 2 1a3 3 0 0 0 3-3c0-1.544-.604-6.584-.685-7.258A4 4 0 0 0 17.32 5z" />
    </svg>
  );
}

export function DownloadsIcon(props: SVGProps<SVGSVGElement>) {
  // Flaticon UICONS "download" (Regular Rounded) - user's icon-manager pick.
  return (
    <svg width={22} height={22} viewBox="0 0 24 24" fill="currentColor" {...props}>
      <path d="M10.2 17.13Q10.93 17.87 12 17.87Q13.07 17.87 13.8 17.13L16.47 14.4Q16.67 14.2 16.67 13.87Q16.67 13.53 16.43 13.3Q16.2 13.07 15.87 13.03Q15.53 13 15.27 13.27L12.8 15.67L12.87 2.8Q12.87 2.47 12.6 2.23Q12.33 2 12 2Q11.67 2 11.4 2.23Q11.13 2.47 11.13 2.8V15.67L8.73 13.27Q8.47 13 8.13 13Q7.8 13 7.57 13.23Q7.33 13.47 7.33 13.83Q7.33 14.2 7.53 14.4ZM21.2 15.33Q20.8 15.33 20.57 15.57Q20.33 15.8 20.33 16.2V19.47Q20.33 19.87 20.1 20.1Q19.87 20.33 19.53 20.33H4.53Q4.13 20.33 3.9 20.1Q3.67 19.87 3.67 19.47V16.13Q3.67 15.8 3.43 15.57Q3.2 15.33 2.87 15.33Q2.47 15.33 2.23 15.57Q2 15.8 2 16.2V19.47Q2 20.53 2.73 21.27Q3.47 22 4.47 22H19.53Q20.53 22 21.27 21.27Q22 20.53 22 19.47V16.13Q22 15.8 21.77 15.57Q21.53 15.33 21.2 15.33Z" />
    </svg>
  );
}

export function FolderIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
    </svg>
  );
}

export function AppsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <rect x="3"  y="3"  width="7" height="7" rx="1.5" />
      <rect x="14" y="3"  width="7" height="7" rx="1.5" />
      <rect x="3"  y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

export function UserIcon(props: SVGProps<SVGSVGElement>) {
  // Clean person silhouette - the default profile avatar when signed out / no pic.
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="8.5" r="3.75" />
      <path d="M4.5 20a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

export function SettingsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  );
}
