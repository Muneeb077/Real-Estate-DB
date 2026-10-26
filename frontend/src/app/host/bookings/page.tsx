"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { PageTitle } from "@/components/auth/require-auth";
import { HostShell } from "@/components/host/host-shell";
import { StatusBadge } from "@/components/status-badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { api } from "@/lib/api";
import { money, shortDate } from "@/lib/format";

type Row = {
  public_id: string;
  check_in: string;
  check_out: string;
  nights: number;
  guests: number;
  total_price: number;
  currency: string;
  status: string;
  listing_title: string;
  guest_name: string;
};

export default function HostBookingsPage() {
  const { data = [], isLoading } = useQuery({ queryKey: ["host-bookings"], queryFn: () => api<Row[]>("/host/bookings") });
  return (
    <HostShell>
      <PageTitle title="Bookings" description="Confirmed, completed and cancelled stays across your listings." />
      {isLoading ? (
        <div className="h-64 animate-pulse rounded-xl bg-muted" />
      ) : (
        <div className="overflow-x-auto rounded-xl border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Guest</TableHead>
                <TableHead>Listing</TableHead>
                <TableHead>Dates</TableHead>
                <TableHead className="text-right">Guests</TableHead>
                <TableHead className="text-right">Total</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((b) => (
                <TableRow key={b.public_id}>
                  <TableCell>
                    <Link href={`/trips/${b.public_id}`} className="font-medium hover:underline">
                      {b.guest_name}
                    </Link>
                  </TableCell>
                  <TableCell className="max-w-56 truncate">{b.listing_title}</TableCell>
                  <TableCell className="whitespace-nowrap">
                    {shortDate(b.check_in)} → {shortDate(b.check_out)}
                  </TableCell>
                  <TableCell className="text-right">{b.guests}</TableCell>
                  <TableCell className="text-right tabular-nums">{money(b.total_price, b.currency)}</TableCell>
                  <TableCell>
                    <StatusBadge status={b.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}
    </HostShell>
  );
}
