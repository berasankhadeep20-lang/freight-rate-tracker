"""
main.py
-------
CLI entry point for the Freight Rate Fluctuation Tracker.

Usage
-----
  python main.py fetch       # pull fresh data + run analysis + print table
  python main.py dash        # regenerate HTML dashboard from DB
  python main.py alerts      # print recent alerts
  python main.py schedule    # run fetch every 6 hours (blocking)
  python main.py reset       # wipe DB and start fresh
"""

import sys
import time

import schedule as sched
from rich.console import Console
from rich.panel import Panel

import config
import database
import analyzer
import dashboard
from fetchers import fetch_all_fred, fetch_all_market

console = Console()

BANNER = """
[bold cyan]
 ███████╗██████╗ ███████╗██╗ ██████╗ ██╗  ██╗████████╗
 ██╔════╝██╔══██╗██╔════╝██║██╔════╝ ██║  ██║╚══██╔══╝
 █████╗  ██████╔╝█████╗  ██║██║  ███╗███████║   ██║   
 ██╔══╝  ██╔══██╗██╔══╝  ██║██║   ██║██╔══██║   ██║   
 ██║     ██║  ██║███████╗██║╚██████╔╝██║  ██║   ██║   
 ╚═╝     ╚═╝  ╚═╝╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═╝   ╚═╝   
[/bold cyan]
[dim]  Freight Rate Fluctuation Tracker  |  github.com/you/freight-rate-tracker[/dim]
"""


def cmd_fetch() -> None:
    console.print(Panel(BANNER, border_style="cyan"))
    console.rule("[cyan]Fetching data[/cyan]")

    rows: list[dict] = []
    rows += fetch_all_market(days=config.HISTORY_DAYS)
    rows += fetch_all_fred(days=config.HISTORY_DAYS)

    inserted = database.upsert_rates(rows)
    database.log_run(inserted)
    console.print(f"\n[bold green]↳ {inserted} new rows inserted into DB[/bold green]\n")

    console.rule("[cyan]Analysis[/cyan]")
    df = database.load_rates(days=config.HISTORY_DAYS)
    df = analyzer.analyze_series(df)
    analyzer.summary_table(df)

    alerts = analyzer.detect_alerts(df)
    if alerts:
        console.rule("[bold red]🚨 Alerts[/bold red]")
        for a in alerts:
            icon = "🔺" if a["alert_type"] == "spike" else "🔻"
            console.print(
                f"  {icon} [bold]{a['label']}[/bold] "
                f"[{'green' if a['alert_type']=='spike' else 'red'}]{a['change_pct']:+.2f}%[/] "
                f"WoW as of {a['date']}"
            )
    else:
        console.print("[dim]No alerts triggered (threshold: "
                      f"{config.ALERT_THRESHOLD_PCT}%)[/dim]")

    console.rule("[cyan]Dashboard[/cyan]")
    dashboard.build_dashboard()


def cmd_dash() -> None:
    console.print("[cyan]Rebuilding dashboard from existing DB data...[/cyan]")
    dashboard.build_dashboard()


def cmd_alerts() -> None:
    alerts_df = database.load_alerts(limit=20)
    if alerts_df.empty:
        console.print("[yellow]No alerts in DB yet.[/yellow]")
        return
    console.print(alerts_df.to_string(index=False))


def cmd_schedule() -> None:
    console.print("[cyan]Scheduler started — fetching every 6 hours.[/cyan]")
    console.print("[dim]Press Ctrl+C to stop.[/dim]\n")
    cmd_fetch()
    sched.every(6).hours.do(cmd_fetch)
    while True:
        sched.run_pending()
        time.sleep(60)


def cmd_reset() -> None:
    import os
    if os.path.exists(config.DB_PATH):
        os.remove(config.DB_PATH)
        console.print(f"[red]Deleted {config.DB_PATH}[/red]")
    database.init_db()
    console.print("[green]Fresh DB initialised.[/green]")


COMMANDS = {
    "fetch":    cmd_fetch,
    "dash":     cmd_dash,
    "alerts":   cmd_alerts,
    "schedule": cmd_schedule,
    "reset":    cmd_reset,
}


if __name__ == "__main__":
    database.init_db()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if cmd not in COMMANDS:
        console.print(f"[red]Unknown command '{cmd}'. Choose from: {list(COMMANDS)}[/red]")
        sys.exit(1)

    COMMANDS[cmd]()
