"""Calendly integration package for Lipaira.

Provides skills for interacting with Calendly scheduling:
- CalendlyGetScheduledEventsSkill: Fetch upcoming scheduled events
- CalendlyGetEventTypesSkill: Retrieve available event types and booking links

Key functions/classes:
    CalendlyGetScheduledEventsSkill: Lists active/confirmed Calendly events
    CalendlyGetEventTypesSkill: Returns event type names, durations, booking URLs
"""

from skills.calendly.scheduling import CalendlyGetScheduledEventsSkill, CalendlyGetEventTypesSkill
__all__ = ["CalendlyGetScheduledEventsSkill", "CalendlyGetEventTypesSkill"]
