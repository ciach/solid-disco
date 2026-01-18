import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from fastmcp_organizer.server.context import Context
from fastmcp_organizer.server.mcp_agent import mcp
from fastmcp_organizer.utils.observability import Observability

console = Console()

@click.group()
def cli():
    pass

@cli.command()
def server():
    """Starts the MCP Server"""
    console.print("[bold green]Starting MCP Server...[/bold green]")
    mcp.run()

@cli.command()
@click.argument('path')
def scan(path):
    """Scans and generates a plan for a directory"""
    service = Context.get_service()
    try:
        with Observability.trace("CLI Scan", metadata={"path": path}):
            with console.status("[bold blue]Scanning directory..."):
                plan_id = service.create_plan(path)
            console.print(f"[bold green]Plan created successfully![/bold green] ID: [yellow]{plan_id}[/yellow]")
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
    finally:
        Observability.flush()

@cli.command()
@click.argument('plan_id')
def show(plan_id):
    """Shows details of a plan"""
    service = Context.get_service()
    plan = service.get_plan(plan_id)
    if not plan:
        console.print(f"[bold red]Plan {plan_id} not found[/bold red]")
        return

    # Metadata Panel
    meta = f"[bold]Root:[/bold] {plan.root_dir}\n[bold]Status:[/bold] {plan.status}\n[bold]Created:[/bold] {plan.created_at}"
    console.print(Panel(meta, title=f"Plan: {plan.id}", border_style="blue"))

    # Items Table
    table = Table(title="Execution Items", show_header=True, header_style="bold magenta")
    table.add_column("Status", style="cyan", width=12)
    table.add_column("Source", style="white")
    table.add_column("Destination", style="green")
    table.add_column("Reasoning", style="dim")

    for item in plan.items:
        status_color = "green" if item.status == "DONE" else "yellow" if item.status == "PENDING" else "red"
        table.add_row(
            f"[{status_color}]{item.status}[/{status_color}]",
            Path(item.src_path).name,
            Path(item.dest_path).parent.name,
            item.reasoning
        )

    console.print(table)

@cli.command()
@click.argument('plan_id')
def execute(plan_id):
    """Executes a plan by ID"""
    service = Context.get_service()
    try:
        with console.status("[bold blue]Executing plan..."):
            results = service.execute_plan(plan_id)
        
        for res in results:
            if "Error" in res:
                console.print(f"[red]{res}[/red]")
            else:
                console.print(f"[green]{res}[/green]")
    except Exception as e:
         console.print(f"[bold red]Error:[/bold red] {e}")

def main():
    cli()

if __name__ == '__main__':
    main()
