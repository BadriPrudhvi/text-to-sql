"use client";

import { useState } from "react";
import { motion } from "motion/react";
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getPaginationRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowUpDown, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { exportCSV, exportJSON } from "@/lib/export";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface DataTableProps {
  data: Record<string, unknown>[];
}

const columnHelper = createColumnHelper<Record<string, unknown>>();

export function DataTable({ data }: DataTableProps) {
  const [sorting, setSorting] = useState<SortingState>([]);

  if (!data || data.length === 0) return null;

  const keys = Object.keys(data[0]);
  const columns = keys.map((key) =>
    columnHelper.accessor(key, {
      header: key,
      cell: (info) => {
        const val = info.getValue();
        if (val === null || val === undefined) {
          return <span className="text-muted-foreground italic">null</span>;
        }
        return String(val);
      },
    })
  );

  return (
    <DataTableInner
      data={data}
      columns={columns}
      sorting={sorting}
      onSortingChange={setSorting}
    />
  );
}

function DataTableInner({
  data,
  columns,
  sorting,
  onSortingChange,
}: {
  data: Record<string, unknown>[];
  columns: ReturnType<typeof columnHelper.accessor>[];
  sorting: SortingState;
  onSortingChange: (s: SortingState) => void;
}) {
  const table = useReactTable({
    data,
    columns,
    state: { sorting },
    onSortingChange: onSortingChange as never,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 10 } },
  });

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-center gap-2 mb-2">
        <Badge variant="secondary" className="text-xs">
          {data.length} row{data.length !== 1 ? "s" : ""}
        </Badge>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => exportCSV(data)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Download as CSV"
          >
            <Download className="h-3 w-3" />
            CSV
          </button>
          <button
            onClick={() => exportJSON(data)}
            className="flex items-center gap-1 rounded-md px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Download as JSON"
          >
            <Download className="h-3 w-3" />
            JSON
          </button>
        </div>
      </div>
      <div className="rounded-md border overflow-x-auto transition-colors hover:border-foreground/15">
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <TableHead
                    key={header.id}
                    className="cursor-pointer select-none whitespace-nowrap"
                    onClick={header.column.getToggleSortingHandler()}
                  >
                    <div className="flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      <ArrowUpDown className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </TableHead>
                ))}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {table.getRowModel().rows.map((row) => (
              <TableRow key={row.id} className="hover:bg-muted/50 transition-colors">
                {row.getVisibleCells().map((cell) => (
                  <TableCell key={cell.id} className="whitespace-nowrap">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
      {table.getPageCount() > 1 && (
        <div className="flex items-center justify-between mt-2">
          <p className="text-xs text-muted-foreground">
            Page {table.getState().pagination.pageIndex + 1} of{" "}
            {table.getPageCount()}
          </p>
          <div className="flex gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => table.previousPage()}
              disabled={!table.getCanPreviousPage()}
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={() => table.nextPage()}
              disabled={!table.getCanNextPage()}
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}
    </motion.div>
  );
}
