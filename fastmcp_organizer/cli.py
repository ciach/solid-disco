import os
# Set service name immediately for OTel/Langfuse
os.environ.setdefault("OTEL_SERVICE_NAME", "fastmcp-organizer")

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
@click.argument('plan_id')
def feedback(plan_id):
    """Provide feedback for a plan to improve AI"""
    service = Context.get_service()
    plan = service.get_plan(plan_id)
    if not plan:
        console.print(f"[bold red]Plan {plan_id} not found[/bold red]")
        return
        
    client = Observability.get_client()
    if not client:
        console.print("[red]Langfuse not configured. Cannot send feedback.[/red]")
        return

    console.print(f"[bold]Providing feedback for Plan: {plan.id}[/bold]")
    console.print("Rate each item (1=Good, 0=Bad). Press Enter to skip.")
    
    for item in plan.items:
        console.print(f"\nFile: [cyan]{Path(item.src_path).name}[/cyan] -> [green]{Path(item.dest_path).parent.name}[/green]")
        console.print(f"Reasoning: {item.reasoning}")
        
        score_input = click.prompt("Score (1/0)", default="", show_default=False)
        if score_input not in ["0", "1"]:
            continue
            
        score_val = int(score_input)
        comment = click.prompt("Comment (optional)", default="", show_default=False)
        
        # We need a trace_id to associate this feedback with. 
        # Making a design choice here: Since we didn't save trace_id in DB, we'll just log a global score
        # OR ideally, we should have stored trace_id in Plan or PlanItem.
        # For now, we'll create a NEW trace for 'Feedback' and reference the filename/category.
        # Better approach: In the future, verify we store trace IDs.
        
        client.score(
            name="user-accuracy",
            value=score_val,
            comment=comment,
            id=f"score-{item.id}", # stable key
            metadata={
                "plan_id": plan_id,
                "file": Path(item.src_path).name,
                "category": Path(item.dest_path).parent.name
            }
        )
        console.print("[green]Feedback Sent![/green]")
        
    Observability.flush()
    console.print("\n[bold green]Thank you! Feedback flushed to Langfuse.[/bold green]")

def main():
    cli()

if __name__ == '__main__':
    main()
