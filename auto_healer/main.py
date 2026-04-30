"""
Auto-Healer Agent - Main Entry Point

This module provides the command-line interface for running the auto-healer agent.
It loads alert data, initializes the graph, and executes the workflow with
proper circuit breakers and error handling.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

from auto_healer.graph import create_graph, visualize_graph
from auto_healer.memory import get_memory_stats, initialize_chromadb

# Initialize Rich console for beautiful output
console = Console()

# Configure logging with Rich
logging.basicConfig(
    level=logging.INFO, format="%(message)s", handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger(__name__)


def load_alert(alert_path: str) -> dict[str, Any]:
    """
    Load alert JSON file from path.

    Args:
        alert_path: Path to alert JSON file

    Returns:
        dict: Alert metadata

    Raises:
        FileNotFoundError: If alert file doesn't exist
        json.JSONDecodeError: If alert file is invalid JSON
    """
    alert_file = Path(alert_path)

    if not alert_file.exists():
        raise FileNotFoundError(f"Alert file not found: {alert_path}")

    with open(alert_file) as f:
        alert_data: dict[str, Any] = json.load(f)

    logger.info(f"Loaded alert from: {alert_path}")

    return alert_data


def display_banner() -> None:
    """Display welcome banner."""
    banner = """
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║          🤖  AUTO-HEALER AGENT  🤖                        ║
    ║                                                           ║
    ║     Autonomous Root Cause Analysis for 5xx Errors        ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    console.print(Panel(banner, style="bold blue"))


def main() -> int:
    """
    Main entry point for the auto-healer agent.

    Parses command-line arguments, loads alert, initializes graph,
    and executes the investigation workflow.
    """
    parser = argparse.ArgumentParser(
        description="Auto-Healer Agent - Autonomous troubleshooting for microservice 5xx errors",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a 500 error
  python -m auto_healer.main --alert examples/alerts/alert_500_zerodivision.json

  # Analyze with debug logging
  python -m auto_healer.main --alert examples/alerts/alert_502_bad_gateway.json --debug

  # Visualize the workflow graph
  python -m auto_healer.main --visualize-only
        """,
    )

    parser.add_argument("--alert", type=str, help="Path to alert JSON file")

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    parser.add_argument(
        "--visualize-only", action="store_true", help="Only visualize the graph, don't run investigation"
    )

    parser.add_argument(
        "--max-iterations", type=int, default=15, help="Maximum recursion limit for graph execution (default: 15)"
    )

    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")

    # Display banner
    display_banner()

    try:
        # Initialize ChromaDB
        console.print("\n[bold cyan]Initializing memory system...[/bold cyan]")
        if not initialize_chromadb():
            console.print("[yellow]Warning: ChromaDB initialization failed. Memory features disabled.[/yellow]")
        else:
            stats = get_memory_stats()
            console.print(f"[green]✓[/green] Memory initialized: {stats.get('total_incidents', 0)} past incidents")

        # Create graph
        console.print("\n[bold cyan]Building agent workflow graph...[/bold cyan]")
        graph = create_graph()
        console.print("[green]✓[/green] Graph compiled successfully")

        # Visualize only mode
        if args.visualize_only:
            console.print("\n[bold cyan]Generating graph visualization...[/bold cyan]")
            mermaid = visualize_graph(graph)
            if mermaid:
                console.print("[green]✓[/green] Mermaid diagram generated (see above)")
            return 0

        # Check if alert file provided
        if not args.alert:
            console.print("[red]Error: --alert argument required (unless using --visualize-only)[/red]")
            parser.print_help()
            return 1

        # Load alert
        console.print(f"\n[bold cyan]Loading alert from: {args.alert}[/bold cyan]")
        alert_info = load_alert(args.alert)

        console.print(
            Panel(
                f"Service: [bold]{alert_info.get('service', 'unknown')}[/bold]\n"
                f"Status Code: [bold red]{alert_info.get('status_code', 0)}[/bold red]\n"
                f"Error: {alert_info.get('error_message', 'Unknown')}\n"
                f"Timestamp: {alert_info.get('timestamp', 'Unknown')}",
                title="Alert Information",
                border_style="red",
            )
        )

        # Prepare initial state
        initial_state = {
            "messages": [],
            "alert_info": alert_info,
            "historical_context": "",
            "next_worker": "",
            "agent_consultation_count": {"log_expert": 0, "infra_expert": 0},
            "approved": False,
            "rca_report": "",
        }

        # Execute graph
        console.print("\n[bold cyan]Starting autonomous investigation...[/bold cyan]\n")

        with Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console
        ) as progress:
            task = progress.add_task("Running agent workflow...", total=None)

            try:
                # Invoke graph with circuit breaker (recursion limit)
                final_state = graph.invoke(
                    initial_state,
                    config={"recursion_limit": args.max_iterations, "configurable": {"thread_id": "main"}},
                )

                progress.update(task, completed=True)

            except RecursionError:
                console.print(f"\n[red]❌ Error: Graph exceeded maximum iterations ({args.max_iterations})[/red]")
                console.print(
                    "[yellow]The agent may be stuck in a loop. Try increasing --max-iterations or check logs.[/yellow]"
                )
                return 1

        # Display results
        console.print("\n" + "=" * 80)
        console.print("[bold green]✓ Investigation Complete![/bold green]")
        console.print("=" * 80)

        # Show if RCA was saved
        if final_state.get("approved", False):
            console.print("\n[green]✓ RCA Report approved and saved to memory![/green]")
        else:
            console.print("\n[yellow]⚠ RCA Report not saved (rejected or interrupted)[/yellow]")

        console.print("\n[dim]Agent workflow completed successfully.[/dim]\n")

        return 0

    except FileNotFoundError as e:
        console.print(f"\n[red]❌ Error: {str(e)}[/red]")
        return 1

    except json.JSONDecodeError as e:
        console.print(f"\n[red]❌ Error: Invalid JSON in alert file: {str(e)}[/red]")
        return 1

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Investigation interrupted by user.[/yellow]")
        return 130

    except Exception as e:
        console.print(f"\n[red]❌ Unexpected error: {str(e)}[/red]")
        if args.debug:
            import traceback

            console.print("\n[dim]" + traceback.format_exc() + "[/dim]")
        return 1


if __name__ == "__main__":
    sys.exit(main())
