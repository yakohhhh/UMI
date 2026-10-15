import type { Metadata } from "next";
import { HomeFeed } from "@/components/app/home-feed";

export const metadata: Metadata = { title: "Home" };

export default function AppHomePage() {
  return <HomeFeed />;
}
