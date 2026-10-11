import { AgentDesk } from "@/components/research";

export default async function Page({ searchParams }: { searchParams: Promise<{ code?: string }> }) {
  const params = await searchParams;
  return <AgentDesk initialCode={params.code || "600519"} />;
}
