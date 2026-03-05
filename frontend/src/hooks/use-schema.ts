"use client";

import { useEffect, useState } from "react";
import { getSchema } from "@/lib/api";

export interface SchemaTable {
  name: string;
  description: string | null;
  columns: { name: string; type: string }[];
}

export function useSchema() {
  const [tables, setTables] = useState<SchemaTable[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);

    getSchema()
      .then((res) => {
        if (!cancelled) setTables(res.tables);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return { tables, isLoading, error };
}
