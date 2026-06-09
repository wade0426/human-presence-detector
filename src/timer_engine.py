from __future__ import annotations

from src.types import ResetMode, TimerEvent, TimerEventType, TimerSnapshot, TimerState


class TimerEngine:
    def __init__(
        self,
        work_threshold_sec: float,
        reset_threshold_sec: float,
        required_rest_sec: float,
        reset_mode: ResetMode,
        repeat_interval_sec: float,
        snooze_sec: float,
    ) -> None:
        self._work_threshold_sec = work_threshold_sec
        self._reset_threshold_sec = reset_threshold_sec
        self._required_rest_sec = required_rest_sec
        self._reset_mode = reset_mode
        self._repeat_interval_sec = repeat_interval_sec
        self._snooze_sec = snooze_sec

        self._state = TimerState.IDLE
        self._work_elapsed = 0.0
        self._last_t: float | None = None
        self._away_since: float | None = None
        self._rest_start_t: float | None = None
        self._work_start_t: float | None = None
        self._reminder_last_t: float | None = None
        self._snooze_until: float | None = None

    @property
    def state(self) -> TimerState:
        return self._state

    def update(self, present: bool, now: float) -> list[TimerEvent]:
        events: list[TimerEvent] = []
        dt = 0.0 if self._last_t is None else max(0.0, now - self._last_t)
        self._last_t = now

        if self._state == TimerState.IDLE:
            if present:
                if self._rest_start_t is not None:
                    events.append(
                        self._event(
                            TimerEventType.REST_ENDED,
                            now,
                            duration_sec=now - self._rest_start_t,
                        )
                    )
                    self._rest_start_t = None
                self._state = TimerState.WORKING
                self._work_elapsed = 0.0
                self._work_start_t = now
                events.append(self._event(TimerEventType.WORK_STARTED, now))

        elif self._state == TimerState.WORKING:
            if present:
                self._work_elapsed += dt
                if self._work_elapsed >= self._work_threshold_sec:
                    self._state = TimerState.REMINDING
                    self._reminder_last_t = now
                    self._away_since = None
                    self._snooze_until = None
                    events.append(self._event(TimerEventType.REMINDER_TRIGGERED, now))
            else:
                self._state = TimerState.PAUSED
                self._away_since = now

        elif self._state == TimerState.PAUSED:
            if present:
                self._state = TimerState.WORKING
                self._away_since = None
            elif (
                self._away_since is not None
                and (now - self._away_since) >= self._reset_threshold_sec
            ):
                events.append(
                    self._event(
                        TimerEventType.WORK_ENDED,
                        now,
                        duration_sec=self._work_elapsed,
                        ended_by="reset",
                    )
                )
                self._rest_start_t = self._away_since
                self._state = TimerState.IDLE
                self._work_elapsed = 0.0
                self._away_since = None
                self._work_start_t = None

        elif self._state == TimerState.REMINDING:
            if present:
                self._work_elapsed += dt
                self._away_since = None
                should_repeat = False
                if self._reset_mode == ResetMode.DETECTION:
                    should_repeat = True
                elif self._reset_mode == ResetMode.SNOOZE:
                    should_repeat = (
                        self._snooze_until is None or now >= self._snooze_until
                    )

                if (
                    should_repeat
                    and self._reminder_last_t is not None
                    and (now - self._reminder_last_t) >= self._repeat_interval_sec
                ):
                    self._reminder_last_t = now
                    events.append(self._event(TimerEventType.REMINDER_REPEATED, now))
            else:
                if self._away_since is None:
                    self._away_since = now
                elif (now - self._away_since) >= self._required_rest_sec:
                    events.append(
                        self._event(
                            TimerEventType.WORK_ENDED,
                            now,
                            duration_sec=self._work_elapsed,
                            ended_by="rest_done",
                        )
                    )
                    self._rest_start_t = self._away_since
                    self._state = TimerState.IDLE
                    self._work_elapsed = 0.0
                    self._away_since = None
                    self._work_start_t = None
                    self._reminder_last_t = None
                    self._snooze_until = None

        return events

    def on_reminder_dismissed(self, now: float) -> list[TimerEvent]:
        if self._state != TimerState.REMINDING:
            return []

        if self._reset_mode == ResetMode.DISMISS:
            finished_duration = self._work_elapsed
            self._state = TimerState.WORKING
            self._work_elapsed = 0.0
            self._work_start_t = now
            self._away_since = None
            self._reminder_last_t = None
            self._snooze_until = None
            return [
                self._event(
                    TimerEventType.WORK_ENDED,
                    now,
                    duration_sec=finished_duration,
                    ended_by="dismiss",
                ),
                self._event(TimerEventType.WORK_STARTED, now),
            ]

        if self._reset_mode == ResetMode.SNOOZE:
            self._snooze_until = now + self._snooze_sec
            self._reminder_last_t = now
            return []

        self._reminder_last_t = now
        return []

    def snapshot(self, now: float) -> TimerSnapshot:
        remaining = (
            max(0.0, self._work_threshold_sec - self._work_elapsed)
            if self._state == TimerState.WORKING
            else 0.0
        )
        away_elapsed = 0.0 if self._away_since is None else now - self._away_since
        return TimerSnapshot(
            state=self._state,
            work_elapsed_sec=self._work_elapsed,
            away_elapsed_sec=away_elapsed,
            remaining_to_reminder_sec=remaining,
            reminder_active=self._state == TimerState.REMINDING,
        )

    def _event(
        self,
        event_type: TimerEventType,
        at: float,
        *,
        duration_sec: float = 0.0,
        ended_by: str = "",
    ) -> TimerEvent:
        return TimerEvent(
            type=event_type,
            at=at,
            duration_sec=duration_sec,
            ended_by=ended_by,
        )
