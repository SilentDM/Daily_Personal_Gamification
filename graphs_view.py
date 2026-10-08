"""Graphs: one period filter for everything, KPI tiles vs the previous period, habit heatmap, score trend,
habit ranking, weekday pattern, year map, weekly XP, studies & quests, and a weekly Gemini summary.

Colors follow the data-viz method and were validated against the dark card surface (#36343B):
- sequential (one hue, low -> high): SEQ, used for every score heatmap
- categorical (2 series): SERIES_1 / SERIES_2; diverging poles for net XP: SERIES_1 / NEGATIVE
Text never wears a series color; values and labels use the ink tokens below.
"""
import math
from datetime import date

import flet as ft
import flet_charts as fch

import ai_gemini
import ai_weekly
import analytics as an
from constants import SCORE_PASSING, DAY_NAMES

SEQ = ["#256abf", "#3987e5", "#6da7ec", "#9ec5f4", "#cde2fb"]   # scores 0-2, 2-4, 4-6, 6-8, 8-10
SERIES_1 = "#3987e5"
SERIES_2 = "#d95926"
NEGATIVE = "#e66767"
INK = ft.Colors.WHITE
INK_2 = "#c3c2b7"
MUTED = "#898781"
GRID = ft.Colors.with_opacity(0.08, ft.Colors.WHITE)
EMPTY = ft.Colors.with_opacity(0.05, ft.Colors.WHITE)
REST = "#6b6a66"   # neutral gray: answered "Rest", not a score (never a hue, so it never reads as good/bad)
GOOD, BAD = "#0ca30c", "#d03b3b"
BAR_W = 20


