import type { Metadata } from "next";
import { ProfileView } from "@/components/app/profile/profile-view";

export const metadata: Metadata = {
  title: "Profile",
  description: "Your records, badges, UMI Clip settings, Premium and privacy controls.",
};

export default function ProfilePage() {
  return <ProfileView />;
}
