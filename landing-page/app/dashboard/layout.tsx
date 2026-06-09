import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — Veriscope",
  description: "Enterprise Regression Intelligence",
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-zinc-950 text-white font-sans antialiased">
      {children}
    </div>
  );
}
