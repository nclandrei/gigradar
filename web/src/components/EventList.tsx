"use client";

import { Event } from "@/types/event";
import { EventCard } from "./EventCard";
import { useMemo } from "react";
import { format } from "date-fns";
import { ro } from "date-fns/locale";

function getDateKey(dateStr: string): string {
  return dateStr.split("T")[0];
}

function dateToKey(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

interface EventListProps {
  events: Event[];
  selectedDate: Date | undefined;
}

export function EventList({ events, selectedDate }: EventListProps) {
  const filteredEvents = useMemo(() => {
    if (!selectedDate) return [];
    const selectedKey = dateToKey(selectedDate);
    
    return events.filter((event) => getDateKey(event.date) === selectedKey);
  }, [events, selectedDate]);

  const formattedDate = selectedDate
    ? format(selectedDate, "EEEE, d MMMM yyyy", { locale: ro })
    : "";

  return (
    <div className="mt-6">
      <h2 className="text-xl font-bold mb-4 capitalize">{formattedDate}</h2>
      
      {filteredEvents.length === 0 ? (
        <div className="rounded-base border-2 border-border bg-secondary-background p-8 text-center shadow-shadow">
          <p className="text-foreground/70">
            Nu sunt evenimente programate pentru această zi.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredEvents.map((event, index) => (
            <EventCard key={`${event.url}-${index}`} event={event} />
          ))}
        </div>
      )}
    </div>
  );
}
