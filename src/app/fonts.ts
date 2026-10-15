import localFont from "next/font/local";

/** Space Grotesk — titles and large figures (tabular numbers via `font-num`). */
export const grotesk = localFont({
  src: "./fonts/SpaceGrotesk-Variable.woff2",
  variable: "--font-grotesk",
  weight: "300 700",
  display: "swap",
});

/** IBM Plex Sans — body copy. */
export const plex = localFont({
  src: "./fonts/IBMPlexSans-Variable.woff2",
  variable: "--font-plex",
  weight: "100 700",
  display: "swap",
});

/** IBM Plex Mono — small metrics and technical labels. */
export const plexMono = localFont({
  src: [
    { path: "./fonts/IBMPlexMono-400.woff2", weight: "400", style: "normal" },
    { path: "./fonts/IBMPlexMono-500.woff2", weight: "500", style: "normal" },
    { path: "./fonts/IBMPlexMono-600.woff2", weight: "600", style: "normal" },
  ],
  variable: "--font-plex-mono",
  display: "swap",
});
