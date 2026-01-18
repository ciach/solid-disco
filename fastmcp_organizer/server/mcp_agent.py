from fastmcp import FastMCP
from fastmcp_organizer.server.context import Context

# Initialize FastMCP Server
mcp = FastMCP("FileOrganizer")

@mcp.tool()
def create_organization_plan(folder_path: str) -> str:
    """
    Scans a folder, classifies files, and generates an execution plan.
    Returns the Plan ID. Call execute_plan with this ID to apply changes.
    """
    service = Context.get_service()
    try:
        plan_id = service.create_plan(folder_path)
        return f"Plan created successfully. ID: {plan_id}. Call execute_plan('{plan_id}') to proceed."
    except Exception as e:
        return f"Error creating plan: {str(e)}"

@mcp.tool()
def execute_plan(plan_id: str) -> str:
    """
    Executes a previously created plan safely.
    Skips items that are already done.
    """
    service = Context.get_service()
    try:
        results = service.execute_plan(plan_id)
        if not results:
            return "Plan executed locally. No actions were pending or all were skipped."
        return "\n".join(results)
    except Exception as e:
        return f"Error executing plan: {str(e)}"

def main():
    mcp.run()
