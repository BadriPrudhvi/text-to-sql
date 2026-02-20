import { cn } from "@/lib/utils";

export function QueryTypeBadge({ queryType }: { queryType: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-medium tracking-wide uppercase",
        queryType === "analytical"
          ? "border-amber-200/60 bg-amber-50 text-amber-600"
          : "border-border bg-muted text-muted-foreground"
      )}
    >
      {queryType}
    </span>
  );
}
