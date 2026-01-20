"use client";

import { useState } from "react";
import { EventCalendar } from "@/components/EventCalendar";
import { EventList } from "@/components/EventList";
import { Event } from "@/types/event";

interface EventsViewProps {
  events: Event[];
}

export function EventsView({ events }: EventsViewProps) {
  const [selectedDate, setSelectedDate] = useState<Date | undefined>(new Date());

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
