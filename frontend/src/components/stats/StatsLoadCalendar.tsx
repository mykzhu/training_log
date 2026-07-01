import {
  ChartCard,
  ChartInsight,
} from "./StatsChartScaffold";

type LoadCalendarDay = {
  date: string;
  day: number;
  has_workout: boolean;
  count: number;
  value: number | null;
  workout_id: number | null;
};

type LoadCalendarWeek = {
  month_label: string;
  days: LoadCalendarDay[];
};

export type LoadCalendar = {
  weeks: LoadCalendarWeek[];
};

type LoadCalendarLevel =
  | "rest"
  | "light"
  | "medium"
  | "hard"
  | "very-hard";

type StatsLoadCalendarProps = {
  loadCalendar?: LoadCalendar;
  onOpenWorkout: (workoutId: number) => void;
};

function formatNumber(value: number | null | undefined, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "—";
  }

  return Number(value).toFixed(digits);
}

function loadCalendarLevel(
  day: LoadCalendarDay,
): LoadCalendarLevel {
  if (!day.has_workout || day.value === null) {
    return "rest";
  }

  if (day.value < 4) {
    return "light";
  }

  if (day.value < 8) {
    return "medium";
  }

  if (day.value < 14) {
    return "hard";
  }

  return "very-hard";
}

function loadCalendarDescription(day: LoadCalendarDay) {
  if (!day.has_workout) {
    return `${day.date} · rest day`;
  }

  const score =
    day.value === null
      ? "unknown load"
      : `load ${formatNumber(day.value, 1)}`;

  const workoutText =
    day.count === 1
      ? "1 workout"
      : `${day.count} workouts`;

  return `${day.date} · ${score} · ${workoutText}`;
}

export default function StatsLoadCalendar({
  loadCalendar,
  onOpenWorkout,
}: StatsLoadCalendarProps) {
  return (
    <ChartCard
      wide
      subtitle="Daily distribution of calculated session load"
      title="Load calendar"
    >
      {loadCalendar?.weeks.length ? (
        <>
          <div className="load-calendar-scroll">
            <div className="load-calendar-shell">
              <div />

              <div
                className="load-calendar-months"
                style={{
                  gridTemplateColumns: `repeat(${loadCalendar.weeks.length}, 16px)`,
                }}
              >
                {loadCalendar.weeks.map((week, weekIndex) => (
                  <span
                    className="load-calendar-month"
                    key={`month-${weekIndex}`}
                  >
                    {week.month_label}
                  </span>
                ))}
              </div>

              <div
                aria-hidden="true"
                className="load-calendar-weekdays"
              >
                <span>Mon</span>
                <span />
                <span>Wed</span>
                <span />
                <span>Fri</span>
                <span />
                <span>Sun</span>
              </div>

              <div className="load-calendar-weeks">
                {loadCalendar.weeks.map((week, weekIndex) => (
                  <div
                    className="load-calendar-week"
                    key={`week-${weekIndex}`}
                  >
                    {week.days.map((day) => {
                      const level = loadCalendarLevel(day);
                      const description =
                        loadCalendarDescription(day);

                      if (
                        day.has_workout &&
                        day.workout_id !== null
                      ) {
                        return (
                          <button
                            aria-label={`${description}. Open workout.`}
                            className={
                              `load-calendar-cell ` +
                              `load-calendar-cell-${level}`
                            }
                            key={day.date}
                            onClick={() =>
                              onOpenWorkout(day.workout_id!)
                            }
                            title={description}
                            type="button"
                          />
                        );
                      }

                      return (
                        <span
                          aria-label={description}
                          className={
                            `load-calendar-cell ` +
                            `load-calendar-cell-${level}`
                          }
                          key={day.date}
                          role="img"
                          title={description}
                        />
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div
            aria-label="Load calendar legend"
            className="load-calendar-legend"
          >
            <div>
              <span className="load-calendar-legend-cell load-calendar-cell-rest" />
              <span>Rest</span>
            </div>

            <div>
              <span className="load-calendar-legend-cell load-calendar-cell-light" />
              <span>Light · &lt;4</span>
            </div>

            <div>
              <span className="load-calendar-legend-cell load-calendar-cell-medium" />
              <span>Medium · 4–&lt;8</span>
            </div>

            <div>
              <span className="load-calendar-legend-cell load-calendar-cell-hard" />
              <span>Hard · 8–&lt;14</span>
            </div>

            <div>
              <span className="load-calendar-legend-cell load-calendar-cell-very-hard" />
              <span>Very hard · 14+</span>
            </div>
          </div>

          <ChartInsight
            question="How are demanding workouts distributed over time?"
            explanation="Each square represents one calendar day. Warmer colors indicate a higher calculated session load."
          >
            <div className="chart-insight-details">
              <span>
                Isolated hard days followed by rest or lighter sessions usually
                show better load spacing.
              </span>

              <span>
                Several orange or red squares close together indicate a cluster of
                demanding sessions that may require more recovery.
              </span>

              <span>
                Dark squares are days without a workout. They do not indicate
                missing data.
              </span>

              <span>
                Select a colored square to open that workout and inspect which
                exercises, set intensities, and RPE contributed to its score.
              </span>
            </div>

            <p className="chart-insight-footnote">
              Load is a personalized app score based on exercise type, repetition
              range, relative intensity, and session RPE. The calendar helps reveal
              scheduling patterns; it does not directly measure whether you have
              recovered.
            </p>
          </ChartInsight>
        </>
      ) : (
        <div className="empty">
          No load calendar data.
        </div>
      )}
    </ChartCard>
  );
}
