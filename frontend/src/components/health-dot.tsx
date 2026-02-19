"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export function HealthDot() {
  const [healthy, setHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      getHealth()
        .then(() => !cancelled && setHealthy(true))
        .catch(() => !cancelled && setHealthy(false));
    };
    check();
    const interval = setInterval(check, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          className={cn(
            "h-2.5 w-2.5 rounded-full",
            healthy === null && "bg-muted-foreground",
            healthy === true && "bg-emerald-500",
            healthy === false && "bg-red-500"
          )}
        />
      </TooltipTrigger>
      <TooltipContent>
        {healthy === null
          ? "Checking backend..."
          : healthy
          ? "Backend connected"
          : "Backend unreachable"}
      </TooltipContent>
    </Tooltip>
  );
}
