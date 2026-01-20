"use client";

import { useState, useEffect } from "react";
import { EventCalendar } from "@/components/EventCalendar";
import { EventList } from "@/components/EventList";
import { Event } from "@/types/event";

interface EventsViewProps {
  events: Event[];
  initialDate: string;
}

export function EventsView({ events, initialDate }: EventsViewProps) {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(() => new Date(initialDate));

  return (
    <>
      <EventCalendar
        events={events}
        selectedDate={selectedDate}
        onSelectDate={setSelectedDate}
      />
      <EventList events={events} selectedDate={selectedDate} />
    </>
  );
}