def seq_color(score):
    if score is None:
        return EMPTY
    return SEQ[min(4, max(0, int(score // 2)))]


def fmt_minutes(m: int) -> str:
    h, mm = divmod(int(m), 60)
    return f"{h}h {mm:02d}m" if h else f"{mm} min"


def card(title, subtitle, content, expand=False):
    head = [ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=INK)]
    if subtitle:
        head.append(ft.Text(subtitle, size=12, color=MUTED))
    return ft.Container(content=ft.Column([ft.Column(head, spacing=2), content], spacing=12),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=16, expand=expand)


def scale_legend(prefix="Score"):
    items = [ft.Text(prefix, size=11, color=MUTED)]
    for i, c in enumerate(SEQ):
        items.append(ft.Container(width=14, height=14, bgcolor=c, border_radius=3,
                                  tooltip=f"{i * 2}–{i * 2 + 2}"))
    items += [ft.Text("0 → 10", size=11, color=MUTED), ft.Container(width=10),
              ft.Container(width=14, height=14, bgcolor=EMPTY, border_radius=3,
                           border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.WHITE))),
              ft.Text("no entry", size=11, color=MUTED), ft.Container(width=10),
              ft.Container(width=14, height=14, bgcolor=REST, border_radius=3),
              ft.Text("rest", size=11, color=MUTED)]
    return ft.Row(items, spacing=4)


def axis_labels(values, fmt=str, size=10):
    return [fch.ChartAxisLabel(value=v, label=ft.Text(fmt(v), size=size, color=MUTED)) for v in values]


def nice_step(lo, hi, target=5):
    span = max(hi - lo, 1)
    raw = span / target
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


class GraphsView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False, spacing=14)
        self.app_page = page
        self.period = "30d"
        self.summary_error = ""

    # ------------------------------------------------------------ public (main.py)
    def refresh(self):
        today = date.today()
        key = self.period
        self.controls = [self._header()]
        series = an.score_series(key, today)
        has_data = any(v is not None for _, _, v in series)
        self.controls.append(self._kpi_row(key, today))
        self.controls.append(self._summary_card())
        if not has_data:
            self.controls.append(card("No habit entries in this period", "",
                                      ft.Text("Mark your habits in the Schedule and the charts will fill in.",
                                              color=INK_2)))
        else:
            self.controls.append(self._trend_card(key, series))
            self.controls.append(self._heatmap_card(key, today))
            self.controls.append(ft.Row([self._ranking_card(key, today), self._weekday_card(key, today)],
                                        spacing=14, vertical_alignment=ft.CrossAxisAlignment.START))
        self.controls.append(self._year_card(today))
        weeks = an.weekly_series(key, today)
        self.controls.append(self._xp_card(weeks))
        self.controls.append(self._study_quest_card(weeks))
        for c in self.controls:
            if isinstance(c, ft.Container):
                c.margin = ft.Margin.symmetric(horizontal=20)
        if self.app_page:
            self.app_page.update()
        if not self.summary_error:  # once per week, in the background; no automatic retries after a failure
            ai_weekly.ensure(on_ready=self._summary_ready)

    def _set_period(self, key):
        self.period = key
        self.refresh()

    # ------------------------------------------------------------ header + KPIs
    def _header(self):
        return ft.Container(content=ft.Row([
            ft.Icon(ft.Icons.INSIGHTS, color=ft.Colors.CYAN_ACCENT, size=28),
            ft.Text("Graphs", size=22, weight=ft.FontWeight.BOLD, expand=True),
            ft.SegmentedButton(
                segments=[ft.Segment(value=k, label=ft.Text(v[0])) for k, v in an.PERIODS.items()],
                selected=[self.period], show_selected_icon=False,
                on_change=lambda e: self._set_period(e.control.selected[0]) if e.control.selected else None),
        ]), padding=ft.Padding.only(top=16))

    def _tile(self, label, value, delta_text=None, delta_good=None, hint=None):
        rows = [ft.Text(label, size=12, color=INK_2),
                ft.Text(value, size=24, weight=ft.FontWeight.W_600, color=INK)]
        if delta_text:
            if delta_good is None:
                rows.append(ft.Text(delta_text, size=11, color=MUTED))
            else:
                color = GOOD if delta_good else BAD
                rows.append(ft.Row([ft.Text("▲" if delta_good else "▼", size=11, color=color),
                                    ft.Text(delta_text, size=11, color=INK_2)], spacing=4))
        return ft.Container(content=ft.Column(rows, spacing=2), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            border_radius=10, padding=14, expand=True, tooltip=hint)

    def _kpi_row(self, key, today):
        k = an.kpis(key, today)
        cur, prev = k["current"], k["previous"]
        vs = "previous " + an.PERIODS[key][0].lower().replace("last ", "")

        def delta(c, p, fmt, higher_is_good=True):
            if c is None or p is None:
                return (f"no data for {vs}", None)
            d = c - p
            if abs(d) < 1e-9:
                return (f"same as {vs}", None)
            good = (d > 0) == higher_is_good
            return (f"{fmt(abs(d))} vs {vs}", good)

        avg = cur["avg_score"]
        tiles = [
            self._tile("Average score", f"{avg:.1f} / 10" if avg is not None else "—",
                       *delta(avg, prev["avg_score"], lambda v: f"{v:.1f}"), hint="Mean of the daily averages"),
            self._tile("Days logged", f"{cur['days_logged']} / {cur['days_total']}" +
                       (f" · {cur['rest_days']} rest" if cur.get("rest_days") else ""),
                       *delta(cur["days_logged"], prev["days_logged"], lambda v: f"{v:g} day{'s' if v != 1 else ''}")),
            self._tile("XP earned", f"{cur['xp']:+.0f}", *delta(cur["xp"], prev["xp"], lambda v: f"{v:.0f} XP"),
                       hint="Habits, quests, studies, reviews and events"),
            self._tile("Best streak", f"{cur['best_streak']} day{'s' if cur['best_streak'] != 1 else ''}",
                       *delta(cur["best_streak"], prev["best_streak"], lambda v: f"{v:g} day{'s' if v != 1 else ''}"),
                       hint=f"Consecutive days with an average of {SCORE_PASSING:g} or more"),
            self._tile("Study time", fmt_minutes(cur["study_minutes"]),
                       *delta(cur["study_minutes"], prev["study_minutes"], fmt_minutes),
                       hint="Time logged in study journal entries"),
        ]
        return ft.Container(content=ft.Row(tiles, spacing=12))

    # ------------------------------------------------------------ weekly summary (Gemini)
    def _summary_ready(self, error=None):
        self.summary_error = error or ""
        try:
            self.refresh()
        except Exception:
            pass

    def _summary_card(self):
        text = ai_weekly.cached()
        if not ai_gemini.is_configured():
            body = ft.Text("Set up your Gemini key (Study → ✨) to get a short summary of each week here.",
                           size=13, color=MUTED)
            action = None
        elif ai_weekly.is_generating():
            body = ft.Row([ft.ProgressRing(width=16, height=16, stroke_width=2),
                           ft.Text("Gemini is reading your week…", size=13, color=INK_2)], spacing=8)
            action = None
        elif text:
            body = ft.Text(text, size=14, color=INK, selectable=True)
            action = ft.IconButton(ft.Icons.REFRESH, icon_size=18, tooltip="Write it again",
                                   on_click=lambda e: (ai_weekly.ensure(self._summary_ready, force=True), self.refresh()))
        else:
            body = ft.Text(self.summary_error or "No summary yet for this week.", size=13,
                           color=BAD if self.summary_error else MUTED)
            action = ft.TextButton("Write this week's summary", icon=ft.Icons.AUTO_AWESOME,
                                   on_click=lambda e: (ai_weekly.ensure(self._summary_ready, force=True), self.refresh()))
        head = ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=ft.Colors.AMBER_ACCENT, size=18),
                       ft.Text("This week", size=16, weight=ft.FontWeight.BOLD, color=INK, expand=True)] +
                      ([action] if action else []))
        return ft.Container(content=ft.Column([head, body], spacing=8), bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                            border_radius=10, padding=16)

    # ------------------------------------------------------------ trend
    def _trend_card(self, key, series):
        points = [fch.LineChartDataPoint(i, round(v, 2), tooltip=f"{label}: {v:.1f}")
                  for i, (label, _, v) in enumerate(series) if v is not None]
        n = len(series)
        goal = fch.LineChartData(points=[fch.LineChartDataPoint(0, SCORE_PASSING, show_tooltip=False),
                                         fch.LineChartDataPoint(n - 1, SCORE_PASSING, show_tooltip=False)],
                                 color=MUTED, stroke_width=1, dash_pattern=[6, 4])
        main = fch.LineChartData(points=points, color=SERIES_1, stroke_width=2, curved=False,
                                 rounded_stroke_cap=True, below_line_bgcolor=ft.Colors.with_opacity(0.10, SERIES_1))
        step = max(1, math.ceil(n / 8))
        labels = [fch.ChartAxisLabel(value=i, label=ft.Text(series[i][0], size=10, color=MUTED))
                  for i in range(0, n, step)]
        chart = fch.LineChart(
            data_series=[goal, main], min_y=0, max_y=10, min_x=0, max_x=max(1, n - 1),
            left_axis=fch.ChartAxis(labels=axis_labels(range(0, 11, 2)), label_size=28),
            bottom_axis=fch.ChartAxis(labels=labels, label_size=24),
            horizontal_grid_lines=fch.ChartGridLines(interval=2, color=GRID, width=1),
            interactive=True, expand=True)
        values = [v for _, _, v in series if v is not None]
        latest = values[-1]
        unit = "week" if an.uses_weeks(key) else "day"
        sub = (f"Average per {unit} • latest {latest:.1f} • period average {sum(values) / len(values):.1f} • "
               f"dashed line = goal {SCORE_PASSING:g}")
        return card("Daily score trend", sub, ft.Container(content=chart, height=230))

    # ------------------------------------------------------------ habit heatmap
    def _heatmap_card(self, key, today):
        columns, rows = an.habit_matrix(key, today)
        cell = {"7d": 44, "30d": 24, "12w": 40, "1y": 15}[key]
        gap = 2
        header = [ft.Container(width=170)]
        step = 1 if len(columns) <= 31 else 4
        for i, (label, first, _) in enumerate(columns):
            header.append(ft.Container(content=ft.Text(label if i % step == 0 else "", size=9, color=MUTED,
                                                       no_wrap=True),
                                       width=cell, alignment=ft.Alignment.CENTER))
        grid = [ft.Row(header, spacing=gap)]
        for name, neg, values, statuses, rests in rows:
            cells = [ft.Container(content=ft.Text(name, size=12, color=INK_2, no_wrap=True,
                                                  overflow=ft.TextOverflow.ELLIPSIS), width=170)]
            for (label, first, last), v, st, rested in zip(columns, values, statuses, rests):
                when = f"{first:%a %d/%m}" if first == last else f"week of {first:%d/%m}"
                tip = f"{name} • {when}: " + (f"{st} ({v:.1f})" if v is not None else
                                              ("rest day" if rested == 1 else f"{rested} rest days") if rested
                                              else "no entry")
                color = seq_color(v) if v is not None else (REST if rested else EMPTY)
                cells.append(ft.Container(width=cell, height=min(cell, 26), bgcolor=color, border_radius=3,
                                          tooltip=tip))
            grid.append(ft.Row(cells, spacing=gap))
        unit = "week (average)" if an.uses_weeks(key) else "day"
        return card("Habit heatmap", f"One cell per habit per {unit}. Vices count as resisted = 10.",
                    ft.Column([ft.Row([ft.Column(grid, spacing=gap)], scroll=ft.ScrollMode.AUTO),
                               scale_legend()], spacing=10))

    # ------------------------------------------------------------ ranking + weekday
    def _ranking_card(self, key, today):
        ranking = an.habit_ranking(key, today)
        width = 260
        rows = []
        for name, neg, avg, days, total, rested in ranking:
            rows.append(ft.Row([
                ft.Text(name + (" (vice)" if neg else ""), size=12, color=INK_2, width=150, no_wrap=True,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Container(content=ft.Container(width=max(3, width * avg / 10), height=12, bgcolor=SERIES_1,
                                                  border_radius=ft.BorderRadius.only(top_right=4, bottom_right=4)),
                             width=width, bgcolor=EMPTY, border_radius=4, alignment=ft.Alignment.CENTER_LEFT,
                             tooltip=f"{name}: average {avg:.1f} on {days} of {total} days" +
                                     (f" ({rested} rest)" if rested else "")),
                ft.Text(f"{avg:.1f}", size=12, color=INK, weight=ft.FontWeight.W_600, width=32),
                ft.Text(f"{days}/{total} days" + (f" • {rested} rest" if rested else ""), size=11, color=MUTED),
            ], spacing=8))
        sub = "Average score, strongest first; the bottom ones are where a little attention pays off most."
        return card("Habit ranking", sub, ft.Column(rows, spacing=8), expand=True)

    def _weekday_card(self, key, today):
        pattern = an.weekday_pattern(key, today)
        groups = [fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
            from_y=0, to_y=round(avg or 0, 2), width=BAR_W, color=SERIES_1 if avg is not None else EMPTY,
            border_radius=ft.BorderRadius.only(top_left=4, top_right=4),
            tooltip=f"{day}: {avg:.1f} ({n} days)" if avg is not None else f"{day}: no entries")])
            for i, (day, avg, n) in enumerate(pattern)]
        chart = fch.BarChart(groups=groups, min_y=0, max_y=10, interactive=True, expand=True,
                             left_axis=fch.ChartAxis(labels=axis_labels(range(0, 11, 2)), label_size=28),
                             bottom_axis=fch.ChartAxis(labels=axis_labels(range(7), lambda i: DAY_NAMES[i]),
                                                       label_size=22),
                             horizontal_grid_lines=fch.ChartGridLines(interval=2, color=GRID, width=1))
        scored = [(d, a) for d, a, _ in pattern if a is not None]
        sub = "Average daily score per weekday"
        if len(scored) >= 2:
            best = max(scored, key=lambda x: x[1])
            worst = min(scored, key=lambda x: x[1])
            sub += f" • strongest {best[0]} ({best[1]:.1f}) • lightest {worst[0]} ({worst[1]:.1f})"
        return card("Weekday pattern", sub, ft.Container(content=chart, height=220), expand=True)

    # ------------------------------------------------------------ year map
    def _year_card(self, today):
        weeks = an.year_map(today)
        size, gap = 13, 2
        # month labels span three week columns so they're never cut ("Oct", not "Oc")
        month_row = [ft.Container(width=30)]
        last_month, skip = None, 0
        for i, wk in enumerate(weeks):
            m = wk[0][0].month
            if skip:
                skip -= 1
            elif m != last_month and i <= len(weeks) - 3:
                month_row.append(ft.Container(content=ft.Text(wk[0][0].strftime("%b"), size=9, color=MUTED,
                                                              no_wrap=True), width=size * 3 + gap * 2))
                skip = 2
            else:
                month_row.append(ft.Container(width=size))
            last_month = m
        day_rows = []
        for di in range(7):
            cells = [ft.Container(content=ft.Text(DAY_NAMES[di] if di in (0, 2, 4) else "", size=9, color=MUTED),
                                  width=30)]
            for wk in weeks:
                d, v, future, rest_only = wk[di]
                cells.append(ft.Container(width=size, height=size, border_radius=2,
                                          bgcolor=ft.Colors.TRANSPARENT if future else (
                                              REST if rest_only else seq_color(v)),
                                          tooltip=None if future else (f"{d:%a %d/%m/%Y}: rest day" if rest_only
                                                                       else f"{d:%a %d/%m/%Y}: {v:.1f}" if v is not None
                                                                       else f"{d:%a %d/%m/%Y}: no entries")))
            day_rows.append(ft.Row(cells, spacing=gap))
        logged = sum(1 for wk in weeks for d, v, f, r in wk if v is not None or r)
        return card("Year map", f"Last 12 months, one square per day • {logged} days logged",
                    ft.Column([ft.Row([ft.Column([ft.Row(month_row, spacing=gap), *day_rows], spacing=gap)],
                                      scroll=ft.ScrollMode.AUTO), scale_legend("Daily score")], spacing=10))

    # ------------------------------------------------------------ XP per week
    def _xp_card(self, weeks):
        values = [w["xp"] for w in weeks]
        lo, hi = min(0.0, min(values, default=0)), max(10.0, max(values, default=0))
        step = nice_step(lo, hi)
        y_min, y_max = math.floor(lo / step) * step, math.ceil(hi / step) * step
        groups = []
        for i, w in enumerate(weeks):
            v = w["xp"]
            groups.append(fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
                from_y=0, to_y=round(v, 1), width=BAR_W if len(weeks) <= 20 else 10,
                color=SERIES_1 if v >= 0 else NEGATIVE,
                border_radius=ft.BorderRadius.only(top_left=4, top_right=4) if v >= 0 else
                ft.BorderRadius.only(bottom_left=4, bottom_right=4),
                tooltip=f"Week of {w['label']}: {v:+.0f} XP")]))
        lstep = max(1, math.ceil(len(weeks) / 10))
        chart = fch.BarChart(groups=groups, min_y=y_min, max_y=y_max, interactive=True, expand=True,
                             left_axis=fch.ChartAxis(labels=axis_labels(range(int(y_min), int(y_max) + 1, int(step)),
                                                                        lambda v: f"{v:g}"), label_size=36),
                             bottom_axis=fch.ChartAxis(labels=[fch.ChartAxisLabel(
                                 value=i, label=ft.Text(w["label"], size=10, color=MUTED))
                                 for i, w in enumerate(weeks) if i % lstep == 0], label_size=22),
                             horizontal_grid_lines=fch.ChartGridLines(interval=step, color=GRID, width=1))
        legend = ft.Row([ft.Container(width=12, height=12, bgcolor=SERIES_1, border_radius=2),
                         ft.Text("XP gained", size=11, color=INK_2), ft.Container(width=8),
                         ft.Container(width=12, height=12, bgcolor=NEGATIVE, border_radius=2),
                         ft.Text("net loss (low habit days)", size=11, color=INK_2)], spacing=4)
        total = sum(values)
        return card("XP per week", f"Net XP from every source • {total:+.0f} XP in these weeks",
                    ft.Column([ft.Container(content=chart, height=220), legend], spacing=8))

    # ------------------------------------------------------------ studies & quests
    def _study_quest_card(self, weeks):
        lstep = max(1, math.ceil(len(weeks) / 8))
        bottom = fch.ChartAxis(labels=[fch.ChartAxisLabel(value=i, label=ft.Text(w["label"], size=10, color=MUTED))
                                       for i, w in enumerate(weeks) if i % lstep == 0], label_size=22)
        narrow = len(weeks) > 20

        hours = [w["study_minutes"] / 60 for w in weeks]
        h_max = max(1.0, max(hours, default=0))
        h_step = nice_step(0, h_max, 4)
        h_top = math.ceil(h_max / h_step) * h_step
        study = fch.BarChart(
            groups=[fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
                from_y=0, to_y=round(h, 2), width=10 if narrow else BAR_W, color=SERIES_1,
                border_radius=ft.BorderRadius.only(top_left=4, top_right=4),
                tooltip=f"Week of {w['label']}: {fmt_minutes(w['study_minutes'])}")]) for i, (w, h) in
                enumerate(zip(weeks, hours))],
            min_y=0, max_y=h_top, interactive=True, expand=True, bottom_axis=bottom,
            left_axis=fch.ChartAxis(labels=axis_labels(_frange(0, h_top, h_step), lambda v: f"{v:g}h"), label_size=34),
            horizontal_grid_lines=fch.ChartGridLines(interval=h_step, color=GRID, width=1))

        c_max = max(1, max((max(w["reviews"], w["quests"]) for w in weeks), default=0))
        c_step = max(1, nice_step(0, c_max, 4))
        c_top = math.ceil(c_max / c_step) * c_step
        counts = fch.BarChart(
            groups=[fch.BarChartGroup(x=i, spacing=2, rods=[
                fch.BarChartRod(from_y=0, to_y=w["reviews"], width=5 if narrow else 10, color=SERIES_1,
                                border_radius=ft.BorderRadius.only(top_left=3, top_right=3),
                                tooltip=f"Week of {w['label']}: {w['reviews']} review(s)"),
                fch.BarChartRod(from_y=0, to_y=w["quests"], width=5 if narrow else 10, color=SERIES_2,
                                border_radius=ft.BorderRadius.only(top_left=3, top_right=3),
                                tooltip=f"Week of {w['label']}: {w['quests']} quest(s)")])
                for i, w in enumerate(weeks)],
            min_y=0, max_y=c_top, interactive=True, expand=True, bottom_axis=bottom,
            left_axis=fch.ChartAxis(labels=axis_labels(range(0, int(c_top) + 1, int(c_step))), label_size=28),
            horizontal_grid_lines=fch.ChartGridLines(interval=c_step, color=GRID, width=1))
        legend = ft.Row([ft.Container(width=12, height=12, bgcolor=SERIES_1, border_radius=2),
                         ft.Text("Study reviews done", size=11, color=INK_2), ft.Container(width=8),
                         ft.Container(width=12, height=12, bgcolor=SERIES_2, border_radius=2),
                         ft.Text("Quests completed", size=11, color=INK_2)], spacing=4)
        total_h = sum(w["study_minutes"] for w in weeks)
        total_r = sum(w["reviews"] for w in weeks)
        total_q = sum(w["quests"] for w in weeks)
        return ft.Container(content=ft.Row([
            card("Study time per week", f"{fmt_minutes(total_h)} logged in your study journal",
                 ft.Container(content=study, height=200), expand=True),
            card("Reviews & quests per week", f"{total_r} review(s) • {total_q} quest(s) completed",
                 ft.Column([ft.Container(content=counts, height=200), legend], spacing=8), expand=True),
        ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START))


def _frange(start, stop, step):
    out, v = [], start
    while v <= stop + 1e-9:
        out.append(round(v, 2))
        v += step
    return out
