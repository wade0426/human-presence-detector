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

        # Pause support (FR-2)
        # ─────────────────────────────────────────────────────────────────────
        # Freeze contract:
        #   pause(now) : sets _paused=True, records _state_before_pause.
        #                Does NOT update _last_t or _work_elapsed — all
        #                elapsed counters remain frozen at the values they
        #                held when pause() was called.
        #   update()   : returns [] immediately while _paused, so no dt is
        #                ever accumulated during the suspended interval.
        #   resume(now): sets _paused=False and resets _last_t = now.
        #                The next update() sees (now - _last_t) ≈ 0, so no
        #                "phantom" time is credited for the pause duration.
        # ─────────────────────────────────────────────────────────────────────
        self._paused: bool = False
        self._state_before_pause: TimerState = TimerState.IDLE

    @property
    def state(self) -> TimerState:
        if self._paused:
            return TimerState.SUSPENDED
        return self._state

    def update(self, present: bool, now: float) -> list[TimerEvent]:
        # FR-2: While paused, all counters are frozen — return immediately.
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
                # FR-4: Direct absence from REMINDING → start rest.
                # Emit WORK_ENDED before REST_STARTED (work session ends here).
                events.append(
                    self._event(
                        TimerEventType.WORK_ENDED,
                        now,
                        duration_sec=self._work_elapsed,
                        ended_by="rest",
                    )
                )
                self._work_elapsed = 0.0  # reset so RESTING snapshot shows 0
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
        """Transition from REMINDING to RESTING (user manually starts rest).

        FR-4: Emits WORK_ENDED (ended_by='rest') before REST_STARTED so that
        the work session is properly closed regardless of how rest is initiated.
        """
        if self._state != TimerState.REMINDING:
            return []
        # FR-4: Close the work session before entering rest.
        work_ended = self._event(
            TimerEventType.WORK_ENDED,
            now,
            duration_sec=self._work_elapsed,
            ended_by="rest",
        )
        self._work_elapsed = 0.0  # reset so RESTING snapshot shows 0
        self._state = TimerState.RESTING
        self._rest_started_at = now
        self._rest_accumulated = 0.0
        self._reminder_last_t = None
        self._last_t = now
        return [work_ended, self._event(TimerEventType.REST_STARTED, now)]

    def confirm_return(self, now: float) -> list[TimerEvent]:
        """Transition from AWAITING_RETURN to WORKING (user confirms they're back).

        NOTE: WORK_ENDED was already emitted when the rest session began
        (in start_rest() or via absence from REMINDING). This method does NOT
        emit WORK_ENDED again.
        """
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
        """Suspend the timer, freezing all elapsed counters.

        FR-2 freeze contract: records current _state, sets _paused=True.
        _last_t and _work_elapsed are intentionally NOT updated here so that
        no phantom time is added during the suspension period.
        """
        if not self._paused:
            self._state_before_pause = self._state
            self._paused = True
            # Deliberately do NOT update _last_t here — this ensures _last_t
            # stays at whatever value it was before the pause, and the next
            # update() after resume() will see dt ≈ 0 (because resume() resets
            # _last_t = now).

    def resume(self, now: float) -> None:
        """Resume the timer from suspended state, resetting the time baseline.

        FR-2 freeze contract: sets _paused=False and resets _last_t = now so
        that the next update() call computes dt = (new_now - now) ≈ 0,
        preventing any back-attribution of time during the pause interval.
        """
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

        # FR-1: overtime_sec — only meaningful in REMINDING state.
        # In SUSPENDED state _work_elapsed is frozen (pause contract), so
        # overtime_sec is implicitly frozen too (computed from frozen value).
        overtime_sec = (
            max(0.0, self._work_elapsed - self._work_threshold_sec)
            if self._state == TimerState.REMINDING
            else 0.0
        )

        return TimerSnapshot(
            state=state,
            work_elapsed_sec=self._work_elapsed,
            away_elapsed_sec=away_elapsed,
            remaining_to_reminder_sec=remaining,
            reminder_active=self._state == TimerState.REMINDING,
            rest_remaining_sec=rest_remaining,
            rest_elapsed_sec=rest_elapsed,
            overtime_sec=overtime_sec,
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
