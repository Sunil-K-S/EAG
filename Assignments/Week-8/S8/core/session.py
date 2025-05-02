# core/session.py

import os
import sys
from typing import Optional, Any, List, Dict
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import requests  # <-- Add for HTTP support


class ToolStub:
    def __init__(self, name, description="No description", parameters=None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}


class HTTPToolResponse:
    def __init__(self, content):
        self.content = content


class MCP:
    """
    Lightweight wrapper for one-time MCP tool calls using stdio transport.
    Each call spins up a new subprocess and terminates cleanly.
    """

    def __init__(
        self,
        server_script: str = "mcp_server_2.py",
        working_dir: Optional[str] = None,
        server_command: Optional[str] = None,
    ):
        self.server_script = server_script
        self.working_dir = working_dir or os.getcwd()
        self.server_command = server_command or sys.executable

    async def list_tools(self):
        server_params = StdioServerParameters(
            command=self.server_command,
            args=[self.server_script],
            cwd=self.working_dir
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                return tools_result.tools

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        server_params = StdioServerParameters(
            command=self.server_command,
            args=[self.server_script],
            cwd=self.working_dir
        )
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(tool_name, arguments=arguments)


class MultiMCP:
    """
    Manages multiple MCP servers (stdio and HTTP) and routes tool calls.
    """

    def __init__(self, server_configs):
        self.server_configs = server_configs
        self.tool_map = {}  # tool_name -> {config, protocol, url/script, description, parameters}
        # Tool discovery moved to async initialize()

    async def initialize(self):
        await self._discover_tools()
        # Debug print: show discovered tools
        print("[DEBUG] Discovered tools:")
        for name, entry in self.tool_map.items():
            print(f"  - {name}: {entry.get('description', 'No description')}")

    async def _discover_tools(self):
        for config in self.server_configs:
            protocol = config.get("protocol", "stdio")
            if protocol == "stdio":
                # Async tool discovery for stdio servers
                tool_objs = await self._list_stdio_tools_async(config["script"], config.get("cwd"))
                for tool in tool_objs:
                    # tool is likely a tool object with .name, .description, .parameters
                    self.tool_map[tool.name] = {
                        "config": config,
                        "protocol": "stdio",
                        "description": getattr(tool, "description", "No description"),
                        "parameters": getattr(tool, "parameters", {})
                    }
            elif protocol == "http":
                # Register HTTP tools with descriptions and parameters
                self.tool_map["send_email"] = {
                    "config": config,
                    "protocol": "http",
                    "url": f"{config['url']}/tool/send_email",
                    "description": "Send an email using Gmail API. Parameters: to_email (str), subject (str), body (str)",
                    "parameters": {"to_email": "Recipient email address", "subject": "Email subject", "body": "Email body text"}
                }
                self.tool_map["create_spreadsheet"] = {
                    "config": config,
                    "protocol": "http",
                    "url": f"{config['url']}/tool/create_spreadsheet",
                    "description": "Create a new spreadsheet in Google Drive. Parameters: title (str), data (list of dicts, optional)",
                    "parameters": {"title": "Spreadsheet title", "data": "List of row dicts (optional)"}
                }

    async def _list_stdio_tools_async(self, script, cwd):
        # Dynamically query the stdio MCP server for its available tools
        mcp = MCP(server_script=script, working_dir=cwd)
        tools = await mcp.list_tools()
        return tools  # Return tool objects directly

    async def call_tool(self, tool_name: str, arguments: dict) -> Any:
        entry = self.tool_map.get(tool_name)
        if not entry:
            raise ValueError(f"Tool '{tool_name}' not found on any server.")

        if entry["protocol"] == "stdio":
            config = entry["config"]
            params = StdioServerParameters(
                command=sys.executable,
                args=[config["script"]],
                cwd=config.get("cwd", os.getcwd())
            )
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await session.call_tool(tool_name, arguments)
        elif entry["protocol"] == "http":
            resp = requests.post(entry["url"], json=arguments)
            return HTTPToolResponse(content=resp.json())

    async def list_all_tools(self) -> List[str]:
        return list(self.tool_map.keys())

    def get_all_tools(self) -> List[Any]:
        tools = []
        for tool_name, entry in self.tool_map.items():
            if entry["protocol"] == "stdio":
                # For stdio, use the real tool object if available
                # (tool objects are registered in tool_map during discovery)
                # If not available, fallback to ToolStub
                desc = entry.get("description", "No description")
                params = entry.get("parameters", {})
                tools.append(ToolStub(name=tool_name, description=desc, parameters=params))
            elif entry["protocol"] == "http":
                desc = entry.get("description", "No description")
                params = entry.get("parameters", {})
                tools.append(ToolStub(name=tool_name, description=desc, parameters=params))
        return tools

    async def shutdown(self):
        pass  # no persistent sessions to close