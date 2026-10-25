import { Badge } from "@/components/ui/badge";
import { cn } from "cn";

const TONE: Record<string, string> = {
  pending: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  requested: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  pending_review: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  accepted: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  confirmed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  published: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  completed: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  verified: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  active: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  sold: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
  rented: "bg-sky-500/15 text-sky-700 dark:text-sky-300",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant="secondary" className={cn("capitalize", TONE[status] ?? "text-muted-foreground")}>
      {status.replaceAll("_", " ")}
    </Badge>
  );
}
