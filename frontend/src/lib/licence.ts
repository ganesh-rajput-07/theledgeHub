// Installed (desktop) build: sign-in goes through the licence server. Set at build time for the installer.
export const DESKTOP = process.env.NEXT_PUBLIC_LICENCE_MODE === "desktop";
export const SITE_URL = process.env.NEXT_PUBLIC_LICENCE_SITE_URL ?? "";

export type LicenceStatus = {
  mode: "off" | "desktop";
  active: boolean;
  seconds_left?: number;
  firm?: string;
  plan?: string;
  ends_on?: string;
  trial?: boolean;
};
