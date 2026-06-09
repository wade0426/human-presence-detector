from __future__ import annotations

from src.types import (
    RestCountMode,
    TimerEvent,
    TimerEventType,
    TimerSnapshot,
    TimerState,
)


class TimerEngine:
    def __init__(
        self,
        work_threshold_sec: float,
        reset_threshold_sec: float,
        required_rest_sec: float,
        repeat_interval_sec: float,
        rest_count_mode: RestCountMode = RestCountMode.PRESENCE,
    ) -> None:
        self._work_threshold_sec = work_threshold_sec
        self._reset_threshold_sec = reset_threshold_sec
        self._required_rest_sec = required_rest_sec
        self._repeat_interval_sec = repeat_interval_sec
        self._rest_count_mode = rest_count_mode

        self._state = TimerState.IDLE
        self._work_elapsed = 0.0
        self._last_t: float | None = None
        self._away_since: float | None = None
        self._rest_start_t: float | None = None
        self._work_start_t: float | None = None
        self._reminder_last_t: float | None = None

        # Rest tracking
        self._rest_started_at: float | None = None
        self._rest_accumulated: float = 0.0

        # Pause support
        self._paused: bool = False
        self._state_before_pause: TimerState = TimerState.IDLE

    @property
    def state(self) -> TimerState:
        if self._paused:
            return TimerState.SUSPENDED
        return self._state

    def update(self, present: bool, now: float) -> list[TimerEvent]:
        if self._paused:
            return []

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
                    events.append(self._event(TimerEventType.REMINDER_TRIGGERED, now))
            else:
                self._state = TimerState.AWAY
                self._away_since = now

        elif self._state == TimerState.AWAY:
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
                if (
                    self._reminder_last_t is not None
                    and (now - self._reminder_last_t) >= self._repeat_interval_sec
                ):
                    self._reminder_last_t = now
                    events.append(self._event(TimerEventType.REMINDER_REPEATED, now))
            else:
                # Direct absence from REMINDING → start rest
                self._state = TimerState.RESTING
                self._rest_started_at = now
                self._rest_accumulated = 0.0
                self._away_since = None
                self._reminder_last_t = None
                events.append(self._event(TimerEventType.REST_STARTED, now))

        elif self._state == TimerState.RESTING:
            satisfied = False
            if self._rest_count_mode == RestCountMode.PRESENCE:
                if not present:
                    self._rest_accumulated += dt
                satisfied = self._rest_accumulated >= self._required_rest_sec
            else:  # FIXED
                if self._rest_started_at is not None:
                    satisfied = (now - self._rest_started_at) >= self._required_rest_sec

            if satisfied and present:
                self._state = TimerState.AWAITING_RETURN
                events.append(self._event(TimerEventType.RETURN_PROMPT, now))
            # else: stay RESTING (waiting for rest to complete or for return)

        elif self._state == TimerState.AWAITING_RETURN:
            # Do not change state automatically; wait for confirm_return()
            pass

        return events

    def start_rest(self, now: float) -> list[TimerEvent]:
        """Transition from REMINDING to RESTING (user manually starts rest)."""
        if self._state != TimerState.REMINDING:
            return []
        self._state = TimerState.RESTING
        self._rest_started_at = now
        self._rest_accumulated = 0.0
        self._reminder_last_t = None
        self._last_t = now
        return [self._event(TimerEventType.REST_STARTED, now)]

    def confirm_return(self, now: float) -> list[TimerEvent]:
        """Transition from AWAITING_RETURN to WORKING (user confirms they're back)."""
        if self._state != TimerState.AWAITING_RETURN:
            return []
        rest_duration = 0.0
        if self._rest_started_at is not None:
            rest_duration = now - self._rest_started_at
        events: list[TimerEvent] = [
            self._event(TimerEventType.REST_ENDED, now, duration_sec=rest_duration),
            self._event(TimerEventType.WORK_STARTED, now),
        ]
        self._state = TimerState.WORKING
        self._work_elapsed = 0.0
        self._work_start_t = now
        self._last_t = now
        self._rest_started_at = None
        self._rest_accumulated = 0.0
        return events

    def pause(self, now: float) -> None:
        """Suspend the timer, freezing all elapsed counters."""
        if not self._paused:
            self._state_before_pause = self._state
            self._paused = True

    def resume(self, now: float) -> None:
        """Resume the timer from suspended state, resetting the time baseline."""
        if self._paused:
            self._paused = False
            self._last_t = now  # ★ Key: reset baseline so next dt ≈ 0
            self._state = self._state_before_pause

    def snapshot(self, now: float) -> TimerSnapshot:
        state = TimerState.SUSPENDED if self._paused else self._state

        remaining = (
            max(0.0, self._work_threshold_sec - self._work_elapsed)
            if self._state == TimerState.WORKING
            else 0.0
        )
        away_elapsed = 0.0 if self._away_since is None else now - self._away_since

        rest_remaining = 0.0
        rest_elapsed = 0.0

        if self._state == TimerState.RESTING:
            if self._rest_count_mode == RestCountMode.FIXED and self._rest_started_at is not None:
                rest_remaining = max(
                    0.0, self._required_rest_sec - (now - self._rest_started_at)
                )
            elif self._rest_count_mode == RestCountMode.PRESENCE:
                rest_elapsed = self._rest_accumulated

        return TimerSnapshot(
            state=state,
            work_elapsed_sec=self._work_elapsed,
            away_elapsed_sec=away_elapsed,
            remaining_to_reminder_sec=remaining,
            reminder_active=self._state == TimerState.REMINDING,
            rest_remaining_sec=rest_remaining,
            rest_elapsed_sec=rest_elapsed,
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
