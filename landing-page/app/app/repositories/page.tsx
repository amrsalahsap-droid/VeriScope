import { auth } from "@/auth";
import { redirect } from "next/navigation";
import RepositoriesClientView from "./RepositoriesClientView";

export const dynamic = "force-dynamic";

export default async function RepositoriesPage() {
  const session = await auth();
  if (!session || !session.user) redirect("/login");
  return <RepositoriesClientView />;
}
