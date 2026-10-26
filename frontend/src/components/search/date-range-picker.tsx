"use client";

import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { cn } from "cn";

export function DateRangePicker({
  value,
  onChange,
  disabled,
  className,
  placeholder = "Add dates",
}: {
  value: DateRange | undefined;
  onChange: (range: DateRange | undefined) => void;
  disabled?: (date: Date) => boolean;
  className?: string;
  placeholder?: string;
}) {
  const label =
    value?.from && value?.to
      ? `${format(value.from, "MMM d")} – ${format(value.to, "MMM d")}`
      : value?.from
        ? `${format(value.from, "MMM d")} – …`
        : placeholder;
  return (
    <Popover>
      <PopoverTrigger
        render={
          <Button
            variant="outline"
            className={cn("h-11 w-full justify-start font-normal", !value?.from && "text-muted-foreground", className)}
          />
        }
      >
        <CalendarIcon /> {label}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="range"
          numberOfMonths={2}
          selected={value}
          onSelect={onChange}
          disabled={(d) => d < new Date(new Date().toDateString()) || (disabled?.(d) ?? false)}
          excludeDisabled
        />
      </PopoverContent>
    </Popover>
  );
}

export function isoDate(d: Date | undefined) {
  return d ? format(d, "yyyy-MM-dd") : undefined;
}
