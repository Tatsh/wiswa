MCP Server
==========

Wiswa includes an MCP server (``wiswa-mcp``) that exposes settings discovery tools for AI
assistants.

Claude Code
-----------

.. code-block:: shell

   claude mcp add wiswa-mcp -- wiswa-mcp

Cursor
------

Add to ``.cursor/mcp.json``:

.. code-block:: json

   {
     "mcpServers": {
       "wiswa-mcp": {
         "command": "wiswa-mcp"
       }
     }
   }

GitHub Copilot CLI
------------------

Add to ``.github/copilot/mcp.json``:

.. code-block:: json

   {
     "mcpServers": {
       "wiswa-mcp": {
         "command": "wiswa-mcp"
       }
     }
   }
